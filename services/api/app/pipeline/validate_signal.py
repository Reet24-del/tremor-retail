"""Publication rule (PRD 7.4) and final signal validation. Fails closed."""

from __future__ import annotations

from ..models.contracts import Signal
from ..safety.policy import prohibited_phrases
from .explain import check_text


def validate(signal: dict, evidence: dict, facts: dict) -> tuple[Signal | None, list[str]]:
    problems: list[str] = []
    try:
        sig = Signal.model_validate(signal)
    except Exception as exc:
        return None, [f"schema: {exc}"]
    missing = [e for e in sig.evidence_ids if e not in evidence]
    if missing:
        problems.append(f"unresolved evidence ids: {missing}")
    for alt in sig.rejected_explanations:
        if any(e not in evidence for e in alt.evidence_ids):
            problems.append(f"rejected explanation '{alt.name}' has unresolved evidence")
    types = {evidence[e]["source_type"] for e in sig.evidence_ids if e in evidence}
    if not ({"sales_csv", "invoice_pdf"} <= types):
        problems.append(f"needs evidence from both the CSV and an invoice, got {sorted(types)}")
    if sig.signal_type == "margin_leakage" and (
        round(sig.financial_impact.amount, 2) != round(float(facts["estimated_margin_leakage"]), 2)
    ):
        problems.append("financial impact does not equal the calculated leakage")
    problems += check_text(
        {"title": sig.title, "observation": sig.observation, "interpretation": sig.interpretation, "next_check": sig.next_check},
        facts,
    )
    for alt in sig.rejected_explanations:
        if prohibited_phrases(alt.reason):
            problems.append("rejected explanation contains prohibited language")
    return (None if problems else sig), problems
