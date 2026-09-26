"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loading, PageHead, SourceBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { date, num, titleCase } from "@/lib/format";
import { useRun } from "@/lib/run-context";
import type { ProductMatch, Source } from "@/lib/types";

export default function SourcesPage() {
  const { run, loading, setRunId } = useRun();
  const router = useRouter();
  const [data, setData] = useState<{ sources: Source[]; matches: ProductMatch[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, string | null>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!run || run.status === "running") return;
    api.sources(run.run_id).then((d) => setData({ sources: d.sources, matches: d.matches })).catch((e) => setErr(e.message));
  }, [run?.run_id, run?.status, run]);

  if (loading) return <main className="page"><Loading /></main>;
  if (!run) return <main className="page"><PageHead title="Data sources" /><div className="card empty"><h3>No files yet</h3><p>Run the sample store or <Link href="/upload">upload your files</Link>.</p></div></main>;

  const review = data?.matches.filter((m) => m.status === "needs_review") ?? [];
  const products = Array.from(new Map((data?.matches ?? []).filter((m) => m.product_id).map((m) => [m.product_id!, m.product_name!])).entries());

  const applyMatches = async () => {
    setBusy(true);
    try {
      const r = await api.confirmMatches(run.run_id, decisions);
      setRunId(r.run_id);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not re-run");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page">
      <PageHead title="Data sources"
        desc="Every file used in the current run, what Tremor read from it and how invoice lines were connected to your products." />
      {err && <div className="alert alert-error">{err}</div>}
      {!data ? <Loading label="Loading sources" /> : (
        <div className="stack">
          <section className="card">
            <div className="card-head"><h2>Files</h2><span className="faint">Run {run.run_id}</span></div>
            <div className="table-wrap" style={{ maxHeight: "none" }}>
              <table>
                <thead><tr><th>Source</th><th>File</th><th>What was read</th><th>Status</th></tr></thead>
                <tbody>
                  {data.sources.map((s) => (
                    <tr key={s.source_id}>
                      <td><SourceBadge t={s.type} /></td>
                      <td><div style={{ fontWeight: 600 }}>{s.filename}</div><div className="mono faint">sha256 {s.content_hash.slice(0, 12)}…</div></td>
                      <td>
                        {s.type === "sales_csv" ? (
                          <>{num(s.row_count)} rows · {String(s.summary.product_count ?? "—")} products · {date(String(s.summary.date_from))} to {date(String(s.summary.date_to))}</>
                        ) : (
                          <>{String(s.summary.supplier_name ?? "—")} · {String(s.summary.invoice_number ?? "—")} · {date(String(s.summary.invoice_date))} · {String(s.summary.line_count)} lines · {s.page_count} page · {String(s.summary.extraction_method)} extraction</>
                        )}
                        {s.messages.length > 0 && <ul className="faint" style={{ margin: "4px 0 0", paddingLeft: 16 }}>{s.messages.map((m, i) => <li key={i}>{m}</li>)}</ul>}
                      </td>
                      <td><span className={`badge ${s.status === "ok" ? "badge-ok" : s.status === "warning" ? "badge-medium" : "badge-high"}`}>{s.status === "ok" ? "Read" : titleCase(s.status)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {review.length > 0 && (
            <section className="card card-pad stack">
              <h2>Matches to confirm</h2>
              <p className="muted">These invoice lines look similar to one of your products, but not certain enough to use automatically.</p>
              {review.map((m) => (
                <div key={m.match_id} className="row between">
                  <div><span className="mono">{m.line_description}</span> <span className="faint">suggested: {m.product_name} ({Math.round(m.confidence * 100)}%)</span></div>
                  <select aria-label={`Match for ${m.line_description}`} value={decisions[m.line_description] ?? "__unset__"}
                    onChange={(e) => setDecisions({ ...decisions, [m.line_description]: e.target.value === "__none__" ? null : e.target.value })}>
                    <option value="__unset__" disabled>Choose…</option>
                    <option value={m.product_id!}>Accept: {m.product_name}</option>
                    <option value="__none__">Leave unmatched</option>
                    {products.filter(([id]) => id !== m.product_id).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                  </select>
                </div>
              ))}
              <div><button className="btn btn-primary" disabled={busy || Object.keys(decisions).length === 0} onClick={applyMatches}>{busy ? "Re-running…" : "Apply and re-run analysis"}</button></div>
            </section>
          )}

          <section className="card">
            <div className="card-head">
              <div><h2>Product matching</h2><div className="faint">Invoice descriptions rarely match shop names. Pack sizes must agree before a match is accepted.</div></div>
              <span className="badge badge-neutral">{data.matches.length} descriptions</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Invoice description</th><th>Your product</th><th>Method</th><th className="r">Fuzzy</th><th className="r">Semantic</th><th className="r">Confidence</th><th>Status</th></tr></thead>
                <tbody>
                  {data.matches.map((m) => (
                    <tr key={m.match_id}>
                      <td className="mono">{m.line_description}</td>
                      <td>{m.product_name ?? <span className="faint">{m.reason || "Unmatched"}</span>}</td>
                      <td>{titleCase(m.method)}</td>
                      <td className="r">{m.scores.fuzzy ?? "—"}</td><td className="r">{m.scores.semantic ?? "—"}</td>
                      <td className="r">{Math.round(m.confidence * 100)}%</td>
                      <td><span className={`badge ${m.status === "accepted" ? "badge-ok" : m.status === "needs_review" ? "badge-medium" : "badge-neutral"}`}>{titleCase(m.status)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
