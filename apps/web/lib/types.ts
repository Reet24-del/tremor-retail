// Shared API types are generated from Pydantic. UI-only extensions live here.
import type { Review as ApiReview, Signal as ApiSignal, RunResponse } from "./contracts.generated";
export type {
  Signal, SignalSummary, SignalTranslation, FinancialImpact, RejectedExplanation, EvidenceMeta,
  RejectedCandidate, Source, ProductMatch, DataIssue, Claim, Invoice, InvoiceCorrection,
  RunStarted, SourcesResponse, SignalsResponse, SignalDetail, CsvValidationResponse,
} from "./contracts.generated";
export type { EvidenceResponse as Evidence } from "./contracts.generated";
export type RunStatus = RunResponse;
export type Severity = ApiSignal["severity"];
export type SignalStatus = ApiSignal["status"];
export type SignalType = ApiSignal["signal_type"];
export type Review = ApiReview & { signal_title?: string; severity?: Severity; amount?: number };

export interface CsvRow {
  source_row: number;
  transaction_date: string;
  product_name: string;
  quantity_sold: number;
  unit_selling_price: number;
  opening_stock: number;
  closing_stock: number;
  recorded_damage: number;
  recorded_returns: number;
}

export interface EvalMetric {
  value: number;
  count?: string;
  target?: string;
}

export interface EvalReport {
  run_id: string;
  generated_at: string;
  passed: boolean;
  versions: Record<string, unknown>;
  metrics: Record<string, EvalMetric>;
  items: Array<Record<string, unknown>>;
}

export const STAGE_LABELS: Record<string, string> = {
  validating_records: "Validating records",
  reading_supplier_bills: "Reading supplier bills",
  matching_products: "Matching products",
  calculating_features: "Calculating financial features",
  finding_unusual_changes: "Finding unusual changes",
  linking_evidence: "Linking evidence",
  preparing_signals: "Preparing signals",
};
export const STAGES = Object.keys(STAGE_LABELS);
