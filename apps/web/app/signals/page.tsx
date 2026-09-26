"use client";

import Link from "next/link";
import AddBillsBanner from "@/components/AddBillsBanner";
import { useEffect, useState } from "react";
import SignalCard from "@/components/SignalCard";
import { Loading, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";
import type { RejectedCandidate, SignalSummary } from "@/lib/types";

export default function SignalsPage() {
  const { run, loading } = useRun();
  const { t } = useLang();
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
        <PageHead title={t("sig.title")} />
        <div className="card empty"><h3>{t("sig.noRunH")}</h3><p>{t("sig.startFrom")} <Link href="/dashboard">{t("nav.overview")}</Link>.</p></div>
      </main>
    );
  }
  if (run.status !== "completed") {
    return (
      <main className="page">
        <PageHead title={t("sig.title")} />
        <div className="card empty">
          <h3>{run.status === "running" ? t("sig.running") : t("ov.lastFailed")}</h3>
          <p>{run.status === "running" ? <Link href={`/runs/${run.run_id}`}>{t("sig.follow")}</Link> : run.error}</p>
        </div>
      </main>
    );
  }

  const list = (data?.signals ?? []).filter((s) => filter === "all" || s.status !== "dismissed");
  return (
    <main className="page">
      <PageHead title={t("sig.title")} desc={t("sig.desc")}
        actions={
          <div className="seg" role="group" aria-label="Filter signals">
            <button aria-pressed={filter === "open"} onClick={() => setFilter("open")}>{t("sig.open")}</button>
            <button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>{t("sig.all")}</button>
          </div>
        } />
      <AddBillsBanner />
      {err && <div className="alert alert-error">{err}</div>}
      {!data ? <Loading label={t("sig.loading")} /> : (
        <div className="stack">
          <section className="card" aria-label="Signal feed">
            {list.length === 0 ? (
              <div className="empty"><h3>{t("sig.noneOpenH")}</h3><p>{t("sig.noneOpenP")}</p></div>
            ) : list.map((s) => <SignalCard key={s.signal_id} s={s} />)}
          </section>

          <section className="card" aria-labelledby="rej-h">
            <div className="card-head">
              <div>
                <h2 id="rej-h">{t("sig.rejectedH")}</h2>
                <div className="faint">{t("sig.rejectedP")}</div>
              </div>
              <span className="badge badge-neutral">{data.rejected.length}</span>
            </div>
            {data.rejected.length === 0 ? <div className="empty">{t("sig.noneRejected")}</div> : data.rejected.map((c) => (
              <div key={c.candidate_id} className="section">
                <div className="row" style={{ marginBottom: 4 }}>
                  <span className="badge badge-neutral">{t("sig.rejected")}</span>
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
