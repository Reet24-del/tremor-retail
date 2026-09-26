# Backend handoff to the frontend

API contract version **1.1**. Existing endpoints and fields remain available. New fields are additive.
The backend implements the synthetic hackathon workflow; production authentication and tenant isolation remain out of scope.

## Start locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt -r services/api/requirements-dev.txt
cd services/api
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interactive API documentation: `http://127.0.0.1:8000/docs`.
Set the web environment variable `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

## Shared contracts

- `services/api/app/models/contracts.py`: domain models and mutation requests.
- `services/api/app/models/responses.py`: typed HTTP responses.
- `apps/web/lib/contracts.generated.ts`: generated TypeScript types.
- `apps/web/lib/api.ts`: typed frontend client, including retry and invoice correction.
- `docs/api/openapi.json`: generated OpenAPI snapshot.
- `docs/api/examples/`: synthetic response examples.

Run `python scripts/export_contracts.py` after a contract change. CI runs the same command with `--check` to prevent drift.
The generated types describe fully serialized models; submit all fields of an invoice correction, including tax and confidence.

## Run lifecycle

1. `POST /api/runs/demo` or upload `sales_csv` with optional `invoices` to `POST /api/runs`.
2. Save `run_id`, then poll `GET /api/runs/{run_id}` while `status` is `running`.
3. `completed` means processing finished, not that every input was usable. Inspect `issues` and the signal feed.
4. Render `failed` separately from a successful empty result. Completed stages remain available.
5. Display each issue's `message`, `action`, `status`, and available `file`, `field`, `rows`, `source_id`, `product_id`, `line_ids`.

Issue statuses are `needs_review`, `needs_data`, and `unresolved`. They are separate from the run lifecycle.
An unresolved invoice conflict is a data issue, not a published financial claim or a confirmed loss.

| Issue code | Frontend behavior |
|---|---|
| `invoice_confirmation_required` | Open original PDF and invoice-field review |
| `invoice_unreadable` | Ask for a replacement PDF; show the specific warning |
| `product_match_required` | Offer the full product catalogue and an explicit leave-unmatched option |
| `conflicting_invoice_costs` | Show both invoice lines; request correction; do not imply one is authoritative |
| `missing_baseline` | Request an older/current invoice for the product |
| `insufficient_history` | Explain that only a direct cost comparison is available |
| `pipeline_failed` | Show the failed stage and offer retry or a fresh upload |

CSV-only uploads check stock with inferred receipts and selling-price valuation; margin checks need two dated costs per product. The summary exposes `bills_uploaded` and `margin_check`. Add bills later with `POST /api/runs/{run_id}/invoices` (multipart `invoices`); this creates a child run while preserving previous corrections and matches. Duplicate filenames are rejected. Two files may still lack two dated costs for a particular product; that produces `missing_baseline`.

## Invoice confirmation and correction

`GET /api/runs/{run_id}/sources` includes current invoices, original extraction snapshots, prior corrections, all shop products, and issues.
Invoice and line `validation_status` is `verified`, `needs_review`, or `confirmed`.
Low-confidence fields, unverified numeric columns, inconsistent headers, or missing lines hold the invoice for review.
Neither confidence alone nor quantity multiplied by price is sufficient proof.

Submit the full corrected invoice:

```http
PUT /api/runs/{run_id}/invoices/{source_id}
Content-Type: application/json
```

```json
{
  "reason": "Compared every field with the original supplier bill",
  "invoice": {
    "supplier_name": "Supplier",
    "invoice_number": "X-1",
    "invoice_date": "2026-09-10",
    "currency": "INR",
    "invoice_total": 1320,
    "line_items": [{
      "raw_description": "Oil 1 L", "quantity": 10, "unit": "bottle",
      "unit_cost": 132, "tax_amount": 0, "line_total": 1320, "confidence": 0.9
    }]
  }
}
```

This example describes a small illustrative invoice; use the actual current invoice fields for a real request.
The server verifies the corrected fields against the retained PDF. Confirmation cannot override currency restrictions,
known column contradictions, missing numeric evidence, or invalid arithmetic. A human can confirm an unfamiliar
column layout when the numeric values are present. Scans without a text layer still require a replacement digital PDF.

Success returns a **new** `run_id` and `parent_run_id`. Switch the frontend to the new run and poll it.
Original files, old signals, old reviews, original extraction, correction reason, and confirmation timestamp are preserved.
Review outcomes are not copied to recomputed signals. Low original confidence remains visible after human confirmation.

## Product corrections

`POST /api/runs/{run_id}/matches` takes `{"decisions": {"invoice description": "shop-product-id"}}`.
Use `null` to deliberately leave a line unmatched. Populate choices from `sources.products`, not from existing matches.
Descriptions must exist in the current run, product IDs must exist in its catalogue, and incompatible known package sizes are rejected.
Manual decisions are merged with earlier decisions and retained alongside invoice corrections on every descendant run.

Package-incompatible products remain excluded. Unresolved candidate matches hold the affected product. Unknown deliveries
hold stock reconciliation; unreadable invoices conservatively prevent publication until replaced.

## Retry

`POST /api/runs/{run_id}/retry` creates a new run from retained files and decisions. No body is needed.
Do not retry while the parent run is running: the server returns 409. Missing retained inputs also return 409 and require reupload.
Verified original extraction snapshots are reused; unreadable extractions are attempted again. Start a fresh upload to force new extraction.

## Claim citations

Signal detail includes `claims`, each with `claim_id`, `field`, `text`, `kind`, and `evidence_ids`.
Claims currently cover the English canonical text. Hindi `translations` remain available in summaries and detail; use the original evidence panel for translated views.
Render citations adjacent to their sentence and open `GET /api/evidence/{evidence_id}` when selected.
`kind` distinguishes observation, interpretation, and recommendation. Financial calculation wording and rejected explanations are also cited.
Do not treat the existence of a signal-wide evidence list as proof of every sentence.

The explanation model selects from approved wording choices generated from deterministic facts. Novel wording is rejected,
even when all its numbers occur elsewhere in the facts. This deliberately trades paraphrase freedom for checkable claim grounding.
The evaluation now reports `claim_coverage` separately from `evidence_completeness` (ID resolution).

## Errors

HTTP errors use `{"detail": {"message": "...", "issues": [...]}}`.
Upload errors retain the older `detail.errors` array for compatibility. Validation issues name fields and source rows where available.
422 means invalid input, 413 means a file exceeds 10 MB, 409 means the requested run operation is unavailable,
404 means the requested resource does not exist, and 500 is a server failure. Never render any of these as “No signals”.
CSV preview returns HTTP 200 with `ok: false` and issues for invalid CSV content; oversized or wrong-format files return HTTP errors.
Both preview and analysis enforce the same file-size limit. Paths are normalized to safe basenames; collisions are rejected.

## AI configuration

No key is needed for the deterministic fixture. Set `GROQ_API_KEY` in the API process environment to enable Groq.
The server does not automatically read a root `.env` file. Use your host's environment settings or export variables before startup.
Never commit a key. Current model: `TREMOR_LLM_MODEL`, default `llama-3.3-70b-versatile`.

Default matching uses a regional lexicon plus fuzzy scores. `semantic_backend` exposes `lexicon`, `sentence_transformers`,
or `fallback_lexicon`. Optional embeddings require `pip install -r services/api/requirements-embeddings.txt` and
`TREMOR_EMBEDDINGS=1`. Pre-download the model for offline use. Embedding failures produce a visible fallback warning.

## Verification and deployment

```bash
cd services/api
../../.venv/bin/pytest -q
cd ../..
.venv/bin/python scripts/export_contracts.py --check
.venv/bin/python scripts/run_evaluation.py
.venv/bin/python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --runs 3
```

For a separately configured live provider, run the smoke command with `--require-llm`. It fails if extraction or explanation falls back.
The live provider and deployed-host check require credentials/a deployed URL and are separate from mocked-provider regression tests.

For Railway, deploy from the repository root using `railway.json`. Configure `TREMOR_CORS_ORIGINS` for the web origin.
Use a persistent volume and set `TREMOR_RUNTIME_DIR` to that mount to retain uploads, DuckDB, retries, and review history across restarts.
Run one API process; the local DuckDB storage is intended for the single-process hackathon deployment.
After deployment, repeat the smoke command against the public API URL before connecting the deployed frontend.

Frontend work still required: invoice review form, issue display, claim citation buttons, retry action,
correction choices from the full catalogue, and the existing overview's error-versus-empty-state fix.
