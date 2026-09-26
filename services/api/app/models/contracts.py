"""Pydantic contracts (PRD sections 10 to 12). Keep in sync with apps/web/lib/types.ts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DataIssue(Strict):
    code: str
    message: str
    action: str
    file: str | None = None
    field: str | None = None
    rows: list[int] = []
    source_id: str | None = None
    product_id: str | None = None
    line_ids: list[str] = []
    status: Literal["needs_review", "needs_data", "unresolved"] = "needs_data"


# ---------- Invoices ----------
class InvoiceLine(Strict):
    line_id: str
    raw_description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str
    unit_cost: float = Field(gt=0)
    tax_amount: float = Field(default=0, ge=0)
    line_total: float = Field(gt=0)
    page_number: int = Field(ge=1)
    source_text: str = ""
    extraction_confidence: float = Field(ge=0, le=1)
    bbox: list[float] | None = None
    validation_status: Literal["verified", "needs_review", "confirmed"] = "verified"
    validation_issues: list[str] = []


class Invoice(Strict):
    source_id: str
    supplier_name: str
    invoice_number: str
    invoice_date: date
    currency: Literal["INR"]
    line_items: list[InvoiceLine] = Field(min_length=1)
    invoice_total: float = Field(gt=0)
    extraction_method: Literal["llm", "cached", "heuristic", "manual"]
    extraction_warnings: list[str] = []
    validation_status: Literal["verified", "needs_review", "confirmed"] = "verified"


class LLMInvoiceLine(Strict):
    """What the LLM is allowed to return per line (locators are added by code)."""

    raw_description: str
    quantity: float
    unit: str
    unit_cost: float
    tax_amount: float = 0
    line_total: float
    confidence: float = Field(ge=0, le=1)


class LLMInvoice(Strict):
    supplier_name: str
    invoice_number: str
    invoice_date: date
    currency: Literal["INR"]
    invoice_total: float
    line_items: list[LLMInvoiceLine]


class InvoiceCorrection(Strict):
    invoice: LLMInvoice
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Explain why the invoice fields were confirmed or corrected")
        return v.strip()


class MatchDecisions(Strict):
    decisions: dict[str, str | None]


class RunStarted(Strict):
    run_id: str
    status: str
    stages: list[str] = []
    parent_run_id: str | None = None


# ---------- Sources ----------
class Source(Strict):
    source_id: str
    type: Literal["sales_csv", "invoice_pdf"]
    filename: str
    content_hash: str
    uploaded_at: datetime
    page_count: int | None = None
    row_count: int | None = None
    status: Literal["ok", "warning", "error"] = "ok"
    messages: list[str] = []
    summary: dict[str, Any] = {}


# ---------- Matching ----------
class ProductMatch(Strict):
    match_id: str
    line_description: str
    product_id: str | None
    product_name: str | None
    method: Literal["exact", "fuzzy", "semantic", "frozen", "manual", "none"]
    scores: dict[str, float]
    confidence: float
    status: Literal["accepted", "needs_review", "unmatched", "blocked"]
    reason: str = ""
    semantic_backend: Literal["lexicon", "sentence_transformers", "fallback_lexicon"] = "lexicon"


# ---------- Signals ----------
SignalType = Literal["margin_leakage", "inventory_discrepancy"]
Severity = Literal["high", "medium", "low"]
Status = Literal["new", "unresolved", "confirmed", "dismissed", "needs_data"]


class Entity(Strict):
    type: Literal["product"]
    id: str
    display_name: str


class FinancialImpact(Strict):
    amount: float
    currency: Literal["INR"] = "INR"
    label: str
    method: str


class RejectedExplanation(Strict):
    name: str
    reason: str
    evidence_ids: list[str]


class ModelMetadata(Strict):
    detector_version: str
    prompt_version: str
    model_name: str
    explanation_source: Literal["llm", "template"]
    extraction_method: str


class Claim(Strict):
    claim_id: str
    field: str
    text: str
    kind: Literal["observation", "interpretation", "recommendation"]
    evidence_ids: list[str] = Field(min_length=1)


class SignalTranslation(Strict):
    title: str = ""
    observation: str = ""
    impact_label: str = ""
    interpretation: str = ""
    next_check: str = ""
    limitations: list[str] = Field(default_factory=list)


class Signal(Strict):
    signal_id: str
    run_id: str
    signal_type: SignalType
    status: Status = "new"
    severity: Severity
    evidence_strength: float = Field(ge=0, le=1)
    evidence_strength_components: dict[str, float]
    entity: Entity
    title: str
    observation: str
    financial_impact: FinancialImpact
    interpretation: str
    evidence_ids: list[str] = Field(min_length=2)
    rejected_explanations: list[RejectedExplanation]
    limitations: list[str] = Field(min_length=1)
    next_check: str
    facts: dict[str, Any]
    ranking: dict[str, float]
    model_metadata: ModelMetadata
    # Language code -> translated user-facing text (title, observation, interpretation, next_check,
    # limitations, impact_label). Built from the same validated facts as the English text.
    translations: dict[str, SignalTranslation] = Field(default_factory=dict)
    claims: list[Claim] = Field(min_length=1)

    @field_validator("next_check", "observation", "interpretation", "title")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class EvidenceReference(Strict):
    evidence_id: str
    signal_id: str
    source_id: str
    source_type: Literal["sales_csv", "invoice_pdf", "calculation", "calendar"]
    label: str
    locator: dict[str, Any]
    excerpt: Any


class RejectedCandidate(Strict):
    candidate_id: str
    candidate_type: str
    product_ids: list[str]
    title: str
    reason: str
    anomaly_score: float
    evidence: dict[str, Any]


class Review(Strict):
    review_id: str
    signal_id: str
    run_id: str
    outcome: Literal["confirmed", "dismissed", "unresolved"]
    reason: str
    created_at: datetime


class ReviewIn(Strict):
    outcome: Literal["confirmed", "dismissed", "unresolved"]
    reason: str = ""


STAGES = [
    "validating_records",
    "reading_supplier_bills",
    "matching_products",
    "calculating_features",
    "finding_unusual_changes",
    "linking_evidence",
    "preparing_signals",
]


class RunStatus(Strict):
    run_id: str
    mode: Literal["demo", "upload"]
    status: Literal["running", "completed", "failed"]
    current_stage: str | None
    completed_stages: list[str]
    failed_stage: str | None = None
    error: str | None = None
    warnings: list[str] = []
    started_at: datetime
    completed_at: datetime | None = None
    dataset_version: str
    configuration_version: str
    store_name: str = ""
    summary: dict[str, Any] = {}
    contract_version: str = "1.1"
    parent_run_id: str | None = None
    issues: list[DataIssue] = []
    retryable: bool = False
