"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dateTime, titleCase } from "@/lib/format";
import type { EvalReport } from "@/lib/types";

export default function EvaluationPanel() {
  const [rep, setRep] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.latestEvaluation().then(setRep).catch(() => undefined);
  }, []);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setRep(await api.runEvaluation());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card" aria-labelledby="eval-h">
      <div className="card-head">
        <div>
          <h2 id="eval-h">Evaluation on the frozen fixture</h2>
          <div className="faint">Re-runs the real pipeline without cached extraction or frozen matches and compares with labelled answers.</div>
        </div>
        <button className="btn" onClick={run} disabled={busy}>{busy ? "Running evaluation…" : "Run evaluation"}</button>
      </div>
      <div className="card-pad stack">
        {err && <div className="alert alert-error">{err}</div>}
        {!rep && !busy && <p className="muted">No evaluation yet. Run it to see precision, recall and decoy handling.</p>}
        {busy && <p className="faint" role="status">Running 7 stages on 34 products and 10 invoices…</p>}
        {rep && (
          <>
            <div className="row">
              <span className={`badge ${rep.passed ? "badge-ok" : "badge-high"}`}>{rep.passed ? "All targets met" : "Targets not met"}</span>
              <span className="faint">Generated {dateTime(rep.generated_at)} · model {String(rep.versions.model)} · extraction {String(rep.versions.extraction_methods)}</span>
            </div>
            <div className="table-wrap" style={{ maxHeight: "none" }}>
              <table>
                <thead><tr><th>Metric</th><th className="r">Result</th><th className="r">Target</th></tr></thead>
                <tbody>
                  {Object.entries(rep.metrics).map(([k, m]) => (
                    <tr key={k}><td>{titleCase(k)}</td><td className="r">{m.count ?? m.value}</td><td className="r">{m.target ?? "—"}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>Item-level outcomes ({rep.items.length})</summary>
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>ID</th><th>Entity</th><th>Expected</th><th>Actual</th><th>Notes</th></tr></thead>
                <tbody>
                  {rep.items.map((it, i) => (
                    <tr key={i}>
                      <td className="mono">{String(it.id)}</td><td>{String(it.entity)}</td><td>{String(it.expected)}</td>
                      <td>{String(it.actual)}</td>
                      <td className="faint">{String(it.failure_reason ?? it.reason_shown ?? (it.severity_ok ? "severity matches" : ""))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
