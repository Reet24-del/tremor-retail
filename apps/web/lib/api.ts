import type {
  EvalReport, Evidence, EvidenceMeta, ProductMatch, RejectedCandidate, Review, RunStatus, Signal, SignalSummary, Source,
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
    const msg = typeof detail === "string" ? detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; llm_enabled: boolean; model: string }>("/api/health"),
  startDemo: () => req<{ run_id: string }>("/api/runs/demo", { method: "POST" }),
  startUpload: (form: FormData) => req<{ run_id: string }>("/api/runs", { method: "POST", body: form }),
  validateCsv: (form: FormData) =>
    req<{ ok: boolean; errors: string[]; warnings: string[]; summary: Record<string, unknown> }>(
      "/api/uploads/validate-csv", { method: "POST", body: form }),
  run: (id: string) => req<RunStatus>(`/api/runs/${id}`),
  signals: (id: string) =>
    req<{ run_id: string; run_status: string; signals: SignalSummary[]; rejected_candidates: RejectedCandidate[] }>(
      `/api/runs/${id}/signals`),
  signal: (id: string) =>
    req<{ signal: Signal; evidence: Record<string, EvidenceMeta>; reviews: Review[] }>(`/api/signals/${id}`),
  evidence: (id: string) => req<Evidence>(`/api/evidence/${id}`),
  sources: (id: string) =>
    req<{ run_id: string; sources: Source[]; matches: ProductMatch[]; invoices: Array<Record<string, unknown>> }>(
      `/api/runs/${id}/sources`),
  reviews: (id: string) => req<{ run_id: string; reviews: Review[] }>(`/api/runs/${id}/reviews`),
  review: (signalId: string, outcome: Review["outcome"], reason: string) =>
    req<Review>(`/api/signals/${signalId}/reviews`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome, reason }),
    }),
  confirmMatches: (runId: string, decisions: Record<string, string | null>) =>
    req<{ run_id: string }>(`/api/runs/${runId}/matches`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decisions }),
    }),
  runEvaluation: () => req<EvalReport>("/api/evaluation/demo", { method: "POST" }),
  latestEvaluation: () => req<EvalReport>("/api/evaluation/latest"),
};

export const sampleCsvUrl = `${API_URL}/api/demo/sample-csv`;
export const imageUrl = (path: string) => `${API_URL}${path}`;
