"""Deterministic financial features (PRD 7.3, 13.3). The code, never the model, does all arithmetic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


def unit_margin(price: float, cost: float) -> float:
    return price - cost


def margin_percent(price: float, cost: float) -> float:
    if price <= 0:
        raise ValueError("selling price must be above zero")
    return (price - cost) / price * 100


def cost_change_percent(prior: float, latest: float) -> float:
    if prior <= 0:
        raise ValueError("prior cost must be above zero")
    return (latest - prior) / prior * 100


def estimated_margin_leakage(units_after: float, prior: float, latest: float) -> float:
    return units_after * max(0.0, latest - prior)


def expected_closing_stock(opening: float, purchased: float, sold: float, damage: float, returns: float) -> float:
    return opening + purchased - sold - damage - returns


def stock_variance_units(actual: float, expected: float) -> float:
    return actual - expected


@dataclass
class Purchase:
    date: date
    unit_cost: float
    quantity: float
    line_id: str
    source_id: str
    invoice_number: str
    supplier_name: str
    confidence: float
    match_confidence: float


@dataclass
class ProductFeatures:
    product_id: str
    product_name: str
    purchases: list[Purchase]
    days: int
    units_sold: float
    revenue: float
    revenue_share: float = 0.0
    velocity: float = 0.0
    # cost / margin
    has_baseline: bool = False
    prior: Purchase | None = None
    latest: Purchase | None = None
    cost_change_pct: float = 0.0
    asp_before: float | None = None
    asp_after: float | None = None
    median_price_after: float | None = None
    prior_margin_pct: float | None = None
    current_margin_pct: float | None = None
    margin_drop_points: float = 0.0
    units_after: float = 0.0
    leakage: float = 0.0
    before_rows: list[int] = field(default_factory=list)
    after_rows: list[int] = field(default_factory=list)
    price_change_dates: list[tuple[str, float]] = field(default_factory=list)
    # stock
    opening_stock: float = 0.0
    purchased_units: float = 0.0
    damage: float = 0.0
    returns: float = 0.0
    expected_closing: float = 0.0
    actual_closing: float = 0.0
    variance_units: float = 0.0
    variance_value: float = 0.0
    variance_pct: float = 0.0
    discrepancy_rows: list[int] = field(default_factory=list)
    discrepancy_dates: list[str] = field(default_factory=list)
    completeness: float = 1.0

    def as_row(self) -> dict:
        d = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ("purchases", "prior", "latest", "before_rows", "after_rows", "discrepancy_rows")
        }
        d["prior_unit_cost"] = self.prior.unit_cost if self.prior else None
        d["latest_unit_cost"] = self.latest.unit_cost if self.latest else None
        d["cost_change_date"] = str(self.latest.date) if self.latest else None
        d["purchase_count"] = len(self.purchases)
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}


def build_features(df: pd.DataFrame, purchases_by_product: dict[str, list[Purchase]]) -> dict[str, ProductFeatures]:
    df = df.sort_values(["product_id", "transaction_date", "source_row"])
    total_rev = float((df["quantity_sold"] * df["unit_selling_price"]).sum()) or 1.0
    all_days = df["transaction_date"].nunique()
    out: dict[str, ProductFeatures] = {}
    for pid, g in df.groupby("product_id", sort=True):
        g = g.reset_index(drop=True)
        name = str(g["product_name"].iloc[-1])
        buys = sorted(purchases_by_product.get(pid, []), key=lambda p: (p.date, p.line_id))
        units = float(g["quantity_sold"].sum())
        rev = float((g["quantity_sold"] * g["unit_selling_price"]).sum())
        f = ProductFeatures(
            pid,
            name,
            buys,
            g["transaction_date"].nunique(),
            units,
            rev,
            revenue_share=rev / total_rev * 100,
            velocity=units / max(1, g["transaction_date"].nunique()),
        )
        f.completeness = g["transaction_date"].nunique() / max(1, all_days)

        # price changes (ignoring single-day noise is not needed on daily aggregates)
        prev = None
        for _, r in g.iterrows():
            if prev is not None and r["unit_selling_price"] != prev:
                f.price_change_dates.append((str(r["transaction_date"]), float(r["unit_selling_price"])))
            prev = r["unit_selling_price"]

        # cost / margin: compare the latest invoice with the previous invoice at a different date
        invoice_dates = sorted({p.date for p in buys})
        if len(invoice_dates) >= 2:
            latest_date, prior_date = invoice_dates[-1], invoice_dates[-2]
            latest = [p for p in buys if p.date == latest_date][-1]
            prior = [p for p in buys if p.date == prior_date][-1]
            f.has_baseline, f.prior, f.latest = True, prior, latest
            f.cost_change_pct = cost_change_percent(prior.unit_cost, latest.unit_cost)
            before = g[(g["transaction_date"] >= prior_date) & (g["transaction_date"] < latest_date) & (g["quantity_sold"] > 0)]
            after = g[(g["transaction_date"] >= latest_date) & (g["quantity_sold"] > 0)]
            if len(before) and len(after):
                f.asp_before = float(before["unit_selling_price"].median())
                f.asp_after = float((after["quantity_sold"] * after["unit_selling_price"]).sum() / after["quantity_sold"].sum())
                f.median_price_after = float(after["unit_selling_price"].median())
                f.prior_margin_pct = margin_percent(f.asp_before, prior.unit_cost)
                f.current_margin_pct = margin_percent(f.asp_after, latest.unit_cost)
                f.margin_drop_points = f.prior_margin_pct - f.current_margin_pct
                f.units_after = float(after["quantity_sold"].sum())
                f.leakage = estimated_margin_leakage(f.units_after, prior.unit_cost, latest.unit_cost)
                f.before_rows = before["source_row"].astype(int).tolist()
                f.after_rows = after["source_row"].astype(int).tolist()
        elif len(invoice_dates) == 1:
            f.latest = buys[-1]

        # stock reconciliation over the whole period
        first_day, last_day = g["transaction_date"].iloc[0], g["transaction_date"].iloc[-1]
        f.opening_stock = float(g["opening_stock"].iloc[0])
        f.actual_closing = float(g["closing_stock"].iloc[-1])
        f.purchased_units = float(sum(p.quantity for p in buys if first_day <= p.date <= last_day))
        f.damage = float(g["recorded_damage"].sum())
        f.returns = float(g["recorded_returns"].sum())
        f.expected_closing = expected_closing_stock(f.opening_stock, f.purchased_units, units, f.damage, f.returns)
        f.variance_units = stock_variance_units(f.actual_closing, f.expected_closing)
        cost_basis = f.latest.unit_cost if f.latest else 0.0
        f.variance_value = abs(f.variance_units) * cost_basis
        f.variance_pct = abs(f.variance_units) / max(1.0, units + f.purchased_units) * 100
        # daily reconciliation pinpoints which rows do not add up
        bought_on = {}
        for p in buys:
            bought_on[p.date] = bought_on.get(p.date, 0) + p.quantity
        for _, r in g.iterrows():
            exp = expected_closing_stock(
                r["opening_stock"],
                bought_on.get(r["transaction_date"], 0),
                r["quantity_sold"],
                r["recorded_damage"],
                r["recorded_returns"],
            )
            if abs(r["closing_stock"] - exp) > 1e-6:
                f.discrepancy_rows.append(int(r["source_row"]))
                f.discrepancy_dates.append(str(r["transaction_date"]))
        out[pid] = f
    return out
