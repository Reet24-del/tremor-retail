"""Groq provider behaviour, with the HTTP call mocked. Model output is never trusted directly."""

import json

import httpx
import pytest

from app import config
from app.pipeline import explain, invoice_extract, llm

INVOICE_TEXT_ROWS = [
    invoice_extract.PdfRow(1, "SHAKTI WHOLESALE", [0, 0, 1, 1]),
    invoice_extract.PdfRow(1, "Invoice No: SW-184", [0, 0, 1, 1]),
    invoice_extract.PdfRow(1, "Invoice Date: 2026-09-10", [0, 0, 1, 1]),
    invoice_extract.PdfRow(1, "1 SUNPURE OIL 1 LTR 210 bottle 132.00 27,720.00", [10, 20, 30, 40]),
    invoice_extract.PdfRow(1, "TOTAL 27,720.00", [0, 0, 1, 1]),
]


class FakeResp:
    def __init__(self, content: dict | str, status: int = 200):
        self.status_code = status
        self._content = content if isinstance(content, str) else json.dumps(content)

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture
def groq_on(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM", True)
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "llama-3.3-70b-versatile")


def _mock(monkeypatch, content, status=200, capture=None):
    def fake_post(url, headers, json, timeout):
        if capture is not None:
            capture.update({"url": url, "headers": headers, "json": json})
        return FakeResp(content, status)

    monkeypatch.setattr(httpx, "post", fake_post)


def _patch_rows(monkeypatch):
    monkeypatch.setattr(invoice_extract, "read_pdf_rows", lambda content: (INVOICE_TEXT_ROWS, 1))


def test_request_shape_is_openai_compatible(groq_on, monkeypatch):
    seen: dict = {}
    _mock(monkeypatch, {"ok": 1}, capture=seen)
    llm._json_call("sys", "user")
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["json"]["response_format"] == {"type": "json_object"}
    assert seen["json"]["temperature"] == 0
    assert llm.model_name() == "groq:llama-3.3-70b-versatile"


def test_llm_extraction_is_validated_against_pdf(groq_on, monkeypatch):
    _patch_rows(monkeypatch)
    _mock(
        monkeypatch,
        {
            "supplier_name": "Shakti Wholesale",
            "invoice_number": "SW-184",
            "invoice_date": "2026-09-10",
            "currency": "INR",
            "invoice_total": 27720,
            "line_items": [
                {
                    "raw_description": "SUNPURE OIL 1 LTR",
                    "quantity": 210,
                    "unit": "bottle",
                    "unit_cost": 132,
                    "tax_amount": 0,
                    "line_total": 27720,
                    "confidence": 0.97,
                },
                {
                    "raw_description": "INVENTED ITEM",
                    "quantity": 1,
                    "unit": "x",
                    "unit_cost": 10,
                    "tax_amount": 0,
                    "line_total": 10,
                    "confidence": 0.9,
                },
            ],
        },
    )
    inv, warns, method = invoice_extract.extract_invoice("src_sw_184", b"%PDF")
    assert method == "llm"
    assert [line.raw_description for line in inv.line_items] == ["SUNPURE OIL 1 LTR"]
    assert any("not found in the PDF" in w for w in warns)


def test_provider_error_falls_back_to_deterministic_parser(groq_on, monkeypatch):
    _patch_rows(monkeypatch)
    _mock(monkeypatch, "", status=503)
    inv, warns, method = invoice_extract.extract_invoice("src_sw_184", b"%PDF")
    assert method == "heuristic"
    assert inv.line_items[0].unit_cost == 132
    assert "LLM extraction unavailable" in warns[0]


FACTS = {
    "product": "Sunpure Cooking Oil 1 L",
    "prior_unit_cost": 118,
    "latest_unit_cost": 132,
    "latest_invoice": "SW-184",
    "latest_invoice_date": "10 Sep 2026",
    "average_selling_price_after": 135,
    "prior_margin_percent": 12.6,
    "current_margin_percent": 2.2,
    "estimated_margin_leakage": 1680,
    "price_changes_after_cost_change": [],
    "supplier": "Shakti Wholesale",
    "stock_variance_units": 0,
}


def test_llm_wording_with_invented_number_is_rejected(groq_on, monkeypatch):
    _mock(
        monkeypatch,
        {
            "title": "Oil margin",
            "observation": "Cost rose to INR 150.",
            "interpretation": "May be thin.",
            "next_check": "Verify the rate.",
        },
    )
    _text, source, notes = explain.explain("margin_leakage", FACTS)
    assert source == "template"
    assert any("not in the facts" in n for n in notes)


def test_llm_wording_with_accusation_is_rejected(groq_on, monkeypatch):
    _mock(
        monkeypatch,
        {
            "title": "Oil margin",
            "observation": "Cost rose from 118 to 132.",
            "interpretation": "Staff may have stole stock.",
            "next_check": "Verify the rate.",
        },
    )
    _, source, notes = explain.explain("margin_leakage", FACTS)
    assert source == "template"
    assert any("prohibited" in n for n in notes)


def test_clean_llm_wording_is_used(groq_on, monkeypatch):
    _mock(monkeypatch, explain.template_text("margin_leakage", FACTS))
    text, source, notes = explain.explain("margin_leakage", FACTS)
    assert source == "llm" and not notes
    assert "INR 132" in text["observation"]
