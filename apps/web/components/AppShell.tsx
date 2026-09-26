"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useRun } from "@/lib/run-context";
import { dateTime } from "@/lib/format";
import { STAGE_LABELS } from "@/lib/types";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/sources", label: "Data sources" },
  { href: "/signals", label: "Signals" },
  { href: "/reviews", label: "Reviews" },
];

export function Logo() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 14h4l2-3 2 3h2l2.5-10L17 20l2-6h3" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round"
        strokeLinejoin="round" />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { run, apiError } = useRun();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const sigCount = run?.summary?.signals;

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <div className="brand-mark"><Logo /></div>
          <div>
            <div className="brand-name">Tremor Retail</div>
            <div className="brand-sub">Profit leakage intelligence</div>
          </div>
        </div>
        <div className="store">
          <div className="faint">Active store</div>
          <div className="store-name">{run?.store_name || "No store analysed yet"}</div>
          {run?.mode === "demo" && <span className="badge badge-synthetic" style={{ marginTop: 6 }}>Synthetic demo data</span>}
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={isActive(n.href) ? "active" : ""} onClick={() => setOpen(false)}
              aria-current={isActive(n.href) ? "page" : undefined}>
              {n.label}
              {n.href === "/signals" && typeof sigCount === "number" && <span className="count">{sigCount}</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span>Tremor gives investigation leads. It never changes prices, credit or stock on its own.</span>
          <span>Team Three Musketeers</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <button className="btn btn-sm menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Open menu">Menu</button>
            <div className="run-status" role="status" aria-live="polite">
              {apiError ? (
                <span className="badge badge-high">API unreachable</span>
              ) : !run ? (
                <span>No analysis run yet</span>
              ) : run.status === "running" ? (
                <><span className="badge badge-accent">Analysing</span>{STAGE_LABELS[run.current_stage || ""] || "Starting"}…</>
              ) : run.status === "failed" ? (
                <><span className="badge badge-high">Run failed</span>at {STAGE_LABELS[run.failed_stage || ""] || "unknown stage"}</>
              ) : (
                <><span className="badge badge-ok">Analysis complete</span>Last run {dateTime(run.completed_at)}</>
              )}
            </div>
          </div>
          {run?.mode === "demo" && <span className="badge badge-synthetic">Synthetic demo data</span>}
        </header>
        {apiError && <div className="page" style={{ paddingBottom: 0 }}><div className="alert alert-error">{apiError}</div></div>}
        {children}
      </div>
    </div>
  );
}
