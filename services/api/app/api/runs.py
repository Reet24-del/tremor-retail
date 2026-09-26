from __future__ import annotations

import json

import pymupdf
from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from .. import config
from ..models.contracts import STAGES, InvoiceCorrection, MatchDecisions, RunStarted
from ..models.responses import CsvValidationResponse, RunResponse, SignalsResponse, SourcesResponse
from ..pipeline.ingest import load_sales_csv
from ..pipeline.invoice_extract import _build, read_pdf_rows
from ..pipeline.product_match import validate_decisions
from ..pipeline.retained import load_inputs, safe_filename
from ..pipeline.run import Run, RunInputs, demo_inputs, now
from ..storage import repository as repo
from .errors import data_issue
from .signals import with_review_status

router = APIRouter(prefix="/api")


async def _read_upload(upload: UploadFile) -> bytes:
    content = await upload.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            413, {"errors": [{"file": upload.filename, "error": f"File is larger than {config.MAX_UPLOAD_MB} MB"}]}
        )
    return content


def _run_or_404(run_id: str) -> dict:
    if run_id == "latest":
        run_id = repo.latest_run_id() or ""
    r = repo.get("runs", run_id, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r


@router.post("/runs/demo", response_model=RunStarted)
def start_demo():
    run = Run(demo_inputs()).start_async()
    return {"run_id": run.run_id, "status": run.status.status, "stages": STAGES}


async def _read_pdfs(files: list[UploadFile], errors: list[dict]) -> list[tuple[str, bytes]]:
    pdfs = []
    for f in files:
        b = await _read_upload(f)
        if not (f.filename or "").lower().endswith(".pdf") or not b.startswith(b"%PDF"):
            errors.append({"file": f.filename, "error": "Not a PDF file"})
            continue
        if len(b) > config.MAX_UPLOAD_MB * 1024 * 1024:
            errors.append({"file": f.filename, "error": f"File is larger than {config.MAX_UPLOAD_MB} MB"})
            continue
        pdfs.append((f.filename, b))
    return pdfs


@router.post("/runs", response_model=RunStarted)
async def start_upload(sales_csv: UploadFile = File(...), invoices: list[UploadFile] | None = File(None)):
    """Supplier bills are optional: stock checks run on the sales file alone; margin checks need bills."""
    errors = []
    csv_bytes = await _read_upload(sales_csv)
    if len(csv_bytes) > config.MAX_UPLOAD_MB * 1024 * 1024:
        errors.append({"file": sales_csv.filename, "error": f"File is larger than {config.MAX_UPLOAD_MB} MB"})
    if not (sales_csv.filename or "").lower().endswith(".csv"):
        errors.append({"file": sales_csv.filename, "error": "Sales and stock file must be a .csv"})
    csv_check = load_sales_csv(csv_bytes)
    for e in csv_check.errors:
        errors.append({"file": sales_csv.filename, "error": e})
    pdfs = await _read_pdfs(invoices or [], errors)
    if errors:
        raise HTTPException(422, {"errors": errors, "csv_summary": csv_check.summary, "warnings": csv_check.warnings})
    try:
        names = [safe_filename(sales_csv.filename), *[safe_filename(n) for n, _ in pdfs]]
        if len(set(n.lower() for n in names)) != len(names):
            raise ValueError("Uploaded filenames must be distinct after normalization")
        run = Run(
            RunInputs(
                mode="upload",
                csv_name=names[0],
                csv_bytes=csv_bytes,
                pdfs=list(zip(names[1:], [b for _, b in pdfs], strict=True)),
                store_name="Your store",
            )
        ).start_async()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"run_id": run.run_id, "status": run.status.status, "stages": STAGES}


@router.post("/uploads/validate-csv", response_model=CsvValidationResponse)
async def validate_csv(sales_csv: UploadFile = File(...)):
    content = await _read_upload(sales_csv)
    if not (sales_csv.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, {"errors": [{"file": sales_csv.filename, "error": "Expected a .csv file"}]})
    res = load_sales_csv(content)
    return {
        "ok": not res.errors,
        "errors": res.errors,
        "warnings": res.warnings,
        "summary": res.summary,
        "issues": [data_issue(e, sales_csv.filename) for e in res.errors],
    }


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str):
    return _run_or_404(run_id)


@router.get("/runs/{run_id}/signals", response_model=SignalsResponse)
def list_signals(run_id: str):
    run = _run_or_404(run_id)
    sigs = [with_review_status(s) for s in repo.list_("signals", run["run_id"])]
    order = {"high": 0, "medium": 1, "low": 2}
    sigs.sort(key=lambda s: (order[s["severity"]], -s["financial_impact"]["amount"]))
    summary_keys = [
        "signal_id",
        "run_id",
        "signal_type",
        "status",
        "severity",
        "evidence_strength",
        "entity",
        "title",
        "observation",
        "financial_impact",
        "model_metadata",
    ]
    return {
        "run_id": run["run_id"],
        "run_status": run["status"],
        "issues": run.get("issues", []),
        "signals": [
            {
                **{k: s[k] for k in summary_keys},
                "translations": {
                    lang: {k: t[k] for k in ("title", "observation", "impact_label") if k in t}
                    for lang, t in s.get("translations", {}).items()
                },
            }
            for s in sigs
        ],
        "rejected_candidates": repo.list_("candidates", run["run_id"]),
    }


@router.get("/runs/{run_id}/sources", response_model=SourcesResponse)
def list_sources(run_id: str):
    run = _run_or_404(run_id)
    sources = repo.list_("sources", run["run_id"])
    for s in sources:
        s["summary"] = {k: v for k, v in s.get("summary", {}).items() if k != "path"}
    return {
        "run_id": run["run_id"],
        "sources": sources,
        "matches": repo.list_("matches", run["run_id"]),
        "invoices": repo.list_("invoices", run["run_id"]),
        "original_invoices": repo.list_("original_invoices", run["run_id"]),
        "products": repo.list_("products", run["run_id"]),
        "issues": run.get("issues", []),
        "invoice_corrections": (repo.get("inputs", run["run_id"], "manifest") or {}).get("invoice_corrections", {}),
        "manual_matches": (repo.get("inputs", run["run_id"], "manifest") or {}).get("manual_matches", {}),
    }


@router.get("/runs/{run_id}/features")
def list_features(run_id: str):
    run = _run_or_404(run_id)
    return {"run_id": run["run_id"], "features": repo.list_("features", run["run_id"])}


def _editable_inputs(run_id):
    run = _run_or_404(run_id)
    if run["status"] == "running":
        raise HTTPException(409, "Wait for the current run to finish before retrying or correcting it")
    try:
        return run, load_inputs(run["run_id"])
    except (ValueError, OSError):
        raise HTTPException(409, "Retained inputs are unavailable; upload the files again") from None


def _start_child(inputs):
    child = Run(inputs).start_async()
    return {"run_id": child.run_id, "status": child.status.status, "stages": STAGES, "parent_run_id": inputs.parent_run_id}


@router.post("/runs/{run_id}/retry", response_model=RunStarted)
def retry_run(run_id: str):
    _, inputs = _editable_inputs(run_id)
    return _start_child(inputs)


@router.post("/runs/{run_id}/matches", response_model=RunStarted)
def confirm_matches(run_id: str, body: MatchDecisions):
    run, inputs = _editable_inputs(run_id)
    matches = repo.list_("matches", run["run_id"])
    products = repo.list_("products", run["run_id"])
    try:
        validate_decisions(body.decisions, {m["line_description"] for m in matches}, products)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    inputs.manual_matches.update(body.decisions)
    return _start_child(inputs)


@router.put("/runs/{run_id}/invoices/{source_id}", response_model=RunStarted)
def correct_invoice(run_id: str, source_id: str, body: InvoiceCorrection):
    run, inputs = _editable_inputs(run_id)
    src = repo.get("sources", run["run_id"], source_id)
    if not src or src["type"] != "invoice_pdf":
        raise HTTPException(404, "Invoice source not found")
    content = dict(inputs.pdfs)[src["filename"]]
    try:
        rows, _ = read_pdf_rows(content)
        corrected, warnings = _build(source_id, body.invoice.model_dump(mode="json"), rows, "manual", confirmed=True)
    except Exception:
        raise HTTPException(422, "The PDF cannot be read; replace it before correcting fields") from None
    if corrected is None:
        raise HTTPException(422, {"errors": [{"file": src["filename"], "error": w} for w in warnings]})
    inputs.invoice_corrections[source_id] = {
        "invoice": body.invoice.model_dump(mode="json"),
        "reason": body.reason,
        "confirmed_at": now().isoformat(),
    }
    return _start_child(inputs)


@router.post("/runs/{run_id}/invoices", response_model=RunStarted)
async def add_invoices(run_id: str, invoices: list[UploadFile] = File(...)):
    """Add supplier bills to an earlier analysis and re-run it with the same sales file (new run id)."""
    run, inp = _editable_inputs(run_id)
    if run["mode"] == "demo":
        raise HTTPException(422, "The sample store already includes its supplier bills")
    errors: list[dict] = []
    new_pdfs = await _read_pdfs(invoices, errors)
    if errors:
        raise HTTPException(422, {"errors": errors})
    if not new_pdfs:
        raise HTTPException(422, {"errors": [{"file": None, "error": "Choose at least one supplier bill PDF"}]})
    try:
        new_pdfs = [(safe_filename(name), content) for name, content in new_pdfs]
        names = [inp.csv_name, *[name for name, _ in inp.pdfs], *[name for name, _ in new_pdfs]]
        if len({name.lower() for name in names}) != len(names):
            raise ValueError("Uploaded filenames must be distinct after normalization")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    inp.pdfs += new_pdfs
    return _start_child(inp)


@router.get("/sources/{run_id}/{source_id}/page/{page}.png")
def page_image(run_id: str, source_id: str, page: int, highlight: str | None = None):
    src = repo.get("sources", run_id, source_id)
    if not src or src["type"] != "invoice_pdf":
        raise HTTPException(404, "Invoice not found")
    if page < 1:
        raise HTTPException(404, "Page numbers start at one")
    path = src["summary"].get("path")
    try:
        doc = pymupdf.open(path)
        pg = doc[page - 1]
    except Exception:
        raise HTTPException(404, "Page not found") from None
    if highlight:
        try:
            x0, y0, x1, y1 = [float(v) for v in highlight.split(",")]
            annot = pg.add_rect_annot(pymupdf.Rect(x0 - 3, y0 - 2, x1 + 3, y1 + 2))
            annot.set_colors(stroke=(0.85, 0.2, 0.15), fill=(1, 0.85, 0.2))
            annot.set_opacity(0.35)
            annot.update()
        except ValueError:
            raise HTTPException(400, "highlight must be x0,y0,x1,y1") from None
    png = pg.get_pixmap(dpi=110).tobytes("png")
    doc.close()
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/runs")
def list_runs():
    rid = repo.latest_run_id()
    return {"latest_run_id": rid}


@router.get("/demo/sample-csv")
def sample_csv():
    head = (config.DEMO_DIR / "sales_stock.csv").read_text().splitlines()[:11]
    return Response(
        "\n".join(head) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tremor_sales_stock_example.csv"},
    )


@router.get("/demo/labels")
def demo_labels():
    return json.loads((config.DEMO_DIR / "labels" / "signals.json").read_text())
