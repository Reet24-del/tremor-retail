"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { PageHead } from "@/components/ui";
import { api, ApiError, sampleCsvUrl } from "@/lib/api";
import { date, num } from "@/lib/format";
import { useLang } from "@/lib/i18n";
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
  const { t } = useLang();
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
    setErrors(rejected.map((f) => t("up.pdfBad", { f: f.name })));
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
      <PageHead title={t("up.title")} crumbs={<><Link href="/dashboard">{t("nav.overview")}</Link> / {t("up.title")}</>}
        desc={t("up.desc")} />
      <div className="grid grid-2">
        <section className="card card-pad stack">
          <div className="row between"><h2>{t("up.csvH")}</h2><a href={sampleCsvUrl} download>{t("up.example")}</a></div>
          <p className="faint">{t("up.columns")}</p>
          <Drop accept=".csv,text/csv" label={csv ? t("up.selected", { f: csv.name }) : t("up.chooseCsv")} hint={t("up.csvHint")} onFiles={pickCsv} />
          {csv && !check && <p className="faint" role="status">{t("up.checking")}</p>}
          {check && check.ok && (
            <div className="alert alert-info">
              <strong>{t("up.good")}</strong> {t("up.rowsSummary", { r: num(Number(check.summary.row_count)), p: String(check.summary.product_count), a: date(String(check.summary.date_from)), b: date(String(check.summary.date_to)) })}
              <div className="faint" style={{ marginTop: 4 }}>{t("up.columnsFound")} {(check.summary.columns as string[] | undefined)?.join(", ")}</div>
            </div>
          )}
          {check && check.errors.length > 0 && (
            <div className="alert alert-error"><strong>{t("up.fix")}</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{check.errors.map((e) => <li key={e}>{e}</li>)}</ul></div>
          )}
          {check && check.warnings.length > 0 && <div className="alert alert-warn">{check.warnings.join(" · ")}</div>}
        </section>

        <section className="card card-pad stack">
          <h2>{t("up.billsH")} <span className="faint" style={{ fontWeight: 400 }}>{t("up.optional")}</span></h2>
          <p className="faint">{t("up.billsP")}</p>
          <Drop accept="application/pdf,.pdf" multiple label={t("up.choosePdf")} hint={t("up.pdfHint")} onFiles={addPdfs} />
          {pdfs.length > 0 && (
            <ul className="file-list">
              {pdfs.map((p) => (
                <li key={p.name}><span>{p.name} <span className="faint">{(p.size / 1024).toFixed(0)} KB</span></span>
                  <button className="btn btn-sm" onClick={() => setPdfs(pdfs.filter((x) => x !== p))} aria-label={`${t("up.remove")} ${p.name}`}>{t("up.remove")}</button></li>
              ))}
            </ul>
          )}
          {pdfs.length === 0 && <p className="faint">{t("up.noBills")}</p>}
          {pdfs.length === 1 && <div className="alert alert-warn">{t("up.oneBill")}</div>}
        </section>
      </div>
      {errors.length > 0 && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      <div className="row" style={{ marginTop: 16 }}>
        <button className="btn btn-primary btn-lg" disabled={!canStart} onClick={start}>{busy ? t("up.uploading") : pdfs.length ? t("up.start") : t("up.stockOnly")}</button>
        <span className="faint">{t("up.noAuto")}</span>
      </div>
    </main>
  );
}
