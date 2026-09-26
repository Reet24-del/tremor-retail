"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading, PageHead, ProcessingTimeline } from "@/components/ui";
import { useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const { run, setRunId } = useRun();
  const router = useRouter();
  const { lang } = useLang();
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);

  useEffect(() => {
    if (runId && run?.run_id !== runId) setRunId(runId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    if (run?.run_id === runId && run.status === "completed") {
      const t = setTimeout(() => router.push("/signals"), 900);
      return () => clearTimeout(t);
    }
  }, [run, runId, router]);

  if (!run || run.run_id !== runId) return <main className="page"><Loading label="Loading run" /></main>;

  return (
    <main className="page">
      <PageHead title={run.status === "running" ? L("Analysing your records", "आपके रिकॉर्ड जाँचे जा रहे हैं") : run.status === "failed" ? L("Analysis failed", "जाँच पूरी नहीं हुई") : L("Analysis complete", "जाँच पूरी")}
        desc={run.mode === "demo" ? L("Sample grocery store with synthetic data.", "सिंथेटिक डेटा वाली सैंपल किराना दुकान।") : L("Your uploaded files.", "आपकी अपलोड की गई फ़ाइलें।")}
        crumbs={<><Link href="/dashboard">{L("Overview", "डैशबोर्ड")}</Link> / Run {run.run_id}</>} />
      <section className="card card-pad stack" style={{ maxWidth: 560 }}>
        <ProcessingTimeline current={run.current_stage} completed={run.completed_stages} failed={run.failed_stage} />
        {run.status === "failed" && (
          <>
            <div className="alert alert-error">{run.error}</div>
            <p className="muted">Completed stages are kept. Fix the file named above and try again.</p>
            <div className="row"><Link className="btn" href="/upload">Back to upload</Link><Link className="btn" href="/sources">See data sources</Link></div>
          </>
        )}
        {run.status === "completed" && (
          <div className="row"><span className="badge badge-ok">Done</span><Link href="/signals">Opening signals…</Link></div>
        )}
      </section>
    </main>
  );
}
