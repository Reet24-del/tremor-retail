"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { dateTime, titleCase } from "@/lib/format";
import type { Review } from "@/lib/types";

const DISMISS_REASONS = ["Expected promotion", "Damaged stock already known", "Incorrect product match", "Data error"];

export default function ReviewControls({ signalId, reviews, onSaved }: { signalId: string; reviews: Review[]; onSaved: () => void }) {
  const [outcome, setOutcome] = useState<Review["outcome"]>("confirmed");
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
            {o === "confirmed" ? "Confirm for investigation" : o === "dismissed" ? "Dismiss" : "Leave unresolved"}
          </button>
        ))}
      </div>
      {outcome === "dismissed" && (
        <div className="row">
          {DISMISS_REASONS.map((r) => <button key={r} className="btn btn-sm" onClick={() => setReason(r)}>{r}</button>)}
        </div>
      )}
      <div className="field">
        <label htmlFor="reason">Reason {needsReason ? "(required)" : "(optional)"}</label>
        <textarea id="reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder={outcome === "confirmed" ? "e.g. Supplier rate checked with Shakti Wholesale" : "Why?"} />
      </div>
      {err && <div className="alert alert-error">{err}</div>}
      <div className="row between">
        <span className="faint">Confirm means “worth investigating”, not proven loss. Reviews never change your records.</span>
        <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save review"}</button>
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
