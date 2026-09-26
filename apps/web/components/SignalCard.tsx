"use client";

import Link from "next/link";
import { inr, titleCase } from "@/lib/format";
import type { SignalSummary } from "@/lib/types";
import { SeverityBadge, StatusBadge, StrengthBadge } from "./ui";

export default function SignalCard({ s }: { s: SignalSummary }) {
  return (
    <Link href={`/signals/${s.signal_id}`} className="signal-card">
      <div>
        <div className="row" style={{ marginBottom: 6 }}>
          <SeverityBadge s={s.severity} />
          <span className="badge badge-neutral">{titleCase(s.signal_type)}</span>
          <StrengthBadge v={s.evidence_strength} />
          <StatusBadge s={s.status} />
        </div>
        <div className="signal-title">{s.title}</div>
        <div className="signal-obs">{s.observation}</div>
      </div>
      <div className="impact">
        <div className="impact-amt">{inr(s.financial_impact.amount)}</div>
        <div className="faint">{s.financial_impact.label}</div>
      </div>
    </Link>
  );
}
