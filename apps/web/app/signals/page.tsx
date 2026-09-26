"use client";

import Link from "next/link";
import AddBillsBanner from "@/components/AddBillsBanner";
import { useEffect, useState } from "react";
import SignalCard from "@/components/SignalCard";
import { Loading, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { useRun } from "@/lib/run-context";
import type { RejectedCandidate, SignalSummary } from "@/lib/types";

export default function SignalsPage() {
  const { run, loading } = useRun();
  const [data, setData] = useState<{ signals: SignalSummary[]; rejected: RejectedCandidate[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<"open" | "all">("open");

  useEffect(() => {
    if (run?.status !== "completed") return;
    api.signals(run.run_id)
      .then((r) => setData({ signals: r.signals, rejected: r.rejected_candidates }))
      .catch((e) => setErr(e.message));
  }, [run?.run_id, run?.status]);

  if (loading) return <main className="page"><Loading /></main>;
  if (!run) {
    return (
      <main className="page">
        <PageHead title="Signals" />
        <div className="card empty"><h3>No analysis yet</h3><p>Start from the <Link href="/">Overview</Link>.</p></div>
      </main>
    );
  }
  if (run.status !== "completed") {
    return (
      <main className="page">
        <PageHead title="Signals" />
        <div className="card empty">
          <h3>{run.status === "running" ? "Analysis still running" : "The last run failed"}</h3>
          <p>{run.status === "running" ? <Link href={`/runs/${run.run_id}`}>Follow progress</Link> : run.error}</p>
        </div>
      </main>
    );
  }

  const list = (data?.signals ?? []).filter((s) => filter === "all" || s.status !== "dismissed");
  return (
    <main className="page">
      <PageHead title="Signals"
        desc="Ranked by severity and estimated amount. Each signal needs a number from your records and proof from a second source."
        actions={
          <div className="seg" role="group" aria-label="Filter signals">
            <button aria-pressed={filter === "open"} onClick={() => setFilter("open")}>Open</button>
            <button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All</button>
          </div>
        } />
      <AddBillsBanner />
      {err && <div className="alert alert-error">{err}</div>}
      {!data ? <Loading label="Loading signals" /> : (
        <div className="stack">
          <section className="card" aria-label="Signal feed">
            {list.length === 0 ? (
              <div className="empty"><h3>No open signals</h3><p>Dismissed signals are under “All”.</p></div>
            ) : list.map((s) => <SignalCard key={s.signal_id} s={s} />)}
          </section>

          <section className="card" aria-labelledby="rej-h">
            <div className="card-head">
              <div>
                <h2 id="rej-h">Checked and not escalated</h2>
                <div className="faint">Unusual patterns Tremor found but did not publish, with the reason.</div>
              </div>
              <span className="badge badge-neutral">{data.rejected.length}</span>
            </div>
            {data.rejected.length === 0 ? <div className="empty">Nothing was rejected in this run.</div> : data.rejected.map((c) => (
              <div key={c.candidate_id} className="section">
                <div className="row" style={{ marginBottom: 4 }}>
                  <span className="badge badge-neutral">Rejected</span>
                  <span className="badge badge-neutral">{titleCase(c.candidate_type)}</span>
                  <strong>{c.title}</strong>
                </div>
                <p className="muted">{c.reason}</p>
              </div>
            ))}
          </section>
        </div>
      )}
    </main>
  );
}
