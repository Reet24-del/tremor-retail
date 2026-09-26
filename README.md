# Tremor Retail

**Profit leakage intelligence for small grocery retailers.** Tremor reads a shop's sales and stock records together with supplier bills, finds where profit is quietly leaking and shows the exact proof behind every finding. It flags. Humans decide.

Built for **PS-06: AI Signal Intelligence Challenge (MacroVision AI)** at Hack-e-Awadh 2026 by **Team Three Musketeers**.

> Demo: `[add deployed URL]` · Video: `[add fallback recording link]`

---

## 1. Problem and target user

A neighbourhood grocery owner usually knows how much was sold but not why cash or profit is lower than expected. A supplier raises the price of cooking oil, the shop keeps selling at the old price, volume stays high and revenue looks healthy while margin disappears. The evidence is split between a sales spreadsheet and a PDF bill that nobody reads side by side.

**Target user:** the owner or manager of a small grocery shop with a basic sales export and supplier invoices as PDFs, and no financial analyst.

## 2. Solution

Tremor connects a **structured** sales and stock CSV with **unstructured** supplier invoice PDFs and publishes a small number of **evidence-backed signals**. Each signal answers five questions:

1. What changed?
2. Why might it matter financially?
3. Which rows and invoice lines prove it? (clickable, with the PDF page highlighted)
4. What alternative explanation was checked and ruled out?
5. What should a human check next?

## 3. Hero workflow

`Run sample grocery store` → validate CSV → read 10 supplier PDFs → match `SUNPURE OIL 1 LTR` to `Sunpure Cooking Oil 1 L` → calculate margins in code → robust z-score flags the cost jump → link invoice lines and sales rows → publish:

> **Sunpure Cooking Oil 1 L: margin leakage requires review** (High)
> The supplier cost rose from INR 118 to INR 132 on invoice SW-184 (10 Sep 2026) while the selling price stayed near INR 135. Gross margin fell from 12.6 percent to 2.2 percent. **Estimated leakage ₹1,680** (120 units × ₹14). A 12 unit stock difference was also counted. *Ruled out: a temporary promotion (ended 5 Jul).* Next check: verify the supplier rate, recount the 12 units and review the selling price.

The owner then confirms, dismisses (with a reason) or leaves it unresolved. Nothing else happens automatically.

## 4. Data sources

| Source | Type | Notes |
|---|---|---|
| `data/demo/sales_stock.csv` | Structured | 90 days × 34 products, daily sales, price and stock |
| `data/demo/invoices/*.pdf` | Unstructured | 10 supplier invoices from 3 suppliers, rendered PDFs with a real text layer |
| `data/demo/calendar.json` | Structured | Store promotions and festival week (used to rule out explanations) |
| `data/demo/labels/*` | Ground truth | Planted signals, decoys, product matches, invoice truth |

All data is **synthetic** and generated deterministically (`make data`, seed 26). See [docs/data-sources.md](docs/data-sources.md).

## 5. Architecture and AI/ML methods

```
Next.js (apps/web)  ──HTTP──▶  FastAPI (services/api)
                                 │ 1 validate CSV (pandas, row numbers preserved)
                                 │ 2 read bills (PyMuPDF rows+bbox → LLM | cached | heuristic → Pydantic)
                                 │ 3 match products (normalize → pack-size block → RapidFuzz → semantic)
                                 │ 4 features (deterministic finance formulas, no model)
                                 │ 5 detect (robust z-score × INR impact; spike and bulk-buy detectors)
                                 │ 6 correlate evidence (CSV rows + invoice lines + calendar)
                                 │ 7 explain (template or LLM) → validators → publish
                                 ▼
                               DuckDB (runs, sources, matches, features, signals, evidence, reviews)
```

| Task | Method | Why |
|---|---|---|
| Money math | Plain Python | Exact and reproducible; the model never produces a number |
| Invoice fields | PyMuPDF + schema-constrained LLM (fallback: cached validated JSON or deterministic parser) | Handles messy layouts; every line must be found in the PDF and pass qty × rate = amount |
| Product matching | Normalization + lexicon (haldi → turmeric) + RapidFuzz, optional sentence embeddings | Shop and supplier names never match exactly; 5 L never matches 1 L |
| Anomaly ranking | Robust z-score (median/MAD) across products × financial impact | Works on small data and is explainable to a shopkeeper |
| Explanation | Template, optionally reworded by an LLM that is rejected if it adds numbers or banned claims | Plain language without hallucinated facts |

Details: [docs/architecture.md](docs/architecture.md).

## 6. Evidence and human review design

- Every factual claim references evidence ids. Unresolvable references **block publication**.
- A signal needs evidence from **both** the CSV and an invoice (publication rule, PRD 7.4).
- Invoice evidence shows the exact extracted text, page number and a rendered page with the line highlighted.
- Observations, interpretation, ruled-out explanations, limitations and next check are separate fields.
- Reviews (`confirmed` / `dismissed` / `unresolved`) store outcome, reason and time, and never change source data.

## 7. Setup prerequisites

Python 3.11+, Node 20+ (22 recommended), npm.

## 8. Environment variables

Copy `.env.example`. **No key is required**: without one, Tremor uses cached/heuristic extraction and template wording, and the UI says so.

| Variable | Where | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY`, `TREMOR_LLM_MODEL` | API | Enable LLM extraction and wording |
| `TREMOR_CORS_ORIGINS` | API | Allowed web origins |
| `TREMOR_EMBEDDINGS=1` | API | Use sentence-transformers for semantic matching |
| `NEXT_PUBLIC_API_URL` | Web | API base URL |

## 9. Commands

```bash
make setup      # install everything
make api        # API on http://localhost:8000  (docs at /docs)
make web        # web on http://localhost:3000
make test       # 19 backend unit + integration tests
make eval       # frozen evaluation, exits non-zero if a target is missed
make lint       # ruff + eslint + tsc
make data       # regenerate the synthetic fixture
```

CI (`.github/workflows/ci.yml`) runs lint, format check, tests, the evaluation and the web build on every push.

## 10. What works

- Sample run and real uploads (CSV + at least 2 PDFs) with named validation errors
- 7 visible processing stages, failed stage shown, never a silent empty result
- Invoice extraction from the PDF text layer with page and bounding box
- Product matching with pack-size blocking and a manual review/override path that re-runs analysis
- Margin leakage and inventory discrepancy signals with evidence, ruled-out explanations and limitations
- Decoy handling: festival beverage spike and a bulk basmati purchase are rejected with visible reasons
- Confirm / dismiss / unresolved reviews
- Evaluation report (API, UI and CLI)

**Evaluation on the frozen fixture** (real extraction from PDFs, no cached data, no frozen matches):

| Metric | Result | Target |
|---|---|---|
| Recall (planted signals) | 5 of 5 | ≥ 4 of 5 |
| Precision | 5 of 5 | ≥ 80% |
| Invoice extraction accuracy | 560 of 560 fields | ≥ 95% |
| Product match accuracy | 35 of 35 | ≥ 90% |
| Evidence completeness | 27 of 27 | 100% |
| Decoys rejected | 2 of 2, 0 escalated | ≥ 1 |
| Safety violations | 0 | 0 |

## 11. What is incomplete

- Semantic matching uses a lexicon by default; embeddings are optional (`TREMOR_EMBEDDINGS=1`)
- No customer credit or UPI settlement signals (PRD "should/could"); S4 and S5 are margin-leakage variants instead
- Scanned (image-only) PDFs are reported as unreadable; OCR is not included
- Hindi explanations are not implemented

## 12. Synthetic data and model limitations

Metrics describe the synthetic fixture only, not production accuracy. The heuristic parser is tuned to tabular invoices; unusual layouts need the LLM path. Estimates exclude tax, delivery, rebates and unrecorded damage. See [docs/limitations.md](docs/limitations.md).

## 13. Safety and privacy boundaries

Document text is wrapped as untrusted data. Money is calculated only in code. Generated text is rejected if it contains numbers not present in the facts or prohibited claims (theft, fraud, "must raise the price", "deny credit"). Discrepancies are described neutrally. No automatic price, credit, employment, lending or investment action exists. Only synthetic data is in the repository; keys live in environment variables.

## 14. Demo

`[deployed URL]` · `[3-minute recording]` · script: [docs/demo-script.md](docs/demo-script.md)

## 15. Team contributions

| Member | Role | Owned |
|---|---|---|
| Reet Singh | Backend + ML | FastAPI, contracts, extraction, matching, features, detection, correlation, validators, evaluation |
| Roshani Mishra | Frontend | Next.js SaaS shell, Overview, Data sources, Signals, Signal detail, Reviews, upload flow |
| Khushi Yadav | Data, eval, pitch | Synthetic fixture and labels, QA, docs, presentation, demo recording |

## 16. Mentor

`[mentor name]`

## 17. Licence

[MIT](LICENSE)
