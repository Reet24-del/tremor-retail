"""Generate a random, fully labelled synthetic grocery store for stress-testing Tremor.

Each seed gives a different store: product mix, costs, margins, sales volumes and noise, invoice
dates, how invoice descriptions are written, planted problems and decoys. The detector is NOT tuned
on these stores; they exist only to measure how well the unchanged pipeline generalises.

Output layout matches data/demo so the same pipeline and evaluation run on it:
  sales_stock.csv, invoices/*.pdf, calendar.json, labels/{signals,product_matches,invoices_truth}.json
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
from datetime import date, timedelta
from pathlib import Path

from catalog import BEVERAGES, PRODUCTS, SUPPLIERS
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AREAS = ["Aliganj", "Gomti Nagar", "Hazratganj", "Chowk", "Rajajipuram", "Mahanagar", "Alambagh", "Vikas Nagar"]
OWNERS = ["Sharma", "Verma", "Gupta", "Yadav", "Mishra", "Khan", "Singh", "Agarwal", "Tiwari", "Srivastava"]

# Ways suppliers commonly write the same pack size on a bill
UNIT_VARIANTS = {
    r"\b1 ?LTR\b": ["1 LTR", "1LTR", "1 LITRE", "1L", "1 LT"],
    r"\b1 ?KG\b": ["1 KG", "1KG", "1 KGS", "1KGS"],
    r"\b5 ?KG\b": ["5 KG", "5KG", "5 KGS"],
    r"\b(\d+) ?GM\b": ["{0} GM", "{0}GM", "{0} G", "{0}G", "{0} GMS"],
    r"\b(\d+) ?G\b": ["{0}G", "{0} G", "{0} GM", "{0}GMS"],
    r"\b(\d+) ?ML\b": ["{0}ML", "{0} ML"],
}


def ceil10(x: float) -> int:
    return int(math.ceil(x / 10.0) * 10)


def vary_description(desc: str, rng: random.Random) -> str:
    out = desc
    for pat, choices in UNIT_VARIANTS.items():
        m = re.search(pat, out)
        if m:
            pick = rng.choice(choices)
            rep = pick.format(*m.groups()) if m.groups() else pick
            out = out[: m.start()] + rep + out[m.end() :]
            break
    if rng.random() < 0.3:
        out = out.replace(" PKT", "").replace(" PACK", "")
    return out


def generate_store(seed: int, out_dir: Path) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = f"{rng.choice(OWNERS)} Kirana Store, {rng.choice(AREAS)}"
    days_n = rng.choice([75, 90, 105, 120])
    start = date(2026, 5, 1) + timedelta(days=rng.randint(0, 40))
    days = [start + timedelta(days=i) for i in range(days_n)]
    end = days[-1]

    # --- product mix: every supplier keeps at least 5 products
    by_sup: dict[str, list] = {}
    for p in PRODUCTS:
        by_sup.setdefault(p[3], []).append(p)
    chosen = []
    for items in by_sup.values():
        k = rng.randint(max(5, len(items) - 5), len(items))
        chosen += rng.sample(items, k)
    products = []
    for pid, name, desc, sup, unit, _size, base, _price, mean in chosen:
        cost = round(base * rng.uniform(0.9, 1.12))
        markup = rng.uniform(0.10, 0.28)
        products.append(
            {
                "pid": pid,
                "name": name,
                "desc": vary_description(desc, rng),
                "sup": sup,
                "unit": unit,
                "cost": cost,
                "price": max(cost + 2, round(cost * (1 + markup))),
                "mean": max(1, round(mean * rng.uniform(0.7, 1.4))),
                "sd": rng.uniform(0.15, 0.35),
            }
        )
    pmap = {p["pid"]: p for p in products}

    # --- invoice schedule per supplier (3 regular invoices, last one inside the period)
    schedule = {}
    for sup in by_sup:
        d0 = start + timedelta(days=rng.randint(1, 4))
        gap1 = rng.randint(28, 40)
        d2 = end - timedelta(days=rng.randint(10, 18))
        d1 = min(d0 + timedelta(days=gap1), d2 - timedelta(days=18))
        prefix = SUPPLIERS[sup]["prefix"]
        base_no = rng.randint(100, 900)
        schedule[sup] = [(f"{prefix}-{base_no + i * rng.randint(20, 40)}", d) for i, d in enumerate([d0, d1, d2])]

    # --- planted margin leakage: 2-4 non-beverage products, cost jump on the latest invoice
    eligible = [p for p in products if p["pid"] not in BEVERAGES and p["mean"] >= 3]
    rng.shuffle(eligible)
    margin_targets, planted = [], []
    for p in eligible:
        if len(margin_targets) >= rng.randint(2, 4):
            break
        last_date = schedule[p["sup"]][2][1]
        units_after = p["mean"] * ((end - last_date).days + 1)
        jump = max(3, round(p["cost"] * rng.uniform(0.07, 0.15)))
        if units_after * jump < 400:  # immaterial leakage is not a meaningful planted signal
            continue
        two_step = rng.random() < 0.3
        mid = max(1, jump // 2) if two_step else 0
        p["cost_path"] = [p["cost"], p["cost"] + mid, p["cost"] + jump]
        p["late_price"] = None
        if two_step and rng.random() < 0.6:
            p["late_price"] = (last_date + timedelta(days=rng.randint(4, 8)), p["price"] + max(1, jump // 3))
        margin_targets.append(p["pid"])
        planted.append(
            {
                "id": f"M{len(planted) + 1}",
                "signal_type": "margin_leakage",
                "product_id": p["pid"],
                "expected_severity": None,
                "facts": {"cost_path": p["cost_path"], "selling_price": p["price"]},
            }
        )

    # --- planted stock shrink: 1-2 other products
    shrink = {}
    others = [p for p in products if p["pid"] not in margin_targets and p["pid"] not in BEVERAGES and p["mean"] >= 2]
    for p in rng.sample(others, rng.randint(1, 2)):
        units = max(8, round(p["mean"] * rng.uniform(2.5, 4)))
        if units * p["cost"] < 350:
            units = math.ceil(350 / p["cost"]) + 1
        shrink[p["pid"]] = (days[rng.randint(days_n // 3, days_n - 8)], units)
        planted.append(
            {
                "id": f"S{len(shrink)}",
                "signal_type": "inventory_discrepancy",
                "product_id": p["pid"],
                "expected_severity": None,
                "facts": {"stock_variance_units": -units},
            }
        )

    # --- noise on everyone else: small cost drift (0-3%), sometimes matched by a price change
    for p in products:
        if "cost_path" not in p:
            drift = rng.choice([0, 0, 0, 0.01, 0.02, 0.03])
            p["cost_path"] = [p["cost"], p["cost"], round(p["cost"] * (1 + drift))]
            p["late_price"] = None

    # --- decoy 1: festival sales spike on beverages
    bev = [p for p in products if p["pid"] in BEVERAGES]
    fest_len = rng.randint(7, 11)
    fest_start = days[rng.randint(15, days_n - fest_len - 20)]
    festival = {
        "name": rng.choice(["Local mela week", "Wedding season week", "Summer fair week"]),
        "start": fest_start,
        "end": fest_start + timedelta(days=fest_len - 1),
        "mult": rng.uniform(2.2, 3.0),
    }
    # --- decoy 2: off-cycle bulk purchase of one slow item
    bulk_candidates = [
        p for p in products if p["pid"] not in margin_targets and p["pid"] not in shrink and p["pid"] not in BEVERAGES
    ]
    bulk_p = rng.choice(bulk_candidates)
    bulk_date = schedule[bulk_p["sup"]][1][1] + timedelta(days=rng.randint(9, 15))
    bulk_qty = ceil10(bulk_p["mean"] * rng.uniform(35, 55))

    # --- promotion on one margin target, well before its cost change (tests "not a promotion")
    promos = []
    if margin_targets:
        pp = pmap[rng.choice(margin_targets)]
        ps = start + timedelta(days=rng.randint(3, 10))
        promos.append(
            {
                "product_id": pp["pid"],
                "start": ps,
                "end": ps + timedelta(days=4),
                "price": pp["price"] - max(1, round(pp["price"] * 0.05)),
                "label": "Weekend offer",
            }
        )

    # --- daily sales
    sales = {}
    for p in products:
        row = []
        for d in days:
            q = max(0, round(rng.gauss(p["mean"], max(0.6, p["mean"] * p["sd"]))))
            if p["pid"] in BEVERAGES and festival["start"] <= d <= festival["end"]:
                q = round(q * festival["mult"])
            row.append(q)
        sales[p["pid"]] = row

    def price_on(p, d):
        for pr in promos:
            if pr["product_id"] == p["pid"] and pr["start"] <= d <= pr["end"]:
                return pr["price"]
        if p["late_price"] and d >= p["late_price"][0]:
            return p["late_price"][1]
        return p["price"]

    # --- invoices (quantities cover demand to the next invoice)
    purchases = {p["pid"]: {} for p in products}
    invoices = []
    for sup, invs in schedule.items():
        for idx, (num, inv_date) in enumerate(invs):
            nxt = invs[idx + 1][1] if idx + 1 < len(invs) else end + timedelta(days=8)
            lines = []
            for p in [x for x in products if x["sup"] == sup]:
                i0, i1 = max(0, (inv_date - start).days), min(days_n, (nxt - start).days)
                demand = sum(sales[p["pid"]][i0:i1]) + (p["mean"] * 8 if idx == 2 else 0)
                qty = ceil10(demand * 1.05 + p["mean"] * 3)
                cost = p["cost_path"][idx]
                lines.append(
                    {
                        "product_id": p["pid"],
                        "raw_description": p["desc"],
                        "quantity": qty,
                        "unit": p["unit"],
                        "unit_cost": cost,
                        "tax_amount": 0,
                        "line_total": qty * cost,
                    }
                )
                purchases[p["pid"]][inv_date] = purchases[p["pid"]].get(inv_date, 0) + qty
            invoices.append({"sup": sup, "number": num, "date": inv_date, "lines": lines})
    bulk_no = f"{SUPPLIERS[bulk_p['sup']]['prefix']}-{rng.randint(900, 999)}B"
    invoices.append(
        {
            "sup": bulk_p["sup"],
            "number": bulk_no,
            "date": bulk_date,
            "lines": [
                {
                    "product_id": bulk_p["pid"],
                    "raw_description": f"{bulk_p['desc']} (BULK ORDER)",
                    "quantity": bulk_qty,
                    "unit": bulk_p["unit"],
                    "unit_cost": bulk_p["cost_path"][1],
                    "tax_amount": 0,
                    "line_total": bulk_qty * bulk_p["cost_path"][1],
                }
            ],
        }
    )
    purchases[bulk_p["pid"]][bulk_date] = purchases[bulk_p["pid"]].get(bulk_date, 0) + bulk_qty

    # --- stock simulation -> CSV
    rows = []
    for p in products:
        stock = p["mean"] * 12
        for i, d in enumerate(days):
            opening = stock
            bought = purchases[p["pid"]].get(d, 0)
            q = min(sales[p["pid"]][i], opening + bought)
            sh = shrink[p["pid"]][1] if p["pid"] in shrink and shrink[p["pid"]][0] == d else 0
            sh = min(sh, opening + bought - q)
            closing = opening + bought - q - sh
            rows.append(
                {
                    "transaction_id": f"TXN-{d:%Y%m%d}-{p['pid']}",
                    "transaction_date": d.isoformat(),
                    "product_id": p["pid"],
                    "product_name": p["name"],
                    "quantity_sold": q,
                    "unit_selling_price": price_on(p, d),
                    "opening_stock": opening,
                    "closing_stock": closing,
                    "recorded_damage": 0,
                    "recorded_returns": 0,
                }
            )
            stock = closing
    rows.sort(key=lambda r: (r["transaction_date"], r["product_id"]))
    with open(out_dir / "sales_stock.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # --- PDFs + labels
    inv_dir = out_dir / "invoices"
    inv_dir.mkdir(exist_ok=True)
    truth = []
    for inv in invoices:
        total = sum(line["line_total"] for line in inv["lines"])
        t = {
            "supplier_name": SUPPLIERS[inv["sup"]]["name"],
            "invoice_number": inv["number"],
            "invoice_date": inv["date"].isoformat(),
            "currency": "INR",
            "invoice_total": total,
            "line_items": inv["lines"],
            "supplier_key": inv["sup"],
        }
        truth.append(t)
        _render(t, store, inv_dir / f"{inv['number']}.pdf")
    labels = out_dir / "labels"
    labels.mkdir(exist_ok=True)
    (labels / "invoices_truth.json").write_text(json.dumps(truth, indent=2))
    pairs = {line["raw_description"]: line["product_id"] for t in truth for line in t["line_items"]}
    (labels / "product_matches.json").write_text(
        json.dumps({"pairs": [{"raw_description": k, "product_id": v} for k, v in sorted(pairs.items())]}, indent=2)
    )
    decoys = []
    if bev:
        decoys.append(
            {
                "id": "D1",
                "candidate_type": "sales_spike",
                "product_ids": sorted(p["pid"] for p in bev),
                "expected": "rejected",
                "reason": "Festival demand",
            }
        )
    decoys.append(
        {
            "id": "D2",
            "candidate_type": "purchase_spike",
            "product_ids": [bulk_p["pid"]],
            "expected": "rejected",
            "reason": "Off-cycle bulk purchase that reconciles",
        }
    )
    (labels / "signals.json").write_text(
        json.dumps({"dataset_version": f"stress-seed-{seed}", "planted_signals": planted, "decoys": decoys}, indent=2)
    )
    cal = {
        "store": store,
        "promotions": [{**p, "start": p["start"].isoformat(), "end": p["end"].isoformat()} for p in promos],
        "festivals": [
            {
                "name": festival["name"],
                "start": festival["start"].isoformat(),
                "end": festival["end"].isoformat(),
                "affects": "beverages",
            }
        ],
    }
    (out_dir / "calendar.json").write_text(json.dumps(cal, indent=2))
    return {
        "seed": seed,
        "store": store,
        "days": days_n,
        "products": len(products),
        "invoices": len(invoices),
        "planted": len(planted),
        "decoys": len(decoys),
    }


def _render(inv: dict, store: str, path: Path) -> None:
    s = SUPPLIERS[inv["supplier_key"]]
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = [
        Paragraph(f"<b>{s['name'].upper()}</b>", st["Title"]),
        Paragraph(f"{s['addr']} | GSTIN {s['gstin']}", st["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>TAX INVOICE</b>", st["Heading3"]),
        Paragraph(f"Invoice No: {inv['invoice_number']}", st["Normal"]),
        Paragraph(f"Invoice Date: {inv['invoice_date']}", st["Normal"]),
        Paragraph(f"Bill To: {store}, Lucknow", st["Normal"]),
        Spacer(1, 10),
    ]
    data = [["#", "Item Description", "Qty", "Unit", "Rate", "Amount"]]
    for i, line in enumerate(inv["line_items"], 1):
        data.append(
            [
                str(i),
                line["raw_description"],
                str(line["quantity"]),
                line["unit"],
                f"{line['unit_cost']:,.2f}",
                f"{line['line_total']:,.2f}",
            ]
        )
    data.append(["", "TOTAL", "", "", "", f"{inv['invoice_total']:,.2f}"])
    t = Table(data, colWidths=[22, 230, 40, 50, 70, 90])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(t)
    doc.build(story)
