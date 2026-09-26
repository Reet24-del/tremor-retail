"use client";

import Link from "next/link";
import { inr } from "@/lib/format";
import { type Key, signalText, useLang } from "@/lib/i18n";
import type { SignalSummary } from "@/lib/types";
import { SeverityBadge, StatusBadge, StrengthBadge } from "./ui";

export default function SignalCard({ s }: { s: SignalSummary }) {
  const { lang, t } = useLang();
  const tx = signalText(s, lang);
  return (
    <Link href={`/signals/${s.signal_id}`} className="signal-card">
      <div>
        <div className="row" style={{ marginBottom: 6 }}>
          <SeverityBadge s={s.severity} />
          <span className="badge badge-neutral">{t(`type.${s.signal_type}` as Key)}</span>
          <StrengthBadge v={s.evidence_strength} />
          <StatusBadge s={s.status} />
        </div>
        <div className="signal-title" lang={tx.translated ? lang : "en"}>{tx.title}</div>
        <div className="signal-obs" lang={tx.translated ? lang : "en"}>{tx.observation}</div>
      </div>
      <div className="impact">
        <div className="impact-amt">{inr(s.financial_impact.amount)}</div>
        <div className="faint">{tx.impactLabel}</div>
      </div>
    </Link>
  );
}
