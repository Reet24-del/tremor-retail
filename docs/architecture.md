# Architecture

## Components

| Path | Responsibility |
|---|---|
| `apps/web` | Next.js 16 + TypeScript. Client pages render only validated API objects; no business math in the browser. |
| `services/api/app/main.py` | FastAPI app, CORS, routers |
| `app/api/` | HTTP layer only: `runs.py`, `signals.py`, `reviews.py` |
| `app/models/contracts.py` | Pydantic contracts (source of truth, mirrored in `apps/web/lib/types.ts`) |
| `app/pipeline/run.py` | Run controller: 7 named stages, status persisted after each stage, failures recorded with the failed stage |
| `app/pipeline/ingest.py` | CSV validation with original line numbers |
| `app/pipeline/invoice_extract.py` | PyMuPDF row reconstruction, LLM/cached/heuristic extraction, fail-closed line validation |
| `app/pipeline/product_match.py` | Normalization, pack-size blocking, RapidFuzz, semantic layer, thresholds, manual overrides |
| `app/pipeline/features.py` | Deterministic formulas (PRD 7.3) and per-product features |
| `app/pipeline/detect.py` | Robust z-scores, impact ranking, spike and bulk-purchase candidates |
| `app/pipeline/correlate.py` | Evidence references and ruled-out explanations per candidate |
| `app/pipeline/explain.py` | Template text, optional LLM wording, number/safety checks |
| `app/pipeline/validate_signal.py` | Publication rule and final schema validation |
| `app/pipeline/evaluate.py` | Frozen evaluation against labels |
| `app/pipeline/llm.py` | The only module that talks to a model provider (Groq, OpenAI-compatible endpoint via httpx, JSON mode, temperature 0) |
| `app/safety/policy.py` | Untrusted-text wrapper, prohibited phrases, unreferenced-number detection |
| `app/storage/repository.py` | DuckDB document store, one table per entity, keyed by run |

## Design decisions

1. **Deterministic core, AI at the edges.** Models read documents and word explanations. Every number shown is computed in `features.py` and re-checked by validators.
2. **Fail closed.** An invoice line that is not found in the PDF, or whose quantity × rate ≠ amount, never enters calculations. A signal with unresolved evidence, invented numbers or prohibited language is blocked and the reason is shown in run warnings.
3. **Provenance everywhere.** CSV rows keep `source_row`; invoice lines keep `page`, `bbox` and `source_text`; features keep input rows; signals keep evidence ids.
4. **Graceful degradation.** No API key → cached (verified against the PDF) or heuristic extraction plus template wording. The mode is visible in the UI and in signal metadata.
5. **Small, explainable detectors.** Robust z-score (median/MAD, with a floor) is stable on 30–50 products; ranking combines anomaly, INR impact, corroboration and data confidence, and each component is stored.
6. **Thin HTTP layer.** Routers only validate input and read the repository; the pipeline is importable and tested without HTTP.

## Ranking

```
rank = 0.35 · min(|z|, 10)/10 + 0.45 · impact / max_impact + 0.10 · corroboration + 0.10 · data_confidence
```

## Evidence strength (not a probability of loss)

Mean of extraction confidence, match confidence, source corroboration, data completeness and anomaly strength. Components are shown on the signal detail page.
