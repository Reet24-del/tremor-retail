"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { type Key, LangToggle, useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";
import { dateTime } from "@/lib/format";

const NAV: { href: string; key: Key }[] = [
  { href: "/dashboard", key: "nav.overview" },
  { href: "/sources", key: "nav.sources" },
  { href: "/signals", key: "nav.signals" },
  { href: "/reviews", key: "nav.reviews" },
];

export function Logo({ color = "#b8664b" }: { color?: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12h4l3-7 4 14 3-7h6" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <Link href="/" className="wordmark" aria-label="Tremor Retail home">
      <Logo />
      <span><b>TREMOR</b><small>RETAIL</small></span>
    </Link>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { run, apiError } = useRun();
  const { t } = useLang();
  const [open, setOpen] = useState(false);

  // The landing page is a full-bleed editorial page with its own navigation.
  if (path === "/") return <>{children}</>;

  const isActive = (href: string) => path.startsWith(href);
  const sigCount = run?.summary?.signals;
  const stage = (s: string | null | undefined) => (s ? t(`stage.${s}` as Key) : "");

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <div className="brand-mark"><Logo /></div>
          <Link href="/" style={{ color: "inherit" }}>
            <div className="brand-name">TREMOR</div>
            <div className="brand-sub">RETAIL</div>
          </Link>
        </div>
        <div className="brand-tag" style={{ padding: "0 8px", marginTop: -10 }}>{t("shell.tagline")}</div>
        <div className="store">
          <div className="faint">{t("shell.activeStore")}</div>
          <div className="store-name">{run?.store_name || t("shell.noStore")}</div>
          {run?.mode === "demo" && <span className="badge badge-synthetic" style={{ marginTop: 6 }}>{t("shell.synthetic")}</span>}
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={isActive(n.href) ? "active" : ""} onClick={() => setOpen(false)}
              aria-current={isActive(n.href) ? "page" : undefined}>
              {t(n.key)}
              {n.href === "/signals" && typeof sigCount === "number" && <span className="count">{sigCount}</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span>{t("shell.foot")}</span>
          <span>Team Three Musketeers</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <button className="btn btn-sm menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={t("shell.menu")}>{t("shell.menu")}</button>
            <div className="run-status" role="status" aria-live="polite">
              {apiError ? (
                <span className="badge badge-high">{t("shell.apiDown")}</span>
              ) : !run ? (
                <span>{t("shell.noRun")}</span>
              ) : run.status === "running" ? (
                <><span className="badge badge-accent">{t("shell.analysing")}</span>{stage(run.current_stage) || "…"}…</>
              ) : run.status === "failed" ? (
                <><span className="badge badge-high">{t("shell.failed")}</span>{t("shell.failedAt")} {stage(run.failed_stage)}</>
              ) : (
                <><span className="badge badge-ok">{t("shell.complete")}</span>{t("shell.lastRun")} {dateTime(run.completed_at)}</>
              )}
            </div>
          </div>
          <div className="row">
            {run?.mode === "demo" && <span className="badge badge-synthetic">{t("shell.synthetic")}</span>}
            <LangToggle />
          </div>
        </header>
        {apiError && <div className="page" style={{ paddingBottom: 0 }}><div className="alert alert-error">{apiError}</div></div>}
        {children}
      </div>
    </div>
  );
}
