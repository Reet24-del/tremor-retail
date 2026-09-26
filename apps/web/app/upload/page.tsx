"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { PageHead } from "@/components/ui";
import { api, ApiError, sampleCsvUrl } from "@/lib/api";
import { date, num } from "@/lib/format";
import { useRun } from "@/lib/run-context";

type CsvCheck = { ok: boolean; errors: string[]; warnings: string[]; summary: Record<string, unknown> };

function Drop({ accept, multiple, label, hint, onFiles }: { accept: string; multiple?: boolean; label: string; hint: string; onFiles: (f: File[]) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div className={`dropzone ${drag ? "drag" : ""}`} role="button" tabIndex={0} aria-label={label}
      onClick={() => ref.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && ref.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(Array.from(e.dataTransfer.files)); }}>
      <strong>{label}</strong>
      <div className="faint">{hint}</div>
      <input ref={ref} type="file" hidden accept={accept} multiple={multiple} onChange={(e) => onFiles(Array.from(e.target.files ?? []))} />
    </div>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const { setRunId } = useRun();
  const [csv, setCsv] = useState<File | null>(null);
  const [check, setCheck] = useState<CsvCheck | null>(null);
  const [pdfs, setPdfs] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const pickCsv = async (files: File[]) => {
    const f = files[0];
    if (!f) return;
    setCsv(f);
    setCheck(null);
    const form = new FormData();
    form.append("sales_csv", f);
    try {
      setCheck(await api.validateCsv(form));
    } catch (e) {
      setCheck({ ok: false, errors: [e instanceof Error ? e.message : "Validation failed"], warnings: [], summary: {} });
    }
  };

  const addPdfs = (files: File[]) => {
    const rejected = files.filter((f) => !f.name.toLowerCase().endsWith(".pdf") || f.size > 10 * 1024 * 1024);
    setErrors(rejected.map((f) => `${f.name}: must be a PDF under 10 MB`));
    const ok = files.filter((f) => !rejected.includes(f));
    setPdfs((prev) => [...prev.filter((p) => !ok.some((o) => o.name === p.name)), ...ok]);
  };

  const start = async () => {
    if (!csv) return;
    setBusy(true);
    setErrors([]);
    const form = new FormData();
    form.append("sales_csv", csv);
    pdfs.forEach((p) => form.append("invoices", p));
    try {
      const r = await api.startUpload(form);
      setRunId(r.run_id);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      if (e instanceof ApiError && e.detail && typeof e.detail === "object" && "errors" in (e.detail as object)) {
        setErrors((e.detail as { errors: { file: string | null; error: string }[] }).errors.map((x) => (x.file ? `${x.file}: ` : "") + x.error));
      } else {
        setErrors([e instanceof Error ? e.message : "Upload failed"]);
      }
    } finally {
      setBusy(false);
    }
  };

  const canStart = !!csv && check?.ok && !busy;

  return (
    <main className="page">
      <PageHead title="Upload my files" crumbs={<><Link href="/">Overview</Link> / Upload</>}
        desc="Your sales and stock CSV is enough to find stock that does not add up. Supplier bills are optional and unlock margin checks. Files are only used for this analysis; Tremor never changes your records." />
      <div className="grid grid-2">
        <section className="card card-pad stack">
          <div className="row between"><h2>1. Sales and stock CSV</h2><a href={sampleCsvUrl} download>Download example CSV</a></div>
          <p className="faint">Required columns: transaction_id, transaction_date, product_id, product_name, quantity_sold, unit_selling_price, opening_stock, closing_stock. Optional: recorded_damage, recorded_returns.</p>
          <Drop accept=".csv,text/csv" label={csv ? `Selected: ${csv.name}` : "Choose or drop a CSV"} hint="CSV, up to 10 MB" onFiles={pickCsv} />
          {csv && !check && <p className="faint" role="status">Checking columns and rows…</p>}
          {check && check.ok && (
            <div className="alert alert-info">
              <strong>Looks good.</strong> {num(Number(check.summary.row_count))} rows · {String(check.summary.product_count)} products · {date(String(check.summary.date_from))} to {date(String(check.summary.date_to))} · INR
              <div className="faint" style={{ marginTop: 4 }}>Columns: {(check.summary.columns as string[] | undefined)?.join(", ")}</div>
            </div>
          )}
          {check && check.errors.length > 0 && (
            <div className="alert alert-error"><strong>Fix these before continuing:</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{check.errors.map((e) => <li key={e}>{e}</li>)}</ul></div>
          )}
          {check && check.warnings.length > 0 && <div className="alert alert-warn">{check.warnings.join(" · ")}</div>}
        </section>

        <section className="card card-pad stack">
          <h2>2. Supplier bills <span className="faint" style={{ fontWeight: 400 }}>(optional)</span></h2>
          <p className="faint">Add bills to check margins. Bills from at least two dates let Tremor compare an older cost with the latest one. You can also add them later. Digital PDFs work best.</p>
          <Drop accept="application/pdf,.pdf" multiple label="Choose or drop invoice PDFs" hint="PDF, up to 10 MB each" onFiles={addPdfs} />
          {pdfs.length > 0 && (
            <ul className="file-list">
              {pdfs.map((p) => (
                <li key={p.name}><span>{p.name} <span className="faint">{(p.size / 1024).toFixed(0)} KB</span></span>
                  <button className="btn btn-sm" onClick={() => setPdfs(pdfs.filter((x) => x !== p))} aria-label={`Remove ${p.name}`}>Remove</button></li>
              ))}
            </ul>
          )}
          {pdfs.length === 0 && <p className="faint">No bills: Tremor will check stock only and ask for bills if it needs them.</p>}
          {pdfs.length === 1 && <div className="alert alert-warn">One bill gives no earlier cost to compare with. Add another from a different date to check margins.</div>}
        </section>
      </div>
      {errors.length > 0 && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      <div className="row" style={{ marginTop: 16 }}>
        <button className="btn btn-primary btn-lg" disabled={!canStart} onClick={start}>{busy ? "Uploading…" : pdfs.length ? "Start analysis" : "Check stock now"}</button>
        <span className="faint">No automatic action will happen. You review every finding.</span>
      </div>
    </main>
  );
}
