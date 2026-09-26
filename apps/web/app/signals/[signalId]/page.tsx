"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import EvidenceViewer from "@/components/EvidenceViewer";
import ReviewControls from "@/components/ReviewControls";
import { Loading, PageHead, SeverityBadge, SourceBadge, StatusBadge, StrengthBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, titleCase } from "@/lib/format";
import type { EvidenceMeta, Review, Signal } from "@/lib/types";

export default function SignalDetail() {
  const { signalId } = useParams<{ signalId: string }>();
  const [data, setData] = useState<{ signal: Signal; evidence: Record<string, EvidenceMeta>; reviews: Review[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  const load = useCallback(() => {
    api.signal(signalId).then((d) => {
      setData(d);
      setActive((a) => a ?? d.signal.evidence_ids.find((e) => d.evidence[e]?.source_type === "invoice_pdf" && e.endsWith("new_invoice"))
        ?? d.signal.evidence_ids[0]);
    }).catch((e) => setErr(e.message));
  }, [signalId]);

  useEffect(() => { load(); }, [load]);

  if (err) return <main className="page"><div className="alert alert-error">{err}</div><p style={{ marginTop: 12 }}><Link href="/signals">Back to signals</Link></p></main>;
  if (!data) return <main className="page"><Loading label="Loading signal" /></main>;
  const { signal: s, evidence } = data;
  const comps = s.evidence_strength_components;

  const EvButton = ({ id }: { id: string }) => {
    const e = evidence[id];
    if (!e) return null;
    return (
      <button className={`ev-item ${active === id ? "active" : ""}`} onClick={() => setActive(id)} aria-pressed={active === id}>
        <SourceBadge t={e.source_type} /><span>{e.label}</span>
      </button>
    );
  };

  return (
    <main className="page">
      <PageHead title={s.title} crumbs={<><Link href="/signals">Signals</Link> / {s.entity.display_name}</>}
        actions={<><SeverityBadge s={s.severity} /><StatusBadge s={s.status} /></>} />

      <div className="split">
        <div className="card">
          <div className="section">
            <h3>What happened</h3>
            <p style={{ fontSize: 15 }}>{s.observation}</p>
            <div className="row" style={{ marginTop: 8 }}>
              <SourceBadge t={s.model_metadata.explanation_source === "llm" ? "ai" : "template"} />
              <span className="faint">Every number above comes from the evidence on the right.</span>
            </div>
          </div>
          <div className="section">
            <h3>Estimated financial effect</h3>
            <div className="impact-amt">{inr(s.financial_impact.amount)}</div>
            <div className="muted">{titleCase(s.financial_impact.label)}: {s.financial_impact.method}. This is an estimate, not an accounting loss.</div>
          </div>
          <div className="section">
            <h3>What it may mean</h3>
            <p>{s.interpretation}</p>
          </div>
          <div className="section">
            <h3>Why Tremor flagged it</h3>
            <div className="row" style={{ marginBottom: 8 }}><StrengthBadge v={s.evidence_strength} /></div>
            <dl className="kv">
              <dt>How unusual (robust z-score vs other products)</dt><dd>{s.ranking.anomaly_score}</dd>
              <dt>Money at stake</dt><dd>{inr(s.ranking.impact_inr)}</dd>
              <dt>Extraction confidence</dt><dd>{Math.round(comps.extraction_confidence * 100)}%</dd>
              <dt>Product match confidence</dt><dd>{Math.round(comps.match_confidence * 100)}%</dd>
              <dt>Sources agreeing</dt><dd>{comps.source_corroboration === 1 ? "CSV and invoice" : "One source"}</dd>
              <dt>Data completeness</dt><dd>{Math.round(comps.data_completeness * 100)}%</dd>
            </dl>
          </div>
          <div className="section">
            <h3>Alternative explanations checked</h3>
            {s.rejected_explanations.length === 0 ? <p className="muted">None could be ruled out with the available data.</p> : (
              <ul style={{ margin: 0, paddingLeft: 18 }} className="stack">
                {s.rejected_explanations.map((a) => (
                  <li key={a.name}>
                    <strong>Ruled out: {a.name}.</strong> <span className="muted">{a.reason}</span>{" "}
                    {a.evidence_ids.map((id) => evidence[id] && (
                      <button key={id} className="btn btn-sm" style={{ marginLeft: 4 }} onClick={() => setActive(id)}>See {evidence[id].source_type === "calendar" ? "calendar" : "rows"}</button>
                    ))}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="section">
            <h3>Recommended check</h3>
            <p style={{ fontWeight: 600 }}>{s.next_check}</p>
          </div>
          <div className="section">
            <h3>Limitations</h3>
            <ul style={{ margin: 0, paddingLeft: 18 }} className="muted">{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </div>
          <div className="section">
            <h3>Your decision</h3>
            <ReviewControls signalId={s.signal_id} reviews={data.reviews} onSaved={load} />
          </div>
        </div>

        <div className="stack" style={{ position: "sticky", top: 64 }}>
          <section className="card card-pad" aria-labelledby="ev-h">
            <h2 id="ev-h" style={{ marginBottom: 10 }}>Evidence</h2>
            <div className="ev-list">{s.evidence_ids.map((id) => <EvButton key={id} id={id} />)}</div>
          </section>
          <section className="card card-pad" aria-live="polite">
            {active ? <EvidenceViewer evidenceId={active} /> : <p className="muted">Select evidence to open it.</p>}
          </section>
          <p className="faint">Detector {s.model_metadata.detector_version} · prompt {s.model_metadata.prompt_version} · model {s.model_metadata.model_name} · extraction {s.model_metadata.extraction_method}</p>
        </div>
      </div>
    </main>
  );
}
