"""Build the data behind the landing-page 3D view (apps/web/public/landing-ridges.json).

Each ridge is one product of the synthetic demo store over its 90 days:
  - height  = daily gross profit (units sold x (price - latest cost)), 3-day smoothed, scaled to the
              product's own peak, so a cost rise that is not passed on shows as a step down
  - margin  = daily gross margin percent, using the latest supplier cost on or before that day
  - gap     = units short against the stock arithmetic (opening - sold - damage + returns)
Products Tremor flags in the demo run are marked, from the first day their margin steps down or their
stock falls short. Nothing here is invented: it is the same fixture the sample run analyses.

Usage: python scripts/build_landing_data.py
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
OUT = ROOT / "apps" / "web" / "public" / "landing-ridges.json"


def main() -> None:
    rows = list(csv.DictReader((DEMO / "sales_stock.csv").open()))
    invoices = json.loads((DEMO / "labels" / "invoices_truth.json").read_text())
    flagged = {
        s["product_id"]
        for s in json.loads((DEMO / "labels" / "signals.json").read_text())[
            "planted_signals"
        ]
    }

    costs: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for inv in invoices:
        for line in inv["line_items"]:
            if line.get("product_id"):
                costs[line["product_id"]].append(
                    (inv["invoice_date"], float(line["unit_cost"]))
                )
    for v in costs.values():
        v.sort()

    dates = sorted({r["transaction_date"] for r in rows})
    by_product: dict[str, dict[str, dict]] = defaultdict(dict)
    names: dict[str, str] = {}
    for r in rows:
        by_product[r["product_id"]][r["transaction_date"]] = r
        names[r["product_id"]] = r["product_name"]

    products = []
    for pid, days in sorted(by_product.items()):
        if pid not in costs:
            continue
        margin, gap, sold = [], [], []
        for d in dates:
            r = days.get(d)
            if r is None:
                margin.append(margin[-1] if margin else 0.0)
                gap.append(0.0)
                sold.append(0.0)
                continue
            price = float(r["unit_selling_price"])
            cost = next(
                (c for cd, c in reversed(costs[pid]) if cd <= d), costs[pid][0][1]
            )
            sold.append(float(r["quantity_sold"]) * (price - cost))
            margin.append(round((price - cost) / price * 100, 2))
            expected = (
                float(r["opening_stock"])
                - float(r["quantity_sold"])
                - float(r.get("recorded_damage") or 0)
                + float(r.get("recorded_returns") or 0)
            )
            gap.append(round(min(0.0, float(r["closing_stock"]) - expected), 1))

        start = None
        if pid in flagged:
            # The persistent change is the last margin step down (earlier ones are promotions that
            # recover); with no margin step, the first stock shortfall.
            drops = [i for i in range(1, len(dates)) if margin[i] < margin[i - 1] - 2]
            gaps = [i for i in range(len(dates)) if gap[i] <= -5]
            start = drops[-1] if drops else (gaps[0] if gaps else None)
        smooth = [
            sum(sold[max(0, i - 1) : i + 2]) / len(sold[max(0, i - 1) : i + 2])
            for i in range(len(sold))
        ]
        peak = max(smooth) or 1.0
        sales = [round(v / peak, 3) for v in smooth]
        products.append(
            {
                "id": pid,
                "name": names[pid],
                "profit": sales,
                "margin": margin,
                "gap": gap,
                "flagged_from": start,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"dates": dates, "products": products}, separators=(",", ":"))
    )
    print(
        f"wrote {OUT.relative_to(ROOT)}: {len(products)} products x {len(dates)} days"
    )
    for p in products:
        if p["flagged_from"] is not None:
            print(" flagged", p["id"], "from", dates[p["flagged_from"]])


if __name__ == "__main__":
    main()
