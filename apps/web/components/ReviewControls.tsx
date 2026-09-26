"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { dateTime, titleCase } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import type { Review } from "@/lib/types";

const DISMISS_REASONS = ["Expected promotion", "Damaged stock already known", "Incorrect product match", "Data error"];

export default function ReviewControls({ signalId, reviews, onSaved }: { signalId: string; reviews: Review[]; onSaved: () => void }) {
  const [outcome, setOutcome] = useState<Review["outcome"]>("confirmed");
  const { lang } = useLang();
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const needsReason = outcome !== "unresolved";

  const save = async () => {
    if (needsReason && reason.trim().length < 3) {
      setErr("Add a short reason so the decision is recorded.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api.review(signalId, outcome, reason);
      setReason("");
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save the review");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack review-box">
      <div className="seg" role="group" aria-label="Review outcome">
        {(["confirmed", "dismissed", "unresolved"] as const).map((o) => (
          <button key={o} aria-pressed={outcome === o} onClick={() => setOutcome(o)}>
            {o === "confirmed" ? L("Confirm for investigation", "जाँच के लिए पक्का करें") : o === "dismissed" ? L("Dismiss", "खारिज करें") : L("Leave unresolved", "अभी अनसुलझा छोड़ें")}
          </button>
        ))}
      </div>
      {outcome === "dismissed" && (
        <div className="row">
          {DISMISS_REASONS.map((r) => <button key={r} className="btn btn-sm" onClick={() => setReason(r)}>{r}</button>)}
        </div>
      )}
      <div className="field">
        <label htmlFor="reason">{L("Reason", "कारण")} {needsReason ? L("(required)", "(ज़रूरी)") : L("(optional)", "(वैकल्पिक)")}</label>
        <textarea id="reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder={outcome === "confirmed" ? L("e.g. Supplier rate checked with Shakti Wholesale", "जैसे: Shakti Wholesale से सप्लायर रेट पक्का किया") : L("Why?", "क्यों?")} />
      </div>
      {err && <div className="alert alert-error">{err}</div>}
      <div className="row between">
        <span className="faint">{L("Confirm means “worth investigating”, not proven loss. Reviews never change your records.", "पक्का करने का मतलब है “जाँच लायक”, नुकसान साबित होना नहीं। समीक्षा आपके रिकॉर्ड कभी नहीं बदलती।")}</span>
        <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? L("Saving…", "सेव हो रहा है…") : L("Save review", "समीक्षा सेव करें")}</button>
      </div>
      {reviews.length > 0 && (
        <div>
          <div className="faint" style={{ marginBottom: 4 }}>History</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {reviews.map((r) => (
              <li key={r.review_id}><strong>{titleCase(r.outcome)}</strong> · {dateTime(r.created_at)}{r.reason ? ` · ${r.reason}` : ""}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
