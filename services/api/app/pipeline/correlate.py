"""Cross-source correlation: turn candidates into evidence-backed signal drafts (PRD 7.2, 7.4, 15)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .. import config
from ..models.contracts import EvidenceReference, RejectedCandidate
from .detect import Candidate
from .features import ProductFeatures

CSV_COLS = [
    "transaction_date",
    "product_name",
    "quantity_sold",
    "unit_selling_price",
    "opening_stock",
    "closing_stock",
    "recorded_damage",
    "recorded_returns",
]


def _csv_excerpt(df: pd.DataFrame, rows: list[int]) -> list[dict]:
    sub = df[df["source_row"].isin(rows)].sort_values("source_row")
    out = []
    for _, r in sub.iterrows():
        d = {"source_row": int(r["source_row"])}
        for c in CSV_COLS:
            v = r[c]
            d[c] = str(v) if c == "transaction_date" else (float(v) if not isinstance(v, str) else v)
        out.append(d)
    return out


def _d(x) -> str:
    return (x if isinstance(x, date) else date.fromisoformat(str(x))).strftime("%-d %b %Y")


def _inr(x: float) -> str:
    return f"INR {x:,.0f}" if float(x).is_integer() else f"INR {x:,.2f}"


def build_signal_drafts(
    run_id: str,
    cands: list[Candidate],
    features: dict[str, ProductFeatures],
    df: pd.DataFrame,
    csv_source_id: str,
    calendar: dict,
):
    drafts, evidence, rejected = [], {}, []
    for c in cands:
        if c.rejected_reason or c.candidate_type not in ("margin_leakage", "inventory_discrepancy"):
            f0 = features[c.product_ids[0]]
            rejected.append(
                RejectedCandidate(
                    candidate_id=c.candidate_id,
                    candidate_type=c.candidate_type,
                    product_ids=c.product_ids,
                    title=_rej_title(c, features),
                    reason=c.rejected_reason or "Not enough cross-source evidence to publish",
                    anomaly_score=round(float(c.anomaly_score), 2),
                    evidence={
                        **c.details,
                        "ranking": c.ranking,
                        "product_names": [features[p].product_name for p in c.product_ids],
                        "velocity": round(f0.velocity, 2),
                    },
                )
            )
            continue
        f = features[c.product_ids[0]]
        kind = "margin" if c.candidate_type == "margin_leakage" else "stock"
        sid = f"sig_{run_id[-6:]}_{kind}_{f.product_id.lower().replace('-', '_')}"
        collector = EvidenceCollector(sid)
        add = collector.add

        if c.candidate_type == "margin_leakage":
            prior, latest = f.prior, f.latest
            e_old = add(
                "old_invoice",
                prior.source_id,
                "invoice_pdf",
                f"Earlier invoice {prior.invoice_number} ({_d(prior.date)}): {prior.supplier_name}",
                {"line_id": prior.line_id, "page": _page(prior.line_id)},
                {"line_id": prior.line_id},
            )
            e_new = add(
                "new_invoice",
                latest.source_id,
                "invoice_pdf",
                f"Latest invoice {latest.invoice_number} ({_d(latest.date)}): {latest.supplier_name}",
                {"line_id": latest.line_id, "page": _page(latest.line_id)},
                {"line_id": latest.line_id},
            )
            e_sales = add(
                "sales_rows",
                csv_source_id,
                "sales_csv",
                f"Sales rows since {_d(latest.date)} ({len(f.after_rows)} days)",
                {"rows": f.after_rows, "columns": CSV_COLS},
                _csv_excerpt(df, f.after_rows),
            )
            e_before = add(
                "sales_before",
                csv_source_id,
                "sales_csv",
                f"Sales rows between the two invoices ({len(f.before_rows)} days)",
                {"rows": f.before_rows, "columns": CSV_COLS},
                _csv_excerpt(df, f.before_rows),
            )
            calc = {
                "prior_unit_cost": prior.unit_cost,
                "latest_unit_cost": latest.unit_cost,
                "unit_cost_increase": round(latest.unit_cost - prior.unit_cost, 2),
                "cost_change_percent": round(f.cost_change_pct, 1),
                "average_selling_price_before": round(f.asp_before, 2),
                "average_selling_price_after": round(f.asp_after, 2),
                "prior_margin_percent": round(f.prior_margin_pct, 1),
                "current_margin_percent": round(f.current_margin_pct, 1),
                "margin_drop_points": round(f.margin_drop_points, 1),
                "units_sold_after_cost_change": f.units_after,
                "estimated_margin_leakage": round(f.leakage, 2),
                "formulas": [
                    "margin_percent = (selling_price - unit_cost) / selling_price x 100",
                    "estimated_margin_leakage = units_sold_after_cost_change x max(0, latest_unit_cost - prior_unit_cost)",
                ],
            }
            e_calc = add(
                "calculation",
                "calc",
                "calculation",
                "Deterministic margin calculation",
                {"formula_version": config.DETECTOR_VERSION},
                calc,
            )
            ev_ids = [e_old, e_new, e_sales, e_before, e_calc]
            e_stock = None
            if abs(f.variance_units) >= 1:
                e_stock = add(
                    "stock_calc",
                    csv_source_id,
                    "sales_csv",
                    f"Stock count difference on {', '.join(_d(x) for x in f.discrepancy_dates)}",
                    {"rows": f.discrepancy_rows, "columns": CSV_COLS},
                    {"rows": _csv_excerpt(df, f.discrepancy_rows), **_stock_calc(f)},
                )
                ev_ids.append(e_stock)
            promos = [x for x in calendar.get("promotions", []) if x["product_id"] == f.product_id]
            e_cal = None
            if promos:
                e_cal = add("calendar", "calendar", "calendar", "Store promotion calendar", {"product_id": f.product_id}, promos)
                ev_ids.append(e_cal)
            facts = {
                **calc,
                "product": f.product_name,
                "supplier": latest.supplier_name,
                "latest_invoice": latest.invoice_number,
                "latest_invoice_date": _d(latest.date),
                "prior_invoice": prior.invoice_number,
                "prior_invoice_date": _d(prior.date),
                "stock_variance_units": f.variance_units,
                "stock_variance_dates": [_d(x) for x in f.discrepancy_dates],
                "price_changes_after_cost_change": [(_d(d), pr) for d, pr in f.price_change_dates if d >= str(latest.date)],
                "promotions": [{"start": _d(x["start"]), "end": _d(x["end"]), "price": x["price"]} for x in promos],
                "revenue_share_percent": round(f.revenue_share, 1),
                "units_per_day": round(f.velocity, 1),
            }
            alts = _margin_alternatives(f, promos, e_sales, e_cal, e_before)
            drafts.append(
                {
                    "signal_id": sid,
                    "candidate": c,
                    "features": f,
                    "facts": facts,
                    "evidence_ids": ev_ids,
                    "evidence_by_role": {"sales": e_sales, "stock": e_stock},
                    "rejected_explanations": alts,
                }
            )
        else:
            e_stock = add(
                "stock_calc",
                csv_source_id,
                "sales_csv",
                f"Rows where counted stock does not add up ({', '.join(_d(x) for x in f.discrepancy_dates)})",
                {"rows": f.discrepancy_rows, "columns": CSV_COLS},
                {"rows": _csv_excerpt(df, f.discrepancy_rows), **_stock_calc(f)},
            )
            buys = [x for x in f.purchases]
            e_buys = []
            for b in buys:
                e_buys.append(
                    add(
                        f"purchase_{b.invoice_number.lower()}",
                        b.source_id,
                        "invoice_pdf",
                        f"Purchase on {b.invoice_number} ({_d(b.date)}): {int(b.quantity)} units",
                        {"line_id": b.line_id, "page": _page(b.line_id)},
                        {"line_id": b.line_id},
                    )
                )
            e_calc = add(
                "calculation",
                "calc",
                "calculation",
                "Stock reconciliation for the whole period",
                {"formula_version": config.DETECTOR_VERSION},
                _stock_calc(f),
            )
            ev_ids = [e_stock, *e_buys, e_calc]
            facts = {
                **_stock_calc(f),
                "product": f.product_name,
                "discrepancy_dates": [_d(x) for x in f.discrepancy_dates],
                "stock_mode": f.stock_mode,
                "value_basis": f.value_basis,
                "valuation_unit_price": f.latest.unit_cost if f.latest else f.variance_value / abs(f.variance_units),
                "variance_value_at_latest_cost": round(f.variance_value, 2),
                "latest_unit_cost": f.latest.unit_cost if f.latest else None,
                "units_per_day": round(f.velocity, 1),
            }
            day_rows = df[df["source_row"].isin(f.discrepancy_rows)]
            alts = []
            if float(day_rows["recorded_damage"].sum() + day_rows["recorded_returns"].sum()) == 0:
                alts.append(
                    {
                        "name": "recorded damage or returns",
                        "reason": "No damage or returns were recorded on the day the count fell short.",
                        "evidence_ids": [e_stock],
                    }
                )
            drafts.append(
                {
                    "signal_id": sid,
                    "candidate": c,
                    "features": f,
                    "facts": facts,
                    "evidence_ids": ev_ids,
                    "evidence_by_role": {"stock": e_stock},
                    "rejected_explanations": alts,
                }
            )
        evidence.update(collector.as_dicts())
    return drafts, evidence, rejected


def _page(line_id: str) -> int:
    """Placeholder page; the run controller replaces invoice locators with the extracted line's page and bbox."""
    return 1


class EvidenceCollector:
    """Builds evidence references for one signal with stable, signal-scoped ids."""

    def __init__(self, signal_id: str):
        self.signal_id = signal_id
        self.items: dict[str, EvidenceReference] = {}

    def add(self, key: str, source_id: str, source_type: str, label: str, locator: dict, excerpt) -> str:
        eid = f"ev_{self.signal_id[4:]}_{key}"
        self.items[eid] = EvidenceReference(
            evidence_id=eid,
            signal_id=self.signal_id,
            source_id=source_id,
            source_type=source_type,
            label=label,
            locator=locator,
            excerpt=excerpt,
        )
        return eid

    def as_dicts(self) -> dict[str, dict]:
        return {k: v.model_dump(mode="json") for k, v in self.items.items()}


def _stock_calc(f: ProductFeatures) -> dict:
    return {
        "opening_stock": f.opening_stock,
        "purchased_units": f.purchased_units,
        "sold_units": f.units_sold,
        "recorded_damage": f.damage,
        "recorded_returns": f.returns,
        "expected_closing_stock": f.expected_closing,
        "actual_closing_stock": f.actual_closing,
        "stock_variance_units": f.variance_units,
        "formula": "expected_closing = opening + purchased - sold - damage - returns",
    }


def _margin_alternatives(f: ProductFeatures, promos, e_sales, e_cal, e_before) -> list[dict]:
    alts = []
    {r for _, r in f.price_change_dates}
    if promos:
        last_end = max(date.fromisoformat(x["end"]) for x in promos)
        if f.latest and last_end < f.latest.date and f.median_price_after and f.median_price_after >= f.asp_before:
            alts.append(
                {
                    "name": "a temporary promotion",
                    "reason": f"The only recorded promotion ended on {_d(last_end)}, before the cost change, and the "
                    f"selling price has stayed at {_inr(f.median_price_after)} since.",
                    "evidence_ids": [e_sales, e_cal],
                }
            )
    if f.median_price_after is not None and f.asp_before is not None and f.asp_after <= f.asp_before:
        alts.append(
            {
                "name": "the selling price already covering it",
                "reason": f"The average selling price was {_inr(f.asp_after)} after the new cost arrived.",
                "evidence_ids": [e_sales],
            }
        )
    if f.velocity and f.units_after / max(1, len(f.after_rows)) >= 0.8 * f.velocity:
        alts.append(
            {
                "name": "too few sales to matter",
                "reason": f"The product kept selling about {round(f.units_after / max(1, len(f.after_rows)), 1)} "
                "units a day after the change, so the smaller margin applies to steady volume.",
                "evidence_ids": [e_sales],
            }
        )
    return alts


def _rej_title(c: Candidate, features) -> str:
    names = ", ".join(features[p].product_name for p in c.product_ids[:4])
    if c.candidate_type == "sales_spike":
        return f"Sales rise: {names}"
    if c.candidate_type == "purchase_spike":
        return f"Large purchase: {names}"
    return f"{c.candidate_type.replace('_', ' ').title()}: {names}"
