"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Loading, PageHead, SeverityBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, inr, titleCase } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";
import type { Review } from "@/lib/types";

export default function ReviewsPage() {
  const { run, loading } = useRun();
  const { lang } = useLang();
  const L = (en: string, hi: string) => (lang === "hi" ? hi : en);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!run) return;
    api.reviews(run.run_id).then((r) => setReviews(r.reviews)).catch((e) => setErr(e.message));
  }, [run?.run_id, run]);

  if (loading) return <main className="page"><Loading /></main>;
  const counts = (reviews ?? []).reduce<Record<string, number>>((a, r) => ({ ...a, [r.outcome]: (a[r.outcome] ?? 0) + 1 }), {});

  return (
    <main className="page">
      <PageHead title={L("Reviews", "समीक्षा")} desc={L("Your decisions on signals in the current run. Reviews record judgement only; they never change source data or trigger an action.", "इस जाँच के संकेतों पर आपके फ़ैसले। समीक्षा सिर्फ़ आपकी राय दर्ज करती है; यह डेटा नहीं बदलती और कोई कदम नहीं उठाती।")} />
      {err && <div className="alert alert-error">{err}</div>}
      {!run ? <div className="card empty"><h3>{L("No analysis yet", "अभी कोई जाँच नहीं")}</h3><p><Link href="/dashboard">{L("Start from the Overview", "डैशबोर्ड से शुरू करें")}</Link>.</p></div>
        : !reviews ? <Loading label="Loading reviews" /> : (
          <div className="stack">
            <div className="row">
              {(["confirmed", "dismissed", "unresolved"] as const).map((o) => (
                <span key={o} className="badge badge-neutral">{titleCase(o)}: {counts[o] ?? 0}</span>
              ))}
            </div>
            <section className="card">
              {reviews.length === 0 ? (
                <div className="empty"><h3>{L("No reviews yet", "अभी कोई समीक्षा नहीं")}</h3><p>Open a <Link href="/signals">signal</Link> and confirm, dismiss or leave it unresolved.</p></div>
              ) : (
                <div className="table-wrap" style={{ maxHeight: "none" }}>
                  <table>
                    <thead><tr><th>When</th><th>Signal</th><th>Severity</th><th className="r">Amount</th><th>Decision</th><th>Reason</th></tr></thead>
                    <tbody>
                      {reviews.map((r) => (
                        <tr key={r.review_id}>
                          <td>{dateTime(r.created_at)}</td>
                          <td><Link href={`/signals/${r.signal_id}`}>{r.signal_title}</Link></td>
                          <td>{r.severity && <SeverityBadge s={r.severity} />}</td>
                          <td className="r">{inr(r.amount)}</td>
                          <td><strong>{r.outcome === "confirmed" ? "Confirmed for investigation" : titleCase(r.outcome)}</strong></td>
                          <td className="muted">{r.reason || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
    </main>
  );
}
