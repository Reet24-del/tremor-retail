import type {
  EvalReport, Evidence, Review, RunStatus, RunStarted, InvoiceCorrection, SourcesResponse, SignalsResponse, SignalDetail, CsvValidationResponse,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(0, `Cannot reach the Tremor API at ${API_URL}. Is the backend running?`, null);
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* not json */
    }
    const info = detail as { message?: string; issues?: { message: string }[] } | null;
    const msg = typeof detail === "string" ? detail : info?.issues?.[0]?.message ?? info?.message ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, msg, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; llm_enabled: boolean; model: string }>("/api/health"),
  startDemo: () => req<RunStarted>("/api/runs/demo", { method: "POST" }),
  startUpload: (form: FormData) => req<RunStarted>("/api/runs", { method: "POST", body: form }),
  validateCsv: (form: FormData) =>
    req<CsvValidationResponse>(
      "/api/uploads/validate-csv", { method: "POST", body: form }),
  run: (id: string) => req<RunStatus>(`/api/runs/${id}`),
  signals: (id: string) =>
    req<SignalsResponse>(
      `/api/runs/${id}/signals`),
  signal: (id: string) =>
    req<SignalDetail>(`/api/signals/${id}`),
  evidence: (id: string) => req<Evidence>(`/api/evidence/${id}`),
  sources: (id: string) =>
    req<SourcesResponse>(
      `/api/runs/${id}/sources`),
  reviews: (id: string) => req<{ run_id: string; reviews: Review[] }>(`/api/runs/${id}/reviews`),
  review: (signalId: string, outcome: Review["outcome"], reason: string) =>
    req<Review>(`/api/signals/${signalId}/reviews`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome, reason }),
    }),
  confirmMatches: (runId: string, decisions: Record<string, string | null>) =>
    req<RunStarted>(`/api/runs/${runId}/matches`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decisions }),
    }),
  addInvoices: (runId: string, form: FormData) =>
    req<RunStarted>(`/api/runs/${runId}/invoices`, { method: "POST", body: form }),
  retryRun: (runId: string) => req<RunStarted>(`/api/runs/${runId}/retry`, { method: "POST" }),
  correctInvoice: (runId: string, sourceId: string, body: InvoiceCorrection) =>
    req<RunStarted>(`/api/runs/${runId}/invoices/${sourceId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  runEvaluation: () => req<EvalReport>("/api/evaluation/demo", { method: "POST" }),
  latestEvaluation: () => req<EvalReport>("/api/evaluation/latest"),
};

export const sampleCsvUrl = `${API_URL}/api/demo/sample-csv`;
export const imageUrl = (path: string) => `${API_URL}${path}`;
