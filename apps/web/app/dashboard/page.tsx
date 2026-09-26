"use client";

import Link from "next/link";
import AddBillsBanner from "@/components/AddBillsBanner";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import EvaluationPanel from "@/components/EvaluationPanel";
import SignalCard from "@/components/SignalCard";
import { Loading, PageHead, ProcessingTimeline } from "@/components/ui";
import { api } from "@/lib/api";
import { date, inr, num } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";
import type { SignalSummary } from "@/lib/types";

export default function Overview() {
  const { run, loading, setRunId } = useRun();
  const router = useRouter();
  const { t } = useLang();
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
      <PageHead title={t("ov.title")} desc={t("ov.desc")} />

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="row between">
          <div style={{ maxWidth: 620 }}>
            <h2>{t("ov.startH")}</h2>
            <p className="muted" style={{ marginTop: 4 }}>
              {t("ov.startP")}
            </p>
          </div>
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={startDemo} disabled={starting || run?.status === "running"}>
              {starting ? t("ov.starting") : t("ov.runSample")}
            </button>
            <Link className="btn btn-lg" href="/upload">{t("ov.upload")}</Link>
          </div>
        </div>
        {err && <div className="alert alert-error" style={{ marginTop: 12 }}>{err}</div>}
      </section>

      <AddBillsBanner />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <div className="stat-label">{t("ov.records")}</div>
          <div className="stat-value">{s ? num(s.records_analysed) : "—"}</div>
          <div className="stat-sub">{s ? t("ov.recordsSub", { p: s.products, a: date(s.date_from), b: date(s.date_to) }) : t("ov.runToSee")}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">{t("ov.invoices")}</div>
          <div className="stat-value">{s ? num(s.invoices_read) : "—"}</div>
          <div className="stat-sub">{s ? t("ov.invoicesSub", { n: s.invoice_lines, m: s.extraction_methods?.join(", ") || "none" }) : t("ov.invoicesEmpty")}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">{t("ov.review")}</div>
          <div className="stat-value">{signals ? open.filter((x) => x.status === "new" || x.status === "unresolved").length : "—"}</div>
          <div className="stat-sub">{s ? t("ov.reviewSub", { n: s.rejected_candidates }) : t("ov.reviewEmpty")}</div>
        </div>
        <div className="card card-pad">
          <div className="stat-label">{t("ov.amount")}</div>
          <div className="stat-value">{signals ? inr(amount) : "—"}</div>
          <div className="stat-sub">{t("ov.amountSub")}</div>
        </div>
      </div>

      {loading ? <Loading label={t("ov.loadingRun")} /> : run?.status === "running" ? (
        <section className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>{t("ov.inProgress")}</h2>
          <ProcessingTimeline current={run.current_stage} completed={run.completed_stages} />
        </section>
      ) : run?.status === "failed" ? (
        <section className="card card-pad stack">
          <h2>{t("ov.lastFailed")}</h2>
          <div className="alert alert-error">{run.error}</div>
          <ProcessingTimeline current={run.current_stage} completed={run.completed_stages} failed={run.failed_stage} />
        </section>
      ) : signals && signals.length > 0 ? (
        <section className="card" style={{ marginBottom: 16 }}>
          <div className="card-head">
            <h2>{t("ov.topSignals")}</h2>
            <Link href="/signals">{t("ov.viewAll", { n: signals.length })}</Link>
          </div>
          {signals.slice(0, 3).map((x) => <SignalCard key={x.signal_id} s={x} />)}
        </section>
      ) : signals ? (
        <section className="card empty">
          <h3>{t("ov.noSignalsH")}</h3>
          <p>{t("ov.noSignalsP", { r: s?.records_analysed, i: s?.invoices_read, a: date(s?.date_from), b: date(s?.date_to) })}</p>
        </section>
      ) : (
        <section className="card empty">
          <h3>{t("ov.noRunH")}</h3>
          <p>{t("ov.noRunP")}</p>
        </section>
      )}

      {run?.status === "completed" && run.warnings.length > 0 && (
        <div className="alert alert-warn" style={{ marginBottom: 16 }}>
          <strong>{t("ov.notes")}</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{run.warnings.slice(0, 6).map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <EvaluationPanel />
    </main>
  );
}
