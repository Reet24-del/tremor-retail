# Limitations

- **Synthetic data.** Every metric describes the frozen fixture, not real shops.
- **Estimates, not accounting loss.** Leakage compares with the prior purchase cost and excludes tax, delivery, rebates and unrecorded damage.
- **Invoice layouts.** The deterministic parser expects a tabular layout (`# description qty unit rate amount`). Other layouts need the LLM path; scanned image-only PDFs are reported as unreadable (no OCR).
- **Matching.** The default semantic layer is a small lexicon of trade abbreviations. Enable embeddings for broader coverage. Pack-size conflicts are never auto-resolved.
- **Baseline needed.** A cost change needs at least two invoice dates. With one invoice Tremor says a baseline is missing.
- **Stock.** Discrepancies are record mismatches. They could be unrecorded sales, unlogged damage or counting errors, and are never attributed to a person.
- **Not built:** customer credit and UPI settlement signals, Hindi output, authentication, multi-tenancy, retention controls. A production pilot would need consent, encryption, tenant isolation and a decision on sending documents to a third-party model.
