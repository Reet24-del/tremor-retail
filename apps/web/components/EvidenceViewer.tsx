"use client";

import { useEffect, useState } from "react";
import { api, imageUrl } from "@/lib/api";
import { date, inr, num, titleCase } from "@/lib/format";
import type { CsvRow, Evidence } from "@/lib/types";
import { Loading, SourceBadge } from "./ui";

function CsvTable({ rows, highlight }: { rows: CsvRow[]; highlight?: Set<number> }) {
  return (
    <div className="table-wrap">
      <table>
        <caption className="faint" style={{ textAlign: "left", padding: "0 0 6px" }}>Original CSV line numbers are shown in the first column.</caption>
        <thead>
          <tr><th>Line</th><th>Date</th><th className="r">Sold</th><th className="r">Price</th><th className="r">Opening</th>
            <th className="r">Closing</th><th className="r">Damage</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.source_row} className={highlight?.has(r.source_row) ? "hl" : ""}>
              <td className="mono">{r.source_row}</td><td>{date(r.transaction_date)}</td>
              <td className="r">{num(r.quantity_sold)}</td><td className="r">{inr(r.unit_selling_price)}</td>
              <td className="r">{num(r.opening_stock)}</td><td className="r">{num(r.closing_stock)}</td>
              <td className="r">{num(r.recorded_damage)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Kv({ obj }: { obj: Record<string, unknown> }) {
  return (
    <dl className="kv">
      {Object.entries(obj).filter(([, v]) => typeof v === "number" || typeof v === "string").map(([k, v]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt>{titleCase(k)}</dt>
          <dd>{typeof v === "number" ? num(v) : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function EvidenceViewer({ evidenceId }: { evidenceId: string }) {
  const [state, setState] = useState<{ id: string; ev?: Evidence; err?: string } | null>(null);

  useEffect(() => {
    let alive = true;
    api.evidence(evidenceId)
      .then((ev) => alive && setState({ id: evidenceId, ev }))
      .catch((e: Error) => alive && setState({ id: evidenceId, err: e.message }));
    return () => { alive = false; };
  }, [evidenceId]);
  const current = state?.id === evidenceId ? state : null;
  const ev = current?.ev ?? null;
  const err = current?.err ?? null;

  if (err) return <div className="alert alert-error">Evidence could not be opened: {err}</div>;
  if (!ev) return <Loading label="Opening evidence" />;

  const head = (
    <div className="row" style={{ marginBottom: 10 }}>
      <SourceBadge t={ev.source_type} /><strong>{ev.label}</strong>
    </div>
  );

  if (ev.source_type === "invoice_pdf") {
    const x = ev.excerpt as Record<string, unknown> & { match?: Record<string, unknown> };
    const loc = ev.locator as { page: number; source_text: string };
    const m = x.match as { product_name?: string; confidence?: number; method?: string; scores?: Record<string, number> } | undefined;
    return (
      <div className="stack">
        {head}
        <div className="faint">{String(x.supplier_name)} · invoice {String(x.invoice_number)} · {date(String(x.invoice_date))} · page {loc.page}</div>
        <div>
          <div className="faint" style={{ marginBottom: 4 }}>Extracted line (exact text from the PDF)</div>
          <div className="quote">{loc.source_text}</div>
        </div>
        <dl className="kv">
          <dt>Description</dt><dd>{String(x.raw_description)}</dd>
          <dt>Quantity</dt><dd>{num(Number(x.quantity))} {String(x.unit)}</dd>
          <dt>Unit cost</dt><dd>{inr(Number(x.unit_cost), 2)}</dd>
          <dt>Line total</dt><dd>{inr(Number(x.line_total), 2)}</dd>
          <dt>Extraction</dt><dd>{String(x.extraction_method)} · confidence {Math.round(Number(x.extraction_confidence) * 100)}%</dd>
          {m && <><dt>Matched to</dt><dd>{m.product_name} · {m.method} match {Math.round((m.confidence ?? 0) * 100)}%</dd></>}
        </dl>
        {ev.page_image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="page-img" src={imageUrl(ev.page_image_url)} alt={`Invoice ${String(x.invoice_number)} page ${loc.page} with the cited line highlighted`} />
        )}
      </div>
    );
  }
  if (ev.source_type === "sales_csv") {
    const ex = ev.excerpt as CsvRow[] | { rows: CsvRow[]; [k: string]: unknown };
    const rows = Array.isArray(ex) ? ex : ex.rows;
    const locRows = new Set<number>(((ev.locator as { rows?: number[] }).rows) ?? []);
    const calc = Array.isArray(ex) ? null : Object.fromEntries(Object.entries(ex).filter(([k]) => k !== "rows"));
    return (
      <div className="stack">
        {head}
        <div className="faint">{locRows.size} row{locRows.size === 1 ? "" : "s"} from the sales and stock CSV{rows.length < locRows.size ? ` (showing the last ${rows.length})` : ""}</div>
        <CsvTable rows={rows} highlight={Array.isArray(ex) ? undefined : locRows} />
        {calc && <div className="card card-pad"><div className="faint" style={{ marginBottom: 6 }}>Stock reconciliation</div><Kv obj={calc} /></div>}
      </div>
    );
  }
  if (ev.source_type === "calculation") {
    const c = ev.excerpt as Record<string, unknown>;
    const formulas = (c.formulas as string[]) || (c.formula ? [String(c.formula)] : []);
    return (
      <div className="stack">
        {head}
        <p className="faint">Calculated by code from the rows and invoice lines above. No AI model produces these numbers.</p>
        <Kv obj={c} />
        {formulas.map((f) => <div key={f} className="mono">{f}</div>)}
      </div>
    );
  }
  const promos = ev.excerpt as Array<Record<string, unknown>>;
  return (
    <div className="stack">
      {head}
      <table>
        <thead><tr><th>Promotion</th><th>From</th><th>To</th><th className="r">Price</th></tr></thead>
        <tbody>{promos.map((p, i) => (
          <tr key={i}><td>{String(p.label)}</td><td>{date(String(p.start))}</td><td>{date(String(p.end))}</td><td className="r">{inr(Number(p.price))}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
