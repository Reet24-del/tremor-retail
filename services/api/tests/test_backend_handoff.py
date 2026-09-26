"""Regression coverage for the frontend handoff's data integrity and recovery contracts."""

import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_api import _wait

from app import config
from app.main import app
from app.pipeline import invoice_extract, llm
from app.pipeline.claims import validate_claims
from app.pipeline.detect import detect
from app.pipeline.features import Purchase, build_features
from app.pipeline.ingest import load_sales_csv
from app.pipeline.invoice_extract import PdfRow, _build
from app.pipeline.product_match import validate_decisions
from app.pipeline.retained import load_inputs
from app.pipeline.run import Run, demo_inputs
from app.storage import repository as repo

client = TestClient(app)
HEADER = "transaction_id,transaction_date,product_id,product_name,quantity_sold,unit_selling_price,opening_stock,closing_stock"
ROWS = [
    PdfRow(1, "Supplier", [0, 0, 100, 10]),
    PdfRow(1, "Invoice No: X-1", [0, 10, 100, 20]),
    PdfRow(1, "Invoice Date: 2026-09-10", [0, 20, 100, 30]),
    PdfRow(1, "1 Oil 1 L 10 bottle 132.00 1320.00", [0, 30, 200, 40]),
    PdfRow(1, "TOTAL 1320.00", [0, 40, 100, 50]),
]
DATA = {
    "supplier_name": "Supplier",
    "invoice_number": "X-1",
    "invoice_date": "2026-09-10",
    "currency": "INR",
    "invoice_total": 1320,
    "line_items": [
        {
            "raw_description": "Oil 1 L",
            "quantity": 10,
            "unit": "bottle",
            "unit_cost": 132,
            "line_total": 1320,
            "confidence": 0.99,
        },
    ],
}


@pytest.fixture(scope="module")
def completed():
    run = Run(demo_inputs()).execute()
    assert run.status.status == "completed"
    return run


def correction_body(invoice):
    body = {k: invoice[k] for k in ("supplier_name", "invoice_number", "invoice_date", "currency", "invoice_total")}
    body["line_items"] = []
    for line in invoice["line_items"]:
        item = {k: line[k] for k in ("raw_description", "quantity", "unit", "unit_cost", "tax_amount", "line_total")}
        item["confidence"] = line["extraction_confidence"]
        body["line_items"].append(item)
    return {"invoice": body, "reason": "Checked against the original PDF"}


def test_consistent_but_invented_numbers_cannot_be_verified():
    data = copy.deepcopy(DATA)
    data["line_items"][0].update(quantity=20, unit_cost=66)
    inv, warnings = _build("src", data, ROWS, "llm")
    assert inv.validation_status == "needs_review"
    assert inv.line_items[0].validation_status == "needs_review"
    assert any("Numeric fields" in w for w in warnings)
    inv, _ = _build("src", data, ROWS, "manual", confirmed=True)
    assert inv is None


def test_swapping_quantity_and_rate_is_not_grounded():
    data = copy.deepcopy(DATA)
    data["line_items"][0].update(quantity=132, unit_cost=10)
    inv, _ = _build("src", data, ROWS, "llm")
    assert inv.line_items[0].validation_status == "needs_review"


def test_low_confidence_requires_explicit_confirmation():
    data = copy.deepcopy(DATA)
    data["line_items"][0]["confidence"] = 0.2
    inv, _ = _build("src", data, ROWS, "llm")
    assert inv.validation_status == "needs_review"
    confirmed, _ = _build("src", data, ROWS, "manual", confirmed=True)
    assert confirmed.validation_status == "confirmed"
    assert confirmed.line_items[0].extraction_confidence == 0.2


@pytest.mark.parametrize("marker", ["USD", "EUR", "$", "GBP"])
def test_foreign_invoice_cannot_fall_back_to_inr(marker, monkeypatch):
    monkeypatch.setattr(invoice_extract, "read_pdf_rows", lambda _: ([*ROWS, PdfRow(1, marker, [0, 0, 1, 1])], 1))
    monkeypatch.setattr(llm, "extract_invoice", lambda _: pytest.fail("Foreign currency reached the model"))
    inv, warnings, _ = invoice_extract.extract_invoice("src", b"%PDF")
    assert inv is None and "Unsupported currency" in warnings[0]


def test_foreign_csv_and_nonfinite_values_rejected():
    csv = HEADER + ",currency\nT1,2026-09-01,P,Oil,1,132,10,9,USD\n"
    assert any("currency" in e for e in load_sales_csv(csv.encode()).errors)
    csv = HEADER + "\nT1,2026-09-01,P,Oil,1,inf,10,9\n"
    assert any("Invalid number" in e for e in load_sales_csv(csv.encode()).errors)


def test_conflicting_costs_are_not_selected():
    csv = HEADER + "\nT1,2026-09-01,P,Oil,10,135,100,90\nT2,2026-09-10,P,Oil,10,135,90,80\n"
    purchases = [
        Purchase(date(2026, 9, d), cost, 10, f"line{i}", f"src{i}", f"I{i}", "S", 1, 1)
        for i, (d, cost) in enumerate([(1, 118), (10, 132), (10, 140)])
    ]
    feature = build_features(load_sales_csv(csv.encode()).df, {"P": purchases})["P"]
    assert set(feature.conflicting_line_ids) == {"line1", "line2"}
    assert not feature.has_baseline and feature.latest is None


def test_short_history_uses_direct_comparison():
    csv = HEADER + "\nT1,2026-09-01,P,Oil,10,135,100,90\nT2,2026-09-10,P,Oil,100,135,90,0\n"
    df = load_sales_csv(csv.encode()).df
    buys = [
        Purchase(date(2026, 9, d), cost, 10, f"line{i}", "src", f"I{i}", "S", 1, 1)
        for i, (d, cost) in enumerate([(1, 118), (10, 132)])
    ]
    features = build_features(df, {"P": buys})
    candidates = detect(features, df, {})
    assert any(c.candidate_type == "margin_leakage" and c.details["insufficient_history"] for c in candidates)


def test_claims_cover_sentences_and_reject_swapped_facts(completed):
    signal = next(s for s in repo.list_("signals", completed.run_id) if s["signal_type"] == "margin_leakage")
    evidence = {e["evidence_id"]: e for e in repo.list_("evidence", completed.run_id)}
    assert not validate_claims(signal, evidence, signal["facts"])
    altered = copy.deepcopy(signal)
    altered["claims"].pop()
    assert validate_claims(altered, evidence, altered["facts"])
    altered = copy.deepcopy(signal)
    altered["observation"] = altered["observation"].replace("rose", "fell")
    assert validate_claims(altered, evidence, altered["facts"])
    del evidence[signal["claims"][0]["evidence_ids"][0]]
    assert validate_claims(signal, evidence, signal["facts"])


def test_manual_matches_require_catalogue_and_compatible_size():
    products = [{"product_id": "P", "product_name": "Oil 1 L"}]
    with pytest.raises(ValueError, match="catalogue"):
        validate_decisions({"Oil 1 L": "fake"}, {"Oil 1 L"}, products)
    with pytest.raises(ValueError, match="conflict"):
        validate_decisions({"Oil 5 L": "P"}, {"Oil 5 L"}, products)
    with pytest.raises(ValueError, match="not part"):
        validate_decisions({"Other": None}, {"Oil 1 L"}, products)


def test_retry_keeps_corrections_and_original_extraction(completed):
    rid = completed.run_id
    invoice = repo.list_("invoices", rid)[0]
    sid = invoice["source_id"]
    first = client.put(f"/api/runs/{rid}/invoices/{sid}", json=correction_body(invoice))
    assert first.status_code == 200, first.text
    child = first.json()["run_id"]
    assert _wait(child)["status"] == "completed"
    matches = [m for m in repo.list_("matches", child) if m["status"] == "accepted"]
    decision = {matches[0]["line_description"]: matches[0]["product_id"]}
    second = client.post(f"/api/runs/{child}/matches", json={"decisions": decision})
    assert second.status_code == 200, second.text
    grandchild = second.json()["run_id"]
    assert _wait(grandchild)["status"] == "completed"
    retry = client.post(f"/api/runs/{grandchild}/retry").json()["run_id"]
    state = _wait(retry)
    assert state["status"] == "completed" and state["parent_run_id"] == grandchild
    retained = load_inputs(retry)
    assert retained.manual_matches == decision
    assert sid in retained.invoice_corrections
    assert repo.get("invoices", rid, sid)["extraction_method"] != "manual"
    assert repo.get("invoices", retry, sid)["extraction_method"] == "manual"
    assert repo.get("original_invoices", retry, sid)["invoice"] == invoice
    sources = client.get(f"/api/runs/{retry}/sources").json()
    assert len(sources["products"]) == 34
    assert sources["invoice_corrections"][sid]["reason"]


def test_invalid_correction_and_invalid_product_rejected(completed):
    rid = completed.run_id
    inv = repo.list_("invoices", rid)[0]
    body = correction_body(inv)
    body["invoice"]["line_items"][0]["unit_cost"] *= 2
    response = client.put(f"/api/runs/{rid}/invoices/{inv['source_id']}", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["issues"][0]["action"]
    response = client.post(f"/api/runs/{rid}/matches", json={"decisions": {"FAKE": "P"}})
    assert response.status_code == 422


def test_upload_limits_apply_to_both_endpoints(monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    for path in ("/api/uploads/validate-csv", "/api/runs"):
        files = [("sales_csv", ("sales.csv", b"x", "text/csv"))]
        if path.endswith("runs"):
            files.append(("invoices", ("x.pdf", b"%PDF", "application/pdf")))
        response = client.post(path, files=files)
        assert response.status_code == 413
        assert response.json()["detail"]["issues"][0]["file"] == "sales.csv"


def test_safe_filenames_and_failed_run_can_be_retried():
    inputs = demo_inputs()
    inputs.csv_name = "../../escaped.csv"
    inputs.pdfs = [("../../broken.pdf", b"%PDF broken"), inputs.pdfs[0]]
    inputs.cached_dir = None
    run = Run(inputs).execute()
    assert not (config.RUNTIME_DIR / "escaped.csv").exists()
    assert (repo.run_dir(run.run_id) / "escaped.csv").exists()
    assert any(i.code == "invoice_unreadable" for i in run.status.issues)
    assert not repo.list_("signals", run.run_id)
    inputs = demo_inputs()
    inputs.pdfs = [("broken.pdf", b"%PDF broken")]
    failed = Run(inputs).execute()
    assert failed.status.status == "failed" and failed.status.completed_stages
    retry = client.post(f"/api/runs/{failed.run_id}/retry")
    assert retry.status_code == 200
    assert _wait(retry.json()["run_id"])["status"] == "failed"


def test_structured_csv_errors_and_no_duplicate_sanitized_names():
    response = client.post("/api/uploads/validate-csv", files={"sales_csv": ("bad.csv", b"transaction_id\nT1")})
    body = response.json()
    assert not body["ok"] and body["issues"][0]["field"] == "transaction_date"
    inputs = demo_inputs()
    inputs.pdfs = [("a/one.pdf", inputs.pdfs[0][1]), ("b/one.pdf", inputs.pdfs[1][1])]
    with pytest.raises(ValueError, match="distinct"):
        Run(inputs)


def test_evaluation_does_not_replace_latest_analysis(completed):
    before = repo.latest_run_id()
    repo.put("runs", "evaluation", "latest", {"passed": True})
    assert repo.latest_run_id() == before


def test_pending_extraction_holds_financial_results_until_corrected(monkeypatch):
    extract = invoice_extract.extract_invoice

    def uncertain(*args, **kwargs):
        inv, warnings, method = extract(*args, **kwargs)
        if inv and inv.invoice_number == "SW-184":
            inv.validation_status = "needs_review"
            inv.line_items[0].validation_status = "needs_review"
            inv.line_items[0].extraction_confidence = 0.3
            warnings = [*warnings, "Confirm the supplier rate"]
        return inv, warnings, method

    monkeypatch.setattr("app.pipeline.run.extract_invoice", uncertain)
    run = Run(demo_inputs()).execute()
    assert run.status.status == "completed"
    assert any(i.code == "invoice_confirmation_required" for i in run.status.issues)
    assert not any(s["entity"]["id"] == "SKU-OIL-1L" for s in repo.list_("signals", run.run_id))
    inv = next(i for i in repo.list_("invoices", run.run_id) if i["invoice_number"] == "SW-184")
    response = client.put(f"/api/runs/{run.run_id}/invoices/{inv['source_id']}", json=correction_body(inv))
    assert response.status_code == 200, response.text
    child = response.json()["run_id"]
    assert _wait(child)["status"] == "completed"
    assert any(s["entity"]["id"] == "SKU-OIL-1L" for s in repo.list_("signals", child))


def test_multiple_manual_decisions_accumulate(completed):
    matches = [m for m in repo.list_("matches", completed.run_id) if m["status"] == "accepted"][:2]
    parent = completed.run_id
    expected = {}
    for m in matches:
        expected[m["line_description"]] = m["product_id"]
        response = client.post(f"/api/runs/{parent}/matches", json={"decisions": {m["line_description"]: m["product_id"]}})
        assert response.status_code == 200
        parent = response.json()["run_id"]
        assert _wait(parent)["status"] == "completed"
    assert load_inputs(parent).manual_matches == expected


def test_run_in_progress_rejects_retry(completed):
    stored = repo.get("runs", completed.run_id, completed.run_id)
    try:
        repo.put("runs", completed.run_id, completed.run_id, {**stored, "status": "running"})
        assert client.post(f"/api/runs/{completed.run_id}/retry").status_code == 409
    finally:
        repo.put("runs", completed.run_id, completed.run_id, stored)


def test_embedding_failure_is_disclosed(monkeypatch):
    import sys

    from app.pipeline import product_match

    monkeypatch.setenv("TREMOR_EMBEDDINGS", "1")
    monkeypatch.setattr(product_match, "_embedder", None)
    monkeypatch.setattr(product_match, "_embedding_failed", False)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    results = product_match.match_all(["Oil 1 L"], [{"product_id": "P", "product_name": "Oil 1 L"}])
    assert results["Oil 1 L"].semantic_backend == "fallback_lexicon"


def test_generated_contracts_are_current():
    import subprocess
    import sys

    subprocess.run([sys.executable, str(config.REPO_ROOT / "scripts/export_contracts.py"), "--check"], check=True)


def test_adding_bills_preserves_corrections_and_rejects_duplicate_names():
    d = config.DEMO_DIR
    files = [("sales_csv", ("sales.csv", (d / "sales_stock.csv").read_bytes(), "text/csv"))]
    files.append(("invoices", ("SW-151.pdf", (d / "invoices/SW-151.pdf").read_bytes(), "application/pdf")))
    rid = client.post("/api/runs", files=files).json()["run_id"]
    assert _wait(rid)["status"] == "completed"
    invoice = client.get(f"/api/runs/{rid}/sources").json()["invoices"][0]
    sid = invoice["source_id"]
    corrected = client.put(f"/api/runs/{rid}/invoices/{sid}", json=correction_body(invoice)).json()["run_id"]
    assert _wait(corrected)["status"] == "completed"
    bills = [("invoices", ("SW-184.pdf", (d / "invoices/SW-184.pdf").read_bytes(), "application/pdf"))]
    child = client.post(f"/api/runs/{corrected}/invoices", files=bills).json()["run_id"]
    state = _wait(child)
    assert state["status"] == "completed"
    assert state["parent_run_id"] == corrected
    assert state["summary"]["bills_uploaded"] == 2
    assert sid in load_inputs(child).invoice_corrections
    assert repo.get("invoices", child, sid)["extraction_method"] == "manual"
    assert client.post(f"/api/runs/{child}/invoices", files=bills).status_code == 422
