// Mirrors services/api/app/models/contracts.py. Keep in sync.
export type Severity = "high" | "medium" | "low";
export type SignalStatus = "new" | "unresolved" | "confirmed" | "dismissed" | "needs_data";
export type SignalType = "margin_leakage" | "inventory_discrepancy";

export interface RunStatus {
  run_id: string;
  mode: "demo" | "upload";
  status: "running" | "completed" | "failed";
  current_stage: string | null;
  completed_stages: string[];
  failed_stage: string | null;
  error: string | null;
  warnings: string[];
  started_at: string;
  completed_at: string | null;
  dataset_version: string;
  configuration_version: string;
  store_name: string;
  summary: {
    records_analysed?: number;
    products?: number;
    invoices_read?: number;
    invoice_lines?: number;
    date_from?: string;
    date_to?: string;
    signals?: number;
    rejected_candidates?: number;
    amount_requiring_investigation?: number;
    extraction_methods?: string[];
    bills_uploaded?: number;
    margin_check?: "done" | "skipped_no_bills" | "needs_more_bills";
    llm_enabled?: boolean;
    matches?: Record<string, number>;
  };
}

export interface FinancialImpact {
  amount: number;
  currency: "INR";
  label: string;
  method: string;
}

export interface SignalSummary {
  signal_id: string;
  run_id: string;
  signal_type: SignalType;
  status: SignalStatus;
  severity: Severity;
  evidence_strength: number;
  entity: { type: "product"; id: string; display_name: string };
  title: string;
  observation: string;
  financial_impact: FinancialImpact;
  model_metadata: {
    detector_version: string;
    prompt_version: string;
    model_name: string;
    explanation_source: "llm" | "template";
    extraction_method: string;
  };
}

export interface RejectedExplanation {
  name: string;
  reason: string;
  evidence_ids: string[];
}

export interface Signal extends SignalSummary {
  evidence_strength_components: Record<string, number>;
  interpretation: string;
  evidence_ids: string[];
  rejected_explanations: RejectedExplanation[];
  limitations: string[];
  next_check: string;
  facts: Record<string, unknown>;
  ranking: Record<string, number>;
}

export interface EvidenceMeta {
  evidence_id: string;
  source_id: string;
  source_type: "sales_csv" | "invoice_pdf" | "calculation" | "calendar";
  label: string;
  locator: Record<string, unknown>;
}

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

export interface Evidence extends EvidenceMeta {
  signal_id: string;
  excerpt: unknown;
  page_image_url?: string;
}

export interface RejectedCandidate {
  candidate_id: string;
  candidate_type: string;
  product_ids: string[];
  title: string;
  reason: string;
  anomaly_score: number;
  evidence: Record<string, unknown>;
}

export interface Review {
  review_id: string;
  signal_id: string;
  run_id: string;
  outcome: "confirmed" | "dismissed" | "unresolved";
  reason: string;
  created_at: string;
  signal_title?: string;
  severity?: Severity;
  amount?: number;
}

export interface Source {
  source_id: string;
  type: "sales_csv" | "invoice_pdf";
  filename: string;
  content_hash: string;
  uploaded_at: string;
  page_count: number | null;
  row_count: number | null;
  status: "ok" | "warning" | "error";
  messages: string[];
  summary: Record<string, unknown>;
}

export interface ProductMatch {
  match_id: string;
  line_description: string;
  product_id: string | null;
  product_name: string | null;
  method: string;
  scores: Record<string, number>;
  confidence: number;
  status: "accepted" | "needs_review" | "unmatched" | "blocked";
  reason: string;
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
