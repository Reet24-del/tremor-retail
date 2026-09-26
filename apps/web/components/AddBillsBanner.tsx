"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useRun } from "@/lib/run-context";

/**
 * Shown only when the current run could not check margins: supplier bills are optional,
 * so Tremor asks for them exactly when a cost-based check needs them.
 */
export default function AddBillsBanner() {
  const { run, setRunId } = useRun();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const check = run?.summary?.margin_check;
  if (!run || run.status !== "completed" || run.mode === "demo" || !check || check === "done") return null;

  const upload = async (files: File[]) => {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setErr("Choose supplier bill PDFs.");
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
            {check === "skipped_no_bills" ? "Margin checks need supplier bills." : "Add one more supplier bill to compare costs."}
          </strong>{" "}
          {check === "skipped_no_bills"
            ? "Stock was checked from your sales file alone. To see whether rising supplier costs are eating into your margin, add the bills from your suppliers."
            : "Tremor needs bills from at least two dates to see whether a supplier raised a price."}
        </div>
        <button className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}>
          {busy ? "Adding bills…" : "Add supplier bills"}
        </button>
        <input ref={input} type="file" hidden multiple accept="application/pdf,.pdf"
          onChange={(e) => upload(Array.from(e.target.files ?? []))} />
      </div>
      {err && <div className="alert alert-error" style={{ marginTop: 8 }}>{err}</div>}
    </section>
  );
}
