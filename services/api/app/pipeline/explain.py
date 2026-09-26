"""Plain-language signal text (PRD 13.5).

Template text is always built from validated facts. When an LLM is configured it may reword the
text, but its output is only used if it passes the number and safety validators.
"""

from __future__ import annotations

import contextlib
import re

from .. import config
from ..safety.policy import prohibited_phrases, unreferenced_numbers
from . import llm

THIN_MARGIN_PERCENT = 5.0  # below this a margin is treated as too thin to cover store costs


def _inr(x: float) -> str:
    x = float(x)
    return f"INR {x:,.0f}" if x.is_integer() else f"INR {x:,.2f}"


def _pct(x: float) -> str:
    return f"{x:.1f} percent"


def severity_for(signal_type: str, facts: dict) -> str:
    if signal_type == "margin_leakage":
        if facts["current_margin_percent"] < THIN_MARGIN_PERCENT and facts["estimated_margin_leakage"] >= 700:
            return "high"
        return "medium"
    return "high" if facts.get("variance_value_at_latest_cost", 0) >= 2000 else "medium"


def template_text(signal_type: str, facts: dict) -> dict:
    name = facts["product"]
    if signal_type == "margin_leakage":
        obs = (
            f"The supplier cost rose from {_inr(facts['prior_unit_cost'])} to {_inr(facts['latest_unit_cost'])} on "
            f"invoice {facts['latest_invoice']} ({facts['latest_invoice_date']}) while the average selling price "
            + ("since then was " if facts["price_changes_after_cost_change"] else "stayed near ")
            + f"{_inr(facts['average_selling_price_after'])}. Gross margin fell from "
            f"{_pct(facts['prior_margin_percent'])} to {_pct(facts['current_margin_percent'])}."
        )
        if facts["current_margin_percent"] < THIN_MARGIN_PERCENT:
            interp = "The shop may now be selling this product at a margin too small to cover its other costs."
        else:
            interp = (
                "The margin on this product is shrinking. It is still positive, but each unit now earns less "
                "than before the supplier cost change."
            )
        if facts["price_changes_after_cost_change"]:
            d, p = facts["price_changes_after_cost_change"][-1]
            interp += (
                f" The selling price was raised to {_inr(p)} on {d}, which recovers part of the increase "
                "but only for the last few days."
            )
        checks = [f"verify the latest supplier rate with {facts['supplier']}"]
        if abs(facts.get("stock_variance_units") or 0) >= 1:
            n = abs(int(facts["stock_variance_units"]))
            interp += (
                f" A {n} unit stock difference was also counted, which may add further loss. "
                "It does not show why the units are missing."
            )
            checks.append(f"recount the {n} unit stock difference")
        checks.append("review whether the selling price should be updated")
        nxt = _join(checks)
        title = f"{name}: margin leakage requires review"
    else:
        n = abs(int(facts["stock_variance_units"]))
        obs = (
            f"Expected closing stock is {facts['expected_closing_stock']:g} units, but the counted closing stock is "
            f"{facts['actual_closing_stock']:g} units. The records do not reconcile by {n} units, first seen on "
            f"{facts['discrepancy_dates'][0]}."
        )
        interp = (
            "This may be unrecorded sales, damaged stock that was not logged, or a counting error. "
            "It is a record mismatch to check, not proof of wrongdoing by anyone."
        )
        nxt = _join(
            [f"recount {name} on the shelf and in storage", "check whether any sales or damage were not entered on that day"]
        )
        title = f"{name}: stock does not reconcile"
    return {"title": title, "observation": obs, "interpretation": interp, "next_check": nxt}


def _join(parts: list[str]) -> str:
    parts = [p[0].upper() + p[1:] if i == 0 else p for i, p in enumerate(parts)]
    if len(parts) == 1:
        return parts[0] + "."
    return ", ".join(parts[:-1]) + " and " + parts[-1] + "."


def allowed_numbers(facts: dict) -> set[float]:
    nums: set[float] = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            nums.update({round(float(v), 1), round(abs(float(v)), 1), round(float(v), 0), round(abs(float(v)), 0)})
        elif isinstance(v, str):
            for m in re.finditer(r"\d[\d,]*\.?\d*", v):
                with contextlib.suppress(ValueError):
                    nums.add(round(float(m.group(0).rstrip(".").replace(",", "")), 1))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(facts)
    return nums


def check_text(text: dict, facts: dict) -> list[str]:
    problems = []
    allowed = allowed_numbers(facts)
    for k in ("title", "observation", "interpretation", "next_check"):
        v = text.get(k, "")
        if not isinstance(v, str) or not v.strip():
            problems.append(f"{k} is empty")
            continue
        bad = prohibited_phrases(v)
        if bad:
            problems.append(f"{k} contains prohibited language: {bad}")
        extra = unreferenced_numbers(v, allowed)
        if extra:
            problems.append(f"{k} contains numbers not in the facts: {extra}")
    return problems


def approved_wording(signal_type: str, facts: dict) -> dict[str, list[str]]:
    base = template_text(signal_type, facts)
    choices = {key: [value] for key, value in base.items()}
    choices["interpretation"].append("These records may indicate an issue that needs a human review.")
    choices["next_check"].append("Verify the cited invoices and sales records before deciding what to do.")
    return choices


def explain(signal_type: str, facts: dict) -> tuple[dict, str, list[str]]:
    """Returns (text, source, notes). Source is 'llm' or 'template'."""
    base = template_text(signal_type, facts)
    if not llm.enabled():
        return base, "template", []
    try:
        out = llm.explain_signal(
            {
                "signal_type": signal_type,
                "facts": facts,
                "draft": base,
                "approved_wording": approved_wording(signal_type, facts),
                "prompt_version": config.PROMPT_VERSION,
            }
        )
        text = {k: str(out.get(k, "")).strip() for k in ("title", "observation", "interpretation", "next_check")}
        problems = check_text(text, facts)
        for key, choices in approved_wording(signal_type, facts).items():
            if text.get(key) not in choices:
                problems.append(f"{key} is outside the evidence-validated wording choices")
        if problems:
            return base, "template", [f"LLM wording rejected: {p}" for p in problems]
        return text, "llm", []
    except Exception as exc:
        return base, "template", [f"LLM unavailable ({type(exc).__name__}); used template wording"]
