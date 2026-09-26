# Three-minute demo script

| Time | Screen | Say |
|---|---|---|
| 0:00–0:20 | Overview | "Sales can look healthy while profit leaks. The reason is split between a sales sheet and a supplier bill nobody reads together." |
| 0:20–0:40 | Click **Run sample grocery store** | "One CSV, ten real supplier PDFs, synthetic data. Watch the seven stages." |
| 0:40–1:05 | Data sources → Product matching | "`SUNPURE OIL 1 LTR` on the bill is `Sunpure Cooking Oil 1 L` in the shop. The 5 litre jar is deliberately **not** matched." |
| 1:05–1:35 | Signals | "Oil is on top: high severity, ₹1,680 estimated leakage, ranked by unusualness × money at stake." |
| 1:35–2:20 | Signal detail → click evidence | Latest invoice (highlighted line on the real page) → earlier invoice → sales rows → calculation. "Every number here comes from code, not the AI." |
| 2:20–2:40 | Signals → Checked and not escalated | "The festival drinks spike and the bulk basmati order look unusual but are rejected, with the reason." |
| 2:40–2:55 | Signal detail → Confirm for investigation | "Tremor never changes a price. The owner decides." |
| 2:55–3:00 | Overview → Evaluation | "5 of 5 planted signals, 0 false positives, both decoys rejected, 0 safety violations." |

Fallback: if the API is down, play the recording. If the LLM is down, nothing changes because the demo runs on verified cached extraction and template wording.
