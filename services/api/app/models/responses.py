"""Public response contracts. Extra response fields remain additive within v1."""

from typing import Any, Literal

from pydantic import BaseModel

from .contracts import (
    DataIssue,
    Entity,
    EvidenceReference,
    FinancialImpact,
    Invoice,
    ModelMetadata,
    ProductMatch,
    RejectedCandidate,
    Review,
    RunStatus,
    Severity,
    Signal,
    SignalTranslation,
    SignalType,
    Source,
    Status,
)


class RunSummary(BaseModel):
    bills_uploaded: int | None = None
    margin_check: Literal["skipped_no_bills", "needs_more_bills", "done"] | None = None
    records_analysed: int | None = None
    products: int | None = None
    invoices_read: int | None = None
    invoice_lines: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    signals: int | None = None
    rejected_candidates: int | None = None
    amount_requiring_investigation: float | None = None
    extraction_methods: list[str] | None = None
    llm_enabled: bool | None = None
    matches: dict[str, int] | None = None
    issue_count: int | None = None
    ready_for_review: bool | None = None


class RunResponse(RunStatus):
    summary: RunSummary = RunSummary()


class Product(BaseModel):
    product_id: str
    product_name: str


class OriginalInvoice(BaseModel):
    source_id: str
    invoice: Invoice | None
    warnings: list[str]
    method: str


class SourcesResponse(BaseModel):
    run_id: str
    sources: list[Source]
    matches: list[ProductMatch]
    invoices: list[Invoice]
    original_invoices: list[OriginalInvoice]
    products: list[Product]
    issues: list[DataIssue]
    invoice_corrections: dict[str, Any]
    manual_matches: dict[str, str | None]


class SignalSummary(BaseModel):
    translations: dict[str, SignalTranslation] = {}
    signal_id: str
    run_id: str
    signal_type: SignalType
    status: Status
    severity: Severity
    evidence_strength: float
    entity: Entity
    title: str
    observation: str
    financial_impact: FinancialImpact
    model_metadata: ModelMetadata


class SignalsResponse(BaseModel):
    run_id: str
    run_status: str
    signals: list[SignalSummary]
    rejected_candidates: list[RejectedCandidate]
    issues: list[DataIssue]


class EvidenceMeta(BaseModel):
    evidence_id: str
    source_id: str
    source_type: Literal["sales_csv", "invoice_pdf", "calculation", "calendar"]
    label: str
    locator: dict[str, Any]


class SignalDetail(BaseModel):
    signal: Signal
    evidence: dict[str, EvidenceMeta]
    reviews: list[Review]


class EvidenceResponse(EvidenceReference):
    page_image_url: str | None = None


class CsvValidationResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    summary: dict[str, Any]
    issues: list[DataIssue]


class ErrorDetail(BaseModel):
    message: str
    issues: list[DataIssue]
    errors: list[dict[str, str | None]] = []


class ErrorResponse(BaseModel):
    detail: ErrorDetail
