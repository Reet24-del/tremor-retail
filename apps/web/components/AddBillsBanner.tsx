"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";

/**
 * Shown only when the current run could not check margins: supplier bills are optional,
 * so Tremor asks for them exactly when a cost-based check needs them.
 */
export default function AddBillsBanner() {
  const { run, setRunId } = useRun();
  const router = useRouter();
  const { t } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const check = run?.summary?.margin_check;
  if (!run || run.status !== "completed" || run.mode === "demo" || !check || check === "done") return null;

  const upload = async (files: File[]) => {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setErr(t("bills.choosePdf"));
      return;
    }
    setBusy(true);
    setErr(null);
    const form = new FormData();
    pdfs.forEach((p) => form.append("invoices", p));
    try {
      const r = await api.addInvoices(run.run_id, form);
      setRunId(r.run_id);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      if (e instanceof ApiError && e.detail && typeof e.detail === "object" && "errors" in (e.detail as object)) {
        setErr((e.detail as { errors: { error: string }[] }).errors.map((x) => x.error).join(" · "));
      } else {
        setErr(e instanceof Error ? e.message : "Could not add the bills");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="alert alert-info" style={{ marginBottom: 16 }} aria-live="polite">
      <div className="row between">
        <div style={{ maxWidth: 680 }}>
          <strong>
            {check === "skipped_no_bills" ? t("bills.noBillsH") : t("bills.moreH")}
          </strong>{" "}
          {check === "skipped_no_bills"
            ? t("bills.noBillsP")
            : t("bills.moreP")}
        </div>
        <button className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}>
          {busy ? t("bills.adding") : t("bills.add")}
        </button>
        <input ref={input} type="file" hidden multiple accept="application/pdf,.pdf"
          onChange={(e) => upload(Array.from(e.target.files ?? []))} />
      </div>
      {err && <div className="alert alert-error" style={{ marginTop: 8 }}>{err}</div>}
    </section>
  );
}
