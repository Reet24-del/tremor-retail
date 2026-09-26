"""Integration tests: demo run -> signals -> evidence -> review -> evaluation."""

import os
import tempfile
import time

os.environ["TREMOR_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="tremor_test_")
os.environ["TREMOR_DISABLE_LLM"] = "1"

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def _wait(run_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(0.3)
    raise AssertionError("run did not finish")


def test_demo_run_produces_hero_signal_with_evidence():
    run_id = client.post("/api/runs/demo").json()["run_id"]
    run = _wait(run_id)
    assert run["status"] == "completed", run
    assert run["completed_stages"][-1] == "preparing_signals"

    feed = client.get(f"/api/runs/{run_id}/signals").json()
    sigs = feed["signals"]
    assert len(sigs) == 5
    top = sigs[0]
    assert top["entity"]["id"] == "SKU-OIL-1L" and top["severity"] == "high"
    assert top["financial_impact"]["amount"] == 1680
    assert {c["candidate_type"] for c in feed["rejected_candidates"]} == {"sales_spike", "purchase_spike"}

    detail = client.get(f"/api/signals/{top['signal_id']}").json()
    sig = detail["signal"]
    assert sig["facts"]["prior_margin_percent"] == 12.6 and sig["facts"]["current_margin_percent"] == 2.2
    assert sig["facts"]["stock_variance_units"] == -12
    assert any(a["name"] == "a temporary promotion" for a in sig["rejected_explanations"])
    for eid in sig["evidence_ids"]:
        ev = client.get(f"/api/evidence/{eid}").json()
        assert ev["evidence_id"] == eid
        if ev["source_type"] == "invoice_pdf":
            assert (ev["locator"]["page"] >= 1 and "132" in ev["locator"]["source_text"]) or "118" in ev["locator"]["source_text"]
            img = client.get(ev["page_image_url"])
            assert img.status_code == 200 and img.headers["content-type"] == "image/png"
        if ev["source_type"] == "sales_csv":
            assert all("source_row" in r for r in (ev["excerpt"] if isinstance(ev["excerpt"], list) else ev["excerpt"]["rows"]))

    # review never changes source data, requires a reason
    assert client.post(f"/api/signals/{top['signal_id']}/reviews", json={"outcome": "confirmed", "reason": ""}).status_code == 422
    r = client.post(f"/api/signals/{top['signal_id']}/reviews", json={"outcome": "confirmed", "reason": "Supplier rate verified"})
    assert r.status_code == 200
    assert client.get(f"/api/signals/{top['signal_id']}").json()["signal"]["status"] == "confirmed"
    assert client.get(f"/api/runs/{run_id}/reviews").json()["reviews"][0]["outcome"] == "confirmed"
    sources = client.get(f"/api/runs/{run_id}/sources").json()
    assert len([s for s in sources["sources"] if s["type"] == "invoice_pdf"]) == 10


def test_upload_rejects_bad_files_with_named_errors():
    r = client.post(
        "/api/runs",
        files=[("sales_csv", ("s.csv", b"transaction_id\nA\n", "text/csv")), ("invoices", ("a.txt", b"hello", "text/plain"))],
    )
    assert r.status_code == 422
    errs = r.json()["detail"]["errors"]
    assert any("product_id" in e["error"] for e in errs)
    assert any(e["error"] == "Not a PDF file" for e in errs)


def test_upload_run_uses_real_extraction():
    d = config.DEMO_DIR
    files = [("sales_csv", ("sales_stock.csv", (d / "sales_stock.csv").read_bytes(), "text/csv"))]
    for name in ("SW-151.pdf", "SW-184.pdf"):
        files.append(("invoices", (name, (d / "invoices" / name).read_bytes(), "application/pdf")))
    run_id = client.post("/api/runs", files=files).json()["run_id"]
    run = _wait(run_id)
    assert run["status"] == "completed"
    assert run["summary"]["extraction_methods"] == ["heuristic"]
    ids = {s["entity"]["id"] for s in client.get(f"/api/runs/{run_id}/signals").json()["signals"]}
    assert "SKU-OIL-1L" in ids


def test_evaluation_passes_targets():
    rep = client.post("/api/evaluation/demo").json()
    assert rep["passed"], rep["metrics"]
    assert rep["metrics"]["recall"]["count"] == "5 of 5"
    assert rep["metrics"]["safety_violations"]["value"] == 0
