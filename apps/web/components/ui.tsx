"use client";

import { strengthLabel, titleCase } from "@/lib/format";
import type { Severity, SignalStatus } from "@/lib/types";
import { STAGES } from "@/lib/types";
import { type Key, useLang } from "@/lib/i18n";

export function SeverityBadge({ s }: { s: Severity }) {
  const { t } = useLang();
  const icon = s === "high" ? "▲" : s === "medium" ? "■" : "●";
  return <span className={`badge badge-${s}`}><span aria-hidden="true">{icon}</span>{t(`sev.${s}` as Key)}</span>;
}

export function StatusBadge({ s }: { s: SignalStatus }) {
  const cls = s === "confirmed" ? "badge-accent" : s === "dismissed" ? "badge-neutral" : s === "new" ? "badge-accent" : "badge-neutral";
  const { t } = useLang();
  const label = t(`status.${s}` as Key) || titleCase(s);
  return <span className={`badge ${cls}`}>{label}</span>;
}

const STRENGTH_HI: Record<string, string> = {
  "Strong evidence": "मज़बूत सबूत",
  "Moderate evidence": "ठीक-ठाक सबूत",
  "Limited evidence": "कम सबूत",
};
export function StrengthBadge({ v }: { v: number }) {
  const { lang } = useLang();
  const label = strengthLabel(v);
  return <span className="badge badge-neutral" title={`Evidence strength ${Math.round(v * 100)}% (how well the data supports the observation, not a probability of loss)`}>{lang === "hi" ? STRENGTH_HI[label] : label}</span>;
}

const SRC: Record<string, [string, string]> = {
  sales_csv: ["src-csv", "CSV rows"],
  invoice_pdf: ["src-pdf", "Invoice"],
  calculation: ["src-calc", "Calculated"],
  calendar: ["src-cal", "Calendar"],
  ai: ["src-ai", "AI wording"],
  template: ["src-calc", "Template wording"],
};
export function SourceBadge({ t }: { t: string }) {
  const [cls, label] = SRC[t] || ["", t];
  return <span className={`src ${cls}`}>{label}</span>;
}

export function Skeleton({ h = 14, w = "100%" }: { h?: number; w?: string | number }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="stack" role="status" aria-live="polite">
      <span className="faint">{label}…</span>
      <Skeleton h={18} w="40%" /><Skeleton h={60} /><Skeleton h={60} />
    </div>
  );
}

export function ProcessingTimeline({ current, completed, failed }: { current: string | null; completed: string[]; failed?: string | null }) {
  const { t } = useLang();
  return (
    <ol className="timeline" aria-label="Processing stages">
      {STAGES.map((s, i) => {
        const done = completed.includes(s);
        const isFailed = failed === s;
        const active = current === s && !isFailed;
        return (
          <li key={s}>
            <span className={`dot ${done ? "done" : ""} ${active ? "active" : ""} ${isFailed ? "failed" : ""}`} aria-hidden="true">
              {done ? "✓" : isFailed ? "!" : i + 1}
            </span>
            <span style={{ color: done || active ? "var(--text)" : "var(--text-3)", fontWeight: active ? 600 : 400 }}>
              {t(`stage.${s}` as Key)}
              <span className="faint"> {t(done ? "stage.done" : isFailed ? "stage.failed" : active ? "stage.active" : "stage.waiting")}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function PageHead({ title, desc, actions, crumbs }: { title: string; desc?: string; actions?: React.ReactNode; crumbs?: React.ReactNode }) {
  return (
    <>
      {crumbs && <div className="crumbs">{crumbs}</div>}
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          {desc && <p>{desc}</p>}
        </div>
        {actions && <div className="row">{actions}</div>}
      </div>
    </>
  );
}
