"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading, PageHead, ProcessingTimeline } from "@/components/ui";
import { useRun } from "@/lib/run-context";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const { run, setRunId } = useRun();
  const router = useRouter();

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
      <PageHead title={run.status === "running" ? "Analysing your records" : run.status === "failed" ? "Analysis failed" : "Analysis complete"}
        desc={run.mode === "demo" ? "Sample grocery store with synthetic data." : "Your uploaded files."}
        crumbs={<><Link href="/">Overview</Link> / Run {run.run_id}</>} />
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
