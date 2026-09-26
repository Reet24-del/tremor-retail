"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import EvidenceViewer from "@/components/EvidenceViewer";
import ReviewControls from "@/components/ReviewControls";
import { Loading, PageHead, SeverityBadge, SourceBadge, StatusBadge, StrengthBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, titleCase } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import type { EvidenceMeta, Review, Signal } from "@/lib/types";

export default function SignalDetail() {
  const { signalId } = useParams<{ signalId: string }>();
  const [data, setData] = useState<{ signal: Signal; evidence: Record<string, EvidenceMeta>; reviews: Review[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const { lang } = useLang();
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);

  const load = useCallback(() => {
    api.signal(signalId).then((d) => {
      setData(d);
      setActive((a) => a ?? d.signal.evidence_ids.find((e) => d.evidence[e]?.source_type === "invoice_pdf" && e.endsWith("new_invoice"))
        ?? d.signal.evidence_ids[0]);
    }).catch((e) => setErr(e.message));
  }, [signalId]);

  useEffect(() => { load(); }, [load]);

  if (err) return <main className="page"><div className="alert alert-error">{err}</div><p style={{ marginTop: 12 }}><Link href="/signals">{L("Back to signals", "संकेतों पर वापस")}</Link></p></main>;
  if (!data) return <main className="page"><Loading label={L("Loading signal", "संकेत लोड हो रहा है")} /></main>;
  const { signal: s, evidence } = data;
  const comps = s.evidence_strength_components;
  // Hindi text comes from the API, built from the same validated facts as the English text.
  const hi = lang === "hi" ? s.translations?.hi : undefined;
  const tx = {
    title: hi?.title ?? s.title,
    observation: hi?.observation ?? s.observation,
    interpretation: hi?.interpretation ?? s.interpretation,
    next_check: hi?.next_check ?? s.next_check,
    limitations: hi?.limitations ?? s.limitations,
    impact_label: hi?.impact_label ?? titleCase(s.financial_impact.label),
  };
  const textLang = hi ? "hi" : "en";

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
      <PageHead title={tx.title} crumbs={<><Link href="/signals">{L("Signals", "संकेत")}</Link> / {s.entity.display_name}</>}
        actions={<><SeverityBadge s={s.severity} /><StatusBadge s={s.status} /></>} />

      <div className="split">
        <div className="card">
          <div className="section">
            <h3>{L("What happened", "क्या हुआ")}</h3>
            <p style={{ fontSize: 15 }} lang={textLang}>{tx.observation}</p>
            <div className="row" style={{ marginTop: 8 }}>
              <SourceBadge t={s.model_metadata.explanation_source === "llm" ? "ai" : "template"} />
              <span className="faint">{L("Every number above comes from the evidence on the right.", "ऊपर का हर आँकड़ा दाईं ओर के सबूत से आता है।")}</span>
            </div>
          </div>
          <div className="section">
            <h3>{L("Estimated financial effect", "अनुमानित आर्थिक असर")}</h3>
            <div className="impact-amt">{inr(s.financial_impact.amount)}</div>
            <div className="muted">{tx.impact_label}: {s.financial_impact.method}. {L("This is an estimate, not an accounting loss.", "यह एक अनुमान है, हिसाब-किताब का असली नुकसान नहीं।")}</div>
          </div>
          <div className="section">
            <h3>{L("What it may mean", "इसका क्या मतलब हो सकता है")}</h3>
            <p lang={textLang}>{tx.interpretation}</p>
          </div>
          <div className="section">
            <h3>{L("Why Tremor flagged it", "Tremor ने इसे क्यों चुना")}</h3>
            <div className="row" style={{ marginBottom: 8 }}><StrengthBadge v={s.evidence_strength} /></div>
            <dl className="kv">
              <dt>{L("How unusual (robust z-score vs other products)", "कितना असामान्य (बाकी प्रोडक्ट के मुकाबले robust z-score)")}</dt><dd>{s.ranking.anomaly_score}</dd>
              <dt>{L("Money at stake", "दाँव पर रकम")}</dt><dd>{inr(s.ranking.impact_inr)}</dd>
              <dt>{L("Extraction confidence", "बिल पढ़ने का भरोसा")}</dt><dd>{Math.round(comps.extraction_confidence * 100)}%</dd>
              <dt>{L("Product match confidence", "प्रोडक्ट मिलान का भरोसा")}</dt><dd>{Math.round(comps.match_confidence * 100)}%</dd>
              <dt>{L("Sources agreeing", "मेल खाते स्रोत")}</dt><dd>{comps.source_corroboration === 1 ? L("CSV and invoice", "CSV और बिल") : L("One source", "एक स्रोत")}</dd>
              <dt>{L("Data completeness", "डेटा कितना पूरा है")}</dt><dd>{Math.round(comps.data_completeness * 100)}%</dd>
            </dl>
          </div>
          <div className="section">
            <h3>{L("Alternative explanations checked", "जाँची गई दूसरी वजहें")}</h3>
            {s.rejected_explanations.length === 0 ? <p className="muted">{L("None could be ruled out with the available data.", "मौजूद डेटा से किसी वजह को खारिज नहीं किया जा सका।")}</p> : (
              <ul style={{ margin: 0, paddingLeft: 18 }} className="stack">
                {s.rejected_explanations.map((a) => (
                  <li key={a.name}>
                    <strong>{L("Ruled out", "खारिज")}: {a.name}.</strong> <span className="muted">{a.reason}</span>{" "}
                    {a.evidence_ids.map((id) => evidence[id] && (
                      <button key={id} className="btn btn-sm" style={{ marginLeft: 4 }} onClick={() => setActive(id)}>{evidence[id].source_type === "calendar" ? L("See calendar", "कैलेंडर देखें") : L("See rows", "पंक्तियाँ देखें")}</button>
                    ))}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="section">
            <h3>{L("Recommended check", "सुझाई गई जाँच")}</h3>
            <p style={{ fontWeight: 600 }} lang={textLang}>{tx.next_check}</p>
          </div>
          <div className="section">
            <h3>{L("Limitations", "सीमाएँ")}</h3>
            <ul style={{ margin: 0, paddingLeft: 18 }} className="muted" lang={textLang}>{tx.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            {hi && <p className="tr-note" style={{ marginTop: 8 }}>हिंदी टेक्स्ट उन्हीं जाँचे गए आँकड़ों से बना है जिनसे अंग्रेज़ी टेक्स्ट बना है। कुछ तकनीकी विवरण अंग्रेज़ी में रहते हैं।</p>}
          </div>
          <div className="section">
            <h3>{L("Your decision", "आपका फ़ैसला")}</h3>
            <ReviewControls signalId={s.signal_id} reviews={data.reviews} onSaved={load} />
          </div>
        </div>

        <div className="stack" style={{ position: "sticky", top: 64 }}>
          <section className="card card-pad" aria-labelledby="ev-h">
            <h2 id="ev-h" style={{ marginBottom: 10 }}>{L("Evidence", "सबूत")}</h2>
            <div className="ev-list">{s.evidence_ids.map((id) => <EvButton key={id} id={id} />)}</div>
          </section>
          <section className="card card-pad" aria-live="polite">
            {active ? <EvidenceViewer evidenceId={active} /> : <p className="muted">{L("Select evidence to open it.", "खोलने के लिए कोई सबूत चुनें।")}</p>}
          </section>
          <p className="faint">Detector {s.model_metadata.detector_version} · prompt {s.model_metadata.prompt_version} · model {s.model_metadata.model_name} · extraction {s.model_metadata.extraction_method}</p>
        </div>
      </div>
    </main>
  );
}
