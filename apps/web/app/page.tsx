"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import EvaluationPanel from "@/components/EvaluationPanel";
import SignalCard from "@/components/SignalCard";
import { Loading, PageHead, ProcessingTimeline } from "@/components/ui";
import { api } from "@/lib/api";
import { date, inr, num } from "@/lib/format";
import { useRun } from "@/lib/run-context";
import type { SignalSummary } from "@/lib/types";

export default function Overview() {
  const { run, loading, setRunId } = useRun();
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ runId: string; signals: SignalSummary[] } | null>(null);

  useEffect(() => {
    if (run?.status !== "completed") return;
    const id = run.run_id;
    api.signals(id).then((r) => setLoaded({ runId: id, signals: r.signals })).catch(() => setLoaded({ runId: id, signals: [] }));
  }, [run?.run_id, run?.status]);
  const signals = run?.status === "completed" && loaded?.runId === run.run_id ? loaded.signals : null;

  const startDemo = async () => {
    setStarting(true);
    setErr(null);
    try {
      const r = await api.startDemo();
      setRunId(r.run_id);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not start the sample run");
    } finally {
      setStarting(false);
    }
  };

  const s = run?.status === "completed" ? run.summary : null;
  const open = signals?.filter((x) => x.status !== "dismissed") ?? [];
  const amount = open.reduce((a, x) => a + x.financial_impact.amount, 0);

  return (
    <main className="page">
      <PageHead title="Overview"
        desc="Tremor reads your sales and stock file together with supplier bills, finds where profit may be leaking and shows the proof for every finding. It never takes an action for you." />

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="row between">
          <div style={{ maxWidth: 620 }}>
            <h2>Start an analysis</h2>
            <p className="muted" style={{ marginTop: 4 }}>
              You need one sales and stock CSV and at least two supplier invoice PDFs, so old and new costs can be compared.
              The sample store runs instantly with synthetic data.
            </p>
          </div>
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={startDemo} disabled={starting || run?.status === "running"}>
              {starting ? "Starting…" : "Run sample grocery store"}
            </button>
            <Link className="btn btn-lg" href="/upload">Upload my files</Link>
          </div>
        </div>
        {err && <div className="alert alert-error" style={{ marginTop: 12 }}>{err}</div>}
      </section>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <div className="stat-label">Records analysed</div>
          <div className="stat-value">{s ? num(s.records_analysed) : "—"}</div>
          <div className="stat-sub">{s ? `${s.products} products, ${date(s.date_from)} to ${date(s.date_to)}` : "Run an analysis to see this"}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">Supplier invoices read</div>
          <div className="stat-value">{s ? num(s.invoices_read) : "—"}</div>
          <div className="stat-sub">{s ? `${s.invoice_lines} line items · ${s.extraction_methods?.join(", ")} extraction` : "PDF bills with page references"}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">Signals requiring review</div>
          <div className="stat-value">{signals ? open.filter((x) => x.status === "new" || x.status === "unresolved").length : "—"}</div>
          <div className="stat-sub">{s ? `${s.rejected_candidates} candidates rejected with a reason` : "Evidence-backed findings only"}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">Amount requiring investigation</div>
          <div className="stat-value">{signals ? inr(amount) : "—"}</div>
          <div className="stat-sub">Estimate across open signals, not an accounting loss</div>
        </div>
      </div>

      {loading ? <Loading label="Loading latest run" /> : run?.status === "running" ? (
        <section className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>Analysis in progress</h2>
          <ProcessingTimeline current={run.current_stage} completed={run.completed_stages} />
        </section>
      ) : run?.status === "failed" ? (
        <section className="card card-pad stack">
          <h2>The last run failed</h2>
          <div className="alert alert-error">{run.error}</div>
          <ProcessingTimeline current={run.current_stage} completed={run.completed_stages} failed={run.failed_stage} />
        </section>
      ) : signals && signals.length > 0 ? (
        <section className="card" style={{ marginBottom: 16 }}>
          <div className="card-head">
            <h2>Top signals</h2>
            <Link href="/signals">View all {signals.length}</Link>
          </div>
          {signals.slice(0, 3).map((x) => <SignalCard key={x.signal_id} s={x} />)}
        </section>
      ) : signals ? (
        <section className="card empty">
          <h3>No signals in the reviewed period</h3>
          <p>Tremor checked {s?.records_analysed} records and {s?.invoices_read} invoices from {date(s?.date_from)} to {date(s?.date_to)}.
            That does not prove there is no risk.</p>
        </section>
      ) : (
        <section className="card empty">
          <h3>No analysis yet</h3>
          <p>Run the sample grocery store to see a complete example in under a minute.</p>
        </section>
      )}

      {run?.status === "completed" && run.warnings.length > 0 && (
        <div className="alert alert-warn" style={{ marginBottom: 16 }}>
          <strong>Notes from this run:</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{run.warnings.slice(0, 6).map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <EvaluationPanel />
    </main>
  );
}
