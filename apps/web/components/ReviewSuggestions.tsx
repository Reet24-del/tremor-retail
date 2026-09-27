"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SeverityBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { signalText, useLang } from "@/lib/i18n";
import type { Review, SignalSummary } from "@/lib/types";

type Suggestion = { outcome: Review["outcome"]; reason: string };

/**
 * Tremor's suggested review for each open signal. It is advice only: the owner accepts it with one
 * click or decides differently. Built from the signal's own evidence strength, severity and status,
 * so it never introduces a number that is not already on the signal.
 */
export function suggest(s: SignalSummary, lang: "en" | "hi"): Suggestion {
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);
  const amt = inr(s.financial_impact.amount);
  if (s.status === "needs_data") {
    return { outcome: "unresolved", reason: L("Waiting for more data before a decision.", "फ़ैसले से पहले और डेटा चाहिए।") };
  }
  if (s.evidence_strength >= 0.85) {
    return {
      outcome: "confirmed",
      reason: s.signal_type === "margin_leakage"
        ? L(`Strong evidence from the bill and sales rows; ${amt} at stake. Check the supplier rate.`, `बिल और बिक्री की पंक्तियों से मज़बूत सबूत; ${amt} दाँव पर। सप्लायर रेट जाँचें।`)
        : L(`Strong evidence from the stock records; ${amt} at stake. Recount the shelf and storage.`, `स्टॉक रिकॉर्ड से मज़बूत सबूत; ${amt} दाँव पर। शेल्फ़ और गोदाम दोबारा गिनें।`),
    };
  }
  if (s.evidence_strength >= 0.65) {
    return { outcome: "confirmed", reason: L(`Reasonable evidence; ${amt} at stake. Worth a quick check.`, `ठीक-ठाक सबूत; ${amt} दाँव पर। एक बार जाँच लें।`) };
  }
  return { outcome: "unresolved", reason: L("Evidence is limited. Add more bills or days of data first.", "सबूत कम है। पहले और बिल या दिनों का डेटा जोड़ें।") };
}

export default function ReviewSuggestions({ runId, reviewed, onSaved }: { runId: string; reviewed: Set<string>; onSaved: () => void }) {
  const { lang } = useLang();
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);
  const [signals, setSignals] = useState<SignalSummary[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.signals(runId).then((r) => setSignals(r.signals)).catch((e) => setErr(e.message));
  }, [runId]);

  const pending = (signals ?? []).filter((s) => !reviewed.has(s.signal_id) && s.status !== "dismissed" && s.status !== "confirmed");
  if (!signals || pending.length === 0) return err ? <div className="alert alert-error">{err}</div> : null;

  const accept = async (s: SignalSummary) => {
    const sug = suggest(s, lang);
    setBusy(s.signal_id);
    setErr(null);
    try {
      await api.review(s.signal_id, sug.outcome, `${L("Accepted Tremor suggestion", "Tremor का सुझाव माना")}: ${sug.reason}`);
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(null);
    }
  };

  const label = (o: Review["outcome"]) =>
    o === "confirmed" ? L("Confirm for investigation", "जाँच के लिए पक्का करें") : o === "dismissed" ? L("Dismiss", "खारिज करें") : L("Leave unresolved", "अनसुलझा छोड़ें");

  return (
    <section className="card" aria-labelledby="sug-h">
      <div className="card-head">
        <div>
          <h2 id="sug-h">{L("Suggested reviews", "सुझाई गई समीक्षा")}</h2>
          <div className="faint">{L("Tremor's suggestion for each open signal, based on its evidence. You decide.", "हर खुले संकेत के लिए Tremor का सुझाव, उसके सबूत के आधार पर। फ़ैसला आपका है।")}</div>
        </div>
        <span className="badge badge-neutral">{pending.length}</span>
      </div>
      {err && <div className="alert alert-error" style={{ margin: 12 }}>{err}</div>}
      {pending.map((s) => {
        const sug = suggest(s, lang);
        const tx = signalText(s, lang);
        return (
          <div key={s.signal_id} className="section row between" style={{ alignItems: "flex-start" }}>
            <div style={{ flex: "1 1 420px", minWidth: 0 }}>
              <div className="row" style={{ marginBottom: 6 }}>
                <SeverityBadge s={s.severity} />
                <span className={`badge ${sug.outcome === "confirmed" ? "badge-accent" : "badge-neutral"}`}>{L("Suggested", "सुझाव")}: {label(sug.outcome)}</span>
              </div>
              <Link href={`/signals/${s.signal_id}`}><strong>{tx.title}</strong></Link>
              <p className="muted" style={{ marginTop: 4 }}>{sug.reason}</p>
            </div>
            <div className="row">
              <button className="btn btn-primary btn-sm" disabled={busy === s.signal_id} onClick={() => accept(s)}>
                {busy === s.signal_id ? L("Saving…", "सेव हो रहा है…") : L("Accept suggestion", "सुझाव मानें")}
              </button>
              <Link className="btn btn-sm" href={`/signals/${s.signal_id}`}>{L("Decide myself", "खुद तय करें")}</Link>
            </div>
          </div>
        );
      })}
    </section>
  );
}
