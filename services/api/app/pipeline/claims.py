"""Sentence-level citations for bounded, validated wording."""

import re

from .explain import approved_wording


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())


def financial_impact(kind: str, facts: dict) -> dict:
    if kind == "margin_leakage":
        return {
            "amount": round(facts["estimated_margin_leakage"], 2),
            "currency": "INR",
            "label": "estimated margin leakage",
            "method": f"{facts['units_sold_after_cost_change']:g} units sold since {facts['latest_invoice_date']} x "
            f"INR {facts['unit_cost_increase']:g} increase in unit cost",
        }
    basis = "latest unit cost" if facts.get("value_basis", "latest_cost") == "latest_cost" else "median selling price"
    price = facts.get("valuation_unit_price", facts["latest_unit_cost"])
    return {
        "amount": round(facts["variance_value_at_latest_cost"], 2),
        "currency": "INR",
        "label": "estimated stock value not reconciled",
        "method": f"{abs(facts['stock_variance_units']):g} units x {basis} INR {price:g}",
    }


def build_claims(signal: dict) -> list[dict]:
    ids = signal["evidence_ids"]

    def pick(*suffixes):
        return [e for e in ids if any(e.endswith(s) for s in suffixes)] or ids

    claims = []
    for field, kind in (
        ("title", "interpretation"),
        ("observation", "observation"),
        ("interpretation", "interpretation"),
        ("next_check", "recommendation"),
    ):
        for i, sentence in enumerate(sentences(signal[field])):
            refs = ids
            if signal["signal_type"] == "margin_leakage":
                refs = pick("old_invoice", "new_invoice", "sales_rows", "sales_before", "calculation")
                if "stock" in sentence.lower() or "units are missing" in sentence.lower():
                    refs = pick("stock_calc", "new_invoice", "old_invoice")
            claims.append({"claim_id": f"{field}_{i + 1}", "field": field, "text": sentence, "kind": kind, "evidence_ids": refs})
    claims.append(
        {
            "claim_id": "financial_impact",
            "field": "financial_impact.method",
            "text": signal["financial_impact"]["method"],
            "kind": "observation",
            "evidence_ids": ids,
        }
    )
    for i, alternative in enumerate(signal["rejected_explanations"]):
        for j, sentence in enumerate(sentences(alternative["reason"])):
            claims.append(
                {
                    "claim_id": f"alternative_{i + 1}_{j + 1}",
                    "field": f"rejected_explanations.{i}.reason",
                    "text": sentence,
                    "kind": "observation",
                    "evidence_ids": alternative["evidence_ids"],
                }
            )
    return claims


def validate_claims(signal: dict, evidence: dict, facts: dict) -> list[str]:
    errors = []
    if signal["financial_impact"] != financial_impact(signal["signal_type"], facts):
        errors.append("Financial impact and calculation wording must equal the stored facts")
    allowed = approved_wording(signal["signal_type"], facts)
    for field, choices in allowed.items():
        if signal[field] not in choices:
            errors.append(f"{field}: wording is not an approved statement of the calculated facts")
    expected = build_claims(signal)
    if signal.get("claims") != expected:
        errors.append("Claims must cover every sentence with its required evidence")
    for claim in signal.get("claims", []):
        for eid in claim["evidence_ids"]:
            ev = evidence.get(eid)
            if not ev or ev.get("signal_id") != signal["signal_id"]:
                errors.append(f"Claim {claim['claim_id']}: missing or unrelated evidence {eid}")
    # Bind the values used for wording to the stored calculation, not merely a bag of allowed numbers.
    for eid in signal["evidence_ids"]:
        ev = evidence.get(eid, {})
        if ev.get("source_type") == "calculation":
            for key, value in ev["excerpt"].items():
                if key in facts and facts[key] != value:
                    errors.append(f"Claim fact {key} differs from its stored calculation")
        if ev.get("source_type") == "invoice_pdf":
            prefix = "prior" if eid.endswith("old_invoice") else "latest" if eid.endswith("new_invoice") else None
            if prefix and facts[f"{prefix}_unit_cost"] != ev["excerpt"]["unit_cost"]:
                errors.append(f"Claim fact {prefix}_unit_cost differs from the invoice")
    return errors
