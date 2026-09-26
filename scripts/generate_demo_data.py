"""Generate the frozen Tremor Retail demo fixture (sales/stock CSV + invoice ground truth + labels).

Run:  python scripts/generate_demo_data.py && python scripts/generate_demo_invoices.py
Deterministic: fixed seed, no network.
"""
import csv
import json
import math
import random
from datetime import timedelta
from pathlib import Path

from catalog import (BEVERAGES, BULK_INVOICE, DAYS, FESTIVAL, INVOICES, PLANTED_COSTS, PRICE_CHANGES,
                     PRODUCTS, PROMOTIONS, SEED, SHRINK, START, STORE_NAME, SUPPLIERS)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
EXACT_VOLUME = {"SKU-OIL-1L", "SKU-SUG-1K", "SKU-TOOR-1K", "SKU-ATTA-5K"}  # clean numbers for the story


def ceil10(x):
    return int(math.ceil(x / 10.0) * 10)


def main():
    rng = random.Random(SEED)
    days = [START + timedelta(days=i) for i in range(DAYS)]
    end = days[-1]

    # 1. Cost path per product per invoice index
    costs = {}
    for pid, _, _, sup, _, _, base, _, _ in PRODUCTS:
        if pid in PLANTED_COSTS:
            costs[pid] = PLANTED_COSTS[pid]
        else:
            bump = rng.choice([0, 0, 0, 0.01, 0.015, 0.02])
            costs[pid] = [base, base, int(round(base * (1 + bump)))]

    # 2. Daily sales
    sales = {}
    for pid, _, _, _, _, _, _, price, mean in PRODUCTS:
        row = []
        for d in days:
            if pid in EXACT_VOLUME:
                q = mean
            else:
                q = max(0, int(round(rng.gauss(mean, max(0.6, mean * 0.25)))))
            if pid in BEVERAGES and FESTIVAL["start"] <= d <= FESTIVAL["end"]:
                q = int(round(q * FESTIVAL["beverage_multiplier"]))
            row.append(q)
        sales[pid] = row

    def price_on(pid, base_price, d):
        p = base_price
        for promo in PROMOTIONS:
            if promo["product_id"] == pid and promo["start"] <= d <= promo["end"]:
                return promo["price"]
        for frm, newp in PRICE_CHANGES.get(pid, []):
            if d >= frm:
                p = newp
        return p

    # 3. Invoices (quantities cover demand until the next invoice)
    invoices = []  # list of dicts (ground truth)
    by_supplier_products = {}
    for p in PRODUCTS:
        by_supplier_products.setdefault(p[3], []).append(p)
    purchases = {p[0]: {} for p in PRODUCTS}  # pid -> {date: qty}
    for sup, invs in INVOICES.items():
        for idx, (num, inv_date) in enumerate(invs):
            nxt = invs[idx + 1][1] if idx + 1 < len(invs) else end + timedelta(days=8)
            lines = []
            for pid, name, desc, _, unit, size, _, _, mean in by_supplier_products[sup]:
                i0 = max(0, (inv_date - START).days)
                i1 = min(DAYS, (nxt - START).days)
                demand = sum(sales[pid][i0:i1]) + (mean * 8 if idx + 1 == len(invs) else 0)
                qty = ceil10(demand * 1.05 + mean * 2)
                cost = costs[pid][idx]
                lines.append({"product_id": pid, "raw_description": desc, "quantity": qty, "unit": unit,
                              "unit_cost": cost, "tax_amount": 0, "line_total": qty * cost})
                purchases[pid][inv_date] = purchases[pid].get(inv_date, 0) + qty
            if num == "SW-184":
                # Invoice line for a pack size the shop does not stock: must stay unmatched (unit conflict test)
                lines.append({"product_id": None, "raw_description": "SUNPURE OIL 5 LTR JAR", "quantity": 4,
                              "unit": "jar", "unit_cost": 640, "tax_amount": 0, "line_total": 2560})
            invoices.append({"supplier_key": sup, "invoice_number": num, "invoice_date": inv_date, "lines": lines})
    bsup, bnum, bdate = BULK_INVOICE
    invoices.append({"supplier_key": bsup, "invoice_number": bnum, "invoice_date": bdate, "lines": [
        {"product_id": "SKU-BAS-5K", "raw_description": "INDIA GATE BASMATI 5KG (BULK ORDER)", "quantity": 60,
         "unit": "bag", "unit_cost": 520, "tax_amount": 0, "line_total": 31200}]})
    purchases["SKU-BAS-5K"][bdate] = purchases["SKU-BAS-5K"].get(bdate, 0) + 60

    # 4. Stock simulation and CSV rows
    rows = []
    for pid, name, _, _, _, _, _, price, mean in PRODUCTS:
        stock = mean * 12
        for i, d in enumerate(days):
            opening = stock
            bought = purchases[pid].get(d, 0)
            q = min(sales[pid][i], opening + bought)
            damage = 1 if (pid == "SKU-BREAD-400" and d.day in (3, 17)) else 0
            shrink = SHRINK[pid][1] if pid in SHRINK and SHRINK[pid][0] == d else 0
            closing = opening + bought - q - damage - shrink
            assert closing >= 0, (pid, d, closing)
            rows.append({"transaction_id": f"TXN-{d:%Y%m%d}-{pid}", "transaction_date": d.isoformat(),
                         "product_id": pid, "product_name": name, "quantity_sold": q,
                         "unit_selling_price": price_on(pid, price, d), "opening_stock": opening,
                         "closing_stock": closing, "recorded_damage": damage, "recorded_returns": 0})
            stock = closing
    rows.sort(key=lambda r: (r["transaction_date"], r["product_id"]))

    DEMO.mkdir(parents=True, exist_ok=True)
    with open(DEMO / "sales_stock.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 5. Ground truth + labels
    truth = []
    for inv in invoices:
        s = SUPPLIERS[inv["supplier_key"]]
        truth.append({"supplier_name": s["name"], "invoice_number": inv["invoice_number"],
                      "invoice_date": inv["invoice_date"].isoformat(), "currency": "INR",
                      "invoice_total": sum(l["line_total"] for l in inv["lines"]),
                      "line_items": inv["lines"], "supplier_key": inv["supplier_key"]})
    labels = DEMO / "labels"
    labels.mkdir(exist_ok=True)
    (labels / "invoices_truth.json").write_text(json.dumps(truth, indent=2))

    matches = {}
    for inv in truth:
        for l in inv["line_items"]:
            matches[l["raw_description"]] = l["product_id"]
    (labels / "product_matches.json").write_text(json.dumps(
        {"description": "Ground truth: invoice line description -> shop product_id (null = must stay unmatched)",
         "pairs": [{"raw_description": k, "product_id": v} for k, v in sorted(matches.items())]}, indent=2))

    signals = {
        "dataset_version": "demo-fixture-v1",
        "planted_signals": [
            {"id": "S1", "signal_type": "margin_leakage", "product_id": "SKU-OIL-1L", "expected_severity": "high",
             "facts": {"prior_unit_cost": 118, "latest_unit_cost": 132, "selling_price": 135,
                       "prior_margin_percent": 12.6, "current_margin_percent": 2.2,
                       "units_sold_after_cost_change": 120, "estimated_margin_leakage": 1680,
                       "stock_variance_units": -12}},
            {"id": "S2", "signal_type": "margin_leakage", "product_id": "SKU-ATTA-5K", "expected_severity": "medium",
             "facts": {"cost_path": [210, 222, 236], "price_change": "260 to 270 from 2026-09-18"}},
            {"id": "S3", "signal_type": "inventory_discrepancy", "product_id": "SKU-RICE-1K",
             "expected_severity": "medium", "facts": {"stock_variance_units": -20}},
            {"id": "S4", "signal_type": "margin_leakage", "product_id": "SKU-SUG-1K", "expected_severity": "high",
             "facts": {"prior_unit_cost": 42, "latest_unit_cost": 47, "selling_price": 48}},
            {"id": "S5", "signal_type": "margin_leakage", "product_id": "SKU-TOOR-1K", "expected_severity": "medium",
             "facts": {"prior_unit_cost": 128, "latest_unit_cost": 141, "selling_price": 150}},
        ],
        "decoys": [
            {"id": "D1", "candidate_type": "sales_spike", "product_ids": sorted(BEVERAGES),
             "expected": "rejected", "reason": "Beverage sales rise inside the labelled festival period"},
            {"id": "D2", "candidate_type": "purchase_spike", "product_ids": ["SKU-BAS-5K"],
             "expected": "rejected", "reason": "One-time bulk purchase; sales and stock reconcile"},
        ],
    }
    (labels / "signals.json").write_text(json.dumps(signals, indent=2))

    calendar = {"store": STORE_NAME,
                "promotions": [{**p, "start": p["start"].isoformat(), "end": p["end"].isoformat()} for p in PROMOTIONS],
                "festivals": [{"name": FESTIVAL["name"], "start": FESTIVAL["start"].isoformat(),
                               "end": FESTIVAL["end"].isoformat(), "affects": "beverages"}]}
    (DEMO / "calendar.json").write_text(json.dumps(calendar, indent=2))
    print(f"rows={len(rows)} products={len(PRODUCTS)} invoices={len(invoices)}")


if __name__ == "__main__":
    main()
