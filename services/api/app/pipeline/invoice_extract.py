"""Supplier invoice extraction (PRD 9.2, 13.1).

1. PyMuPDF reads words with positions and rebuilds visual rows (keeps page + bbox).
2. Fields come from one of:
   - llm: schema-constrained LLM call (when a key is configured)
   - cached: frozen validated JSON for the bundled demo, verified line by line against the real PDF text
   - heuristic: deterministic table parser (fallback when no LLM is configured)
3. Everything passes Pydantic + arithmetic checks. Invalid lines fail closed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf

from ..models.contracts import Invoice, InvoiceLine, LLMInvoice
from ..safety.policy import wrap_untrusted
from . import llm
from .invoice_validation import numeric_fields_present, unsupported_currency

NUM = r"-?\d[\d,]*\.?\d*"


@dataclass
class PdfRow:
    page: int
    text: str
    bbox: list[float]


def read_pdf_rows(content: bytes) -> tuple[list[PdfRow], int]:
    doc = pymupdf.open(stream=content, filetype="pdf")
    rows: list[PdfRow] = []
    for pno, page in enumerate(doc, 1):
        words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, wno
        buckets: dict[int, list] = {}
        for w in words:
            key = round((w[1] + w[3]) / 2 / 3)  # group by vertical centre (3pt tolerance)
            buckets.setdefault(key, []).append(w)
        for key in sorted(buckets):
            ws = sorted(buckets[key], key=lambda w: w[0])
            text = " ".join(w[4] for w in ws)
            bbox = [min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)]
            rows.append(PdfRow(pno, text, [round(b, 1) for b in bbox]))
    return rows, doc.page_count


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().upper())


def _header(rows: list[PdfRow]) -> dict:
    text = "\n".join(r.text for r in rows)
    out = {}
    m = re.search(r"Invoice No:?\s*([A-Z0-9\-/]+)", text, re.I)
    if m:
        out["invoice_number"] = m.group(1)
    m = re.search(r"Invoice Date:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
    if m:
        out["invoice_date"] = m.group(1)
    else:
        m = re.search(r"Invoice Date:?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text, re.I)
        if m:
            out["invoice_date"] = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    if rows:
        out["supplier_name"] = rows[0].text.title()
    m = re.search(r"^TOTAL\s+(" + NUM + r")$", text, re.M | re.I)
    if m:
        out["invoice_total"] = _num(m.group(1))
    return out


LINE_RE = re.compile(rf"^(\d+)\s+(.+?)\s+({NUM})\s+([A-Za-z]+)\s+({NUM})\s+({NUM})$")


def heuristic_extract(rows: list[PdfRow]) -> dict:
    head = _header(rows)
    lines = []
    for r in rows:
        m = LINE_RE.match(r.text)
        if not m:
            continue
        lines.append(
            {
                "raw_description": m.group(2),
                "quantity": _num(m.group(3)),
                "unit": m.group(4).lower(),
                "unit_cost": _num(m.group(5)),
                "tax_amount": 0.0,
                "line_total": _num(m.group(6)),
                "confidence": 0.9,
            }
        )
    return {**head, "currency": "INR", "line_items": lines}


def _locate(desc: str, rows: list[PdfRow]) -> PdfRow | None:
    d = _norm(desc)
    for r in rows:
        if d and d in _norm(r.text):
            return r
    return None


def _build(
    source_id: str, data: dict, rows: list[PdfRow], method: str, confirmed: bool = False
) -> tuple[Invoice | None, list[str]]:
    if data.get("currency", "INR") != "INR" or unsupported_currency("\n".join(r.text for r in rows)):
        return None, ["Unsupported currency: only INR invoices can be analysed"]
    warnings: list[str] = []
    lines: list[InvoiceLine] = []
    for i, li in enumerate(data.get("line_items", []), 1):
        try:
            qty, cost, total = float(li["quantity"]), float(li["unit_cost"]), float(li["line_total"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"Line {i}: missing or non-numeric fields; excluded")
            continue
        if abs(qty * cost - total) > max(1.0, 0.01 * total):
            warnings.append(f"Line {i} ({li.get('raw_description')}): quantity x rate does not equal amount; excluded")
            continue
        row = _locate(li.get("raw_description", ""), rows)
        if row is None:
            warnings.append(f"Line {i} ({li.get('raw_description')}): text not found in the PDF; excluded")
            continue
        problems = []
        if not numeric_fields_present(li, row.text):
            problems.append("Numeric fields do not match the cited PDF row")
        parsed = LINE_RE.match(row.text)
        if parsed:
            if any(
                abs(float(li[k]) - _num(parsed.group(g))) > 0.005
                for k, g in (("quantity", 3), ("unit_cost", 5), ("line_total", 6))
            ):
                problems.append("Quantity, rate or total is assigned to the wrong PDF column")
            if str(li.get("unit", "")).lower() != parsed.group(4).lower():
                problems.append("Unit differs from the PDF row")
        elif not confirmed:
            problems.append("Unfamiliar invoice layout: confirm the field-to-column mapping")
        if confirmed and problems:
            warnings.append(f"Line {i}: {'; '.join(problems)}; excluded")
            continue
        conf = float(li.get("confidence", li.get("extraction_confidence", 0.9)))
        if conf < 0.85 and not confirmed:
            problems.append("Extraction confidence is below 85%; confirmation required")
        if problems:
            warnings.append(f"Line {i}: {'; '.join(problems)}")
        try:
            lines.append(
                InvoiceLine(
                    line_id=f"{source_id}:line_{i:02d}",
                    raw_description=li["raw_description"],
                    quantity=qty,
                    unit=str(li.get("unit", "")).lower(),
                    unit_cost=cost,
                    tax_amount=float(li.get("tax_amount") or 0),
                    line_total=total,
                    page_number=row.page,
                    source_text=row.text,
                    extraction_confidence=min(conf, 1.0),
                    bbox=row.bbox,
                    validation_status="confirmed" if confirmed else ("needs_review" if problems else "verified"),
                    validation_issues=problems,
                )
            )
        except Exception as exc:
            warnings.append(f"Line {i}: failed schema validation ({exc}); excluded")
    if not lines:
        return None, [*warnings, "No valid line items could be extracted"]
    total = data.get("invoice_total")
    line_sum = sum(line.line_total for line in lines)
    if total is None:
        warnings.append("Invoice total not found; using the sum of extracted lines")
        total = line_sum
    elif abs(float(total) - line_sum) > max(1.0, 0.005 * line_sum):
        warnings.append(
            f"Extracted lines sum to {line_sum:,.2f} but invoice total is {float(total):,.2f}; some lines may be missing"
        )
    if _norm(data.get("supplier_name", "")) not in _norm(" ".join(r.text for r in rows)):
        if confirmed:
            return None, ["Supplier name must be present in the PDF"]
        warnings.append("Supplier name not verified in the PDF; confirmation required")
    header = _header(rows)
    for key in ("invoice_date", "invoice_number", "invoice_total"):
        value = data.get(key)
        printed = header.get(key)
        if printed is None or str(value) != str(printed):
            # Numeric equality tolerates 1320 versus 1320.0.
            if key == "invoice_total" and printed is not None and value is not None and float(value) == float(printed):
                continue
            if confirmed and printed is not None:
                return None, [f"Header {key} differs from the PDF; correct it before confirming"]
            warnings.append(f"Header {key}: requires confirmation against the PDF")
    if confirmed and (
        any("excluded" in w or "some lines may be missing" in w for w in warnings)
        or len(lines) != len(data.get("line_items", []))
    ):
        return None, warnings
    try:
        inv = Invoice(
            source_id=source_id,
            supplier_name=data.get("supplier_name") or "Unknown supplier",
            invoice_number=data.get("invoice_number") or source_id,
            invoice_date=date.fromisoformat(str(data["invoice_date"])),
            currency="INR",
            line_items=lines,
            invoice_total=float(total),
            extraction_method=method,
            extraction_warnings=warnings,
            validation_status="confirmed" if confirmed else ("needs_review" if warnings else "verified"),
        )
    except Exception as exc:
        return None, [*warnings, f"Invoice header failed validation: {exc}"]
    return inv, warnings


def extract_invoice(source_id: str, content: bytes, cached_path: Path | None = None) -> tuple[Invoice | None, list[str], str]:
    try:
        rows, _ = read_pdf_rows(content)
    except Exception:
        return None, ["Corrupted or unreadable PDF; replace this file"], "none"
    if unsupported_currency("\n".join(r.text for r in rows)):
        return None, ["Unsupported currency: only INR invoices can be analysed"], "none"
    if not rows:
        return None, ["No text layer found (image-only PDF). Please upload a digital PDF or confirm fields."], "none"
    if llm.enabled():
        try:
            raw = llm.extract_invoice(wrap_untrusted("\n".join(r.text for r in rows)))
            parsed = LLMInvoice.model_validate(raw)
            inv, warns = _build(source_id, parsed.model_dump(mode="json"), rows, "llm")
            if inv:
                return inv, warns, "llm"
        except Exception as exc:
            fallback_note = f"LLM extraction unavailable ({type(exc).__name__}); used fallback"
        else:
            fallback_note = "LLM extraction returned no valid lines; used fallback"
    else:
        fallback_note = None
    if cached_path and cached_path.exists():
        data = json.loads(cached_path.read_text())
        inv, warns = _build(source_id, data, rows, "cached")
        if fallback_note:
            warns.insert(0, fallback_note)
        return inv, warns, "cached"
    inv, warns = _build(source_id, heuristic_extract(rows), rows, "heuristic")
    if fallback_note:
        warns.insert(0, fallback_note)
    return inv, warns, "heuristic"
