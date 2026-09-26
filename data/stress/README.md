# Stress-test stores (sample)

Results of running the **unchanged** Tremor pipeline on 50 unseen random stores (held-out seeds 2000-2049).
Full write-up: [docs/stress-test.md](../../docs/stress-test.md).

**Recall 98.5% (198 of 201) · precision 98.0% (198 of 202) · 0 decoys escalated.**

| File | What it is |
|---|---|
| `index.csv` | All 50 stores: name, days, products, invoices, planted problems, found, recall, precision, decoys |
| `report.json` | Full results, including every missed signal and false positive |
| `store_2000/` | A store with a perfect score |
| `store_2025/` | A store with a **miss** (Kabuli Chana cost jump hidden by noise from other products) |
| `store_2039/` | A store with a **false positive** (Parle-G up by one rupee, price flat: a tiny real leakage labelled as noise) |

Each store folder has the same layout as `data/demo`: `sales_stock.csv`, `invoices/*.pdf`, `calendar.json` and
`labels/` (the answer key).

Only 3 of 50 stores are committed to keep the repo small. The generator is deterministic, so every store
regenerates byte-for-byte with:

```bash
make stress        # or: python scripts/stress_test.py --stores 50 --seed-start 2000
```
