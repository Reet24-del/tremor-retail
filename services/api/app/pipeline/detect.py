"""Anomaly detection and impact ranking (PRD 13.3).

Robust z-scores (median / MAD) find what is unusual across products; financial impact decides
what matters; the publication rule (correlate.py) decides what is explainable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .. import config
from .features import ProductFeatures


def robust_z(values: dict[str, float], floor: float) -> dict[str, float]:
    s = pd.Series(values, dtype=float)
    if s.empty:
        return {}
    med = float(s.median())
    mad = float((s - med).abs().median())
    scale = max(1.4826 * mad, floor)
    return {k: (v - med) / scale for k, v in values.items()}


@dataclass
class Candidate:
    candidate_id: str
    candidate_type: str  # margin_leakage | inventory_discrepancy | sales_spike | purchase_spike
    product_ids: list[str]
    anomaly_score: float
    impact: float
    details: dict = field(default_factory=dict)
    rejected_reason: str | None = None
    ranking: dict = field(default_factory=dict)


def detect(features: dict[str, ProductFeatures], df: pd.DataFrame, calendar: dict) -> list[Candidate]:
    cands: list[Candidate] = []

    # 1. Supplier cost change -> margin leakage
    with_base = {pid: f.cost_change_pct for pid, f in features.items() if f.has_baseline and f.asp_after}
    cost_z = robust_z(with_base, floor=1.0)
    for pid, z in cost_z.items():
        f = features[pid]
        if z >= config.COST_Z_THRESHOLD and f.leakage >= config.MIN_LEAKAGE_INR:
            cands.append(
                Candidate(
                    f"cand_margin_{pid}",
                    "margin_leakage",
                    [pid],
                    z,
                    f.leakage,
                    {"cost_change_pct": f.cost_change_pct, "margin_drop_points": f.margin_drop_points},
                )
            )

    # 2. Stock that does not reconcile
    var_z = robust_z({pid: f.variance_pct for pid, f in features.items()}, floor=0.5)
    margin_pids = {c.product_ids[0] for c in cands}
    for pid, f in features.items():
        if (
            abs(f.variance_units) >= config.MIN_STOCK_VARIANCE_UNITS
            and f.variance_value >= config.MIN_STOCK_VARIANCE_INR
            and pid not in margin_pids
        ):
            cands.append(
                Candidate(
                    f"cand_stock_{pid}",
                    "inventory_discrepancy",
                    [pid],
                    var_z.get(pid, 0.0),
                    f.variance_value,
                    {"variance_units": f.variance_units},
                )
            )

    # 3. Sales spikes (decoy territory: needs corroborating loss evidence to publish)
    festivals = [(date.fromisoformat(x["start"]), date.fromisoformat(x["end"]), x["name"]) for x in calendar.get("festivals", [])]
    published_pids = {c.product_ids[0] for c in cands}
    spike_by_window: dict[tuple, list[tuple[str, float, float]]] = {}
    for pid, g in df.groupby("product_id"):
        q = g.set_index("transaction_date")["quantity_sold"].astype(float)
        med = float(q.median())
        mad = float((q - med).abs().median())
        scale = max(1.4826 * mad, 1.0, 0.25 * med)
        z = (q - med) / scale
        hot = z[z >= config.SPIKE_Z_THRESHOLD]
        if len(hot) < 4:
            continue
        # attribute the spike to a calendar event when most hot days fall inside it
        key = None
        for s, e, _n in festivals:
            inside = [d for d in hot.index if s <= d <= e]
            if len(inside) >= 0.8 * len(hot):
                key = (s, e)
                break
        if key is None:
            key = (min(hot.index), max(hot.index))
        start, end = key
        extra = float((q[(q.index >= start) & (q.index <= end)] - med).clip(lower=0).sum())
        spike_by_window.setdefault(key, []).append((pid, float(z.max()), extra))
    for (start, end), items in spike_by_window.items():
        pids = sorted(p for p, _, _ in items)
        fest = next((n for s, e, n in festivals if s <= start and end <= e), None)
        loss = [p for p in pids if p in published_pids]
        reason = None
        if fest and not loss:
            reason = (
                f"Expected seasonal demand: the sales rise from {start:%d %b} to {end:%d %b} falls inside "
                f"'{fest}' and there is no cost increase, margin drop or stock difference behind it."
            )
        elif not loss:
            reason = "Higher sales alone are not a risk: no cost, margin or stock evidence supports a loss."
        cands.append(
            Candidate(
                f"cand_spike_{start}",
                "sales_spike",
                pids,
                max(z for _, z, _ in items),
                0.0,
                {"start": str(start), "end": str(end), "festival": fest, "extra_units": {p: e for p, _, e in items}},
                reason,
            )
        )

    # 4. Off-cycle bulk purchases: a large order that arrives while shelves are still well stocked
    opening = {
        (r.product_id, r.transaction_date): float(r.opening_stock)
        for r in df[["product_id", "transaction_date", "opening_stock"]].itertuples(index=False)
    }
    for pid, f in features.items():
        if len(f.purchases) < 3 or not f.velocity:
            continue
        qtys = pd.Series([p.quantity for p in f.purchases], dtype=float)
        dates = sorted({p.date for p in f.purchases})
        for p in f.purchases:
            on_hand_days = opening.get((pid, p.date), 0.0) / f.velocity
            days_cover = p.quantity / f.velocity
            base = float(qtys.median())
            earlier = [d for d in dates if d < p.date]
            gap = (p.date - earlier[-1]).days if earlier else 999
            if on_hand_days >= 30 and days_cover >= 30 and gap <= 21:
                reconciles = abs(f.variance_units) < 1
                reason = None
                if reconciles:
                    reason = (
                        f"Planned restocking: {int(p.quantity)} extra units arrived on {p.invoice_number} "
                        f"({p.date:%d %b}) while about {on_hand_days:.0f} days of stock was still on the shelf. "
                        "Sales plus counted stock reconcile exactly, so no margin or stock loss follows from it."
                    )
                cands.append(
                    Candidate(
                        f"cand_purchase_{pid}_{p.invoice_number}",
                        "purchase_spike",
                        [pid],
                        round(p.quantity / base, 2) if base else 0.0,
                        0.0,
                        {
                            "invoice_number": p.invoice_number,
                            "quantity": p.quantity,
                            "usual_order": base,
                            "days_on_hand_before": round(on_hand_days, 1),
                            "days_of_cover_added": round(days_cover, 1),
                            "line_id": p.line_id,
                        },
                        reason,
                    )
                )

    # Rank publishable candidates: unusualness x impact x corroboration x data confidence
    live = [c for c in cands if c.rejected_reason is None and c.candidate_type in ("margin_leakage", "inventory_discrepancy")]
    max_impact = max([c.impact for c in live], default=1.0) or 1.0
    for c in cands:
        f = features[c.product_ids[0]]
        match_conf = min([p.match_confidence for p in f.purchases], default=0.0)
        extract_conf = min([p.confidence for p in f.purchases], default=0.0)
        anomaly_norm = min(abs(c.anomaly_score), 10.0) / 10.0
        impact_norm = c.impact / max_impact if max_impact else 0.0
        corroboration = 1.0 if f.purchases else 0.5
        data_conf = (match_conf + extract_conf) / 2
        c.ranking = {
            "anomaly_score": round(c.anomaly_score, 2),
            "anomaly_norm": round(anomaly_norm, 3),
            "impact_inr": round(c.impact, 2),
            "impact_norm": round(impact_norm, 3),
            "corroboration": corroboration,
            "data_confidence": round(data_conf, 3),
            "rank_score": round(0.35 * anomaly_norm + 0.45 * impact_norm + 0.10 * corroboration + 0.10 * data_conf, 4),
        }
    cands.sort(key=lambda c: -c.ranking["rank_score"])
    return cands
