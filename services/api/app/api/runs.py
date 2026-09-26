from __future__ import annotations

import json

import pymupdf
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .. import config
from ..models.contracts import STAGES
from ..pipeline.ingest import load_sales_csv
from ..pipeline.run import Run, RunInputs, demo_inputs
from ..storage import repository as repo
from .signals import with_review_status

router = APIRouter(prefix="/api")


def _run_or_404(run_id: str) -> dict:
    if run_id == "latest":
        run_id = repo.latest_run_id() or ""
    r = repo.get("runs", run_id, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r


@router.post("/runs/demo")
def start_demo():
    run = Run(demo_inputs()).start_async()
    return {"run_id": run.run_id, "status": run.status.status, "stages": STAGES}


async def _read_pdfs(files: list[UploadFile], errors: list[dict]) -> list[tuple[str, bytes]]:
    pdfs = []
    for f in files:
        b = await f.read()
        if not (f.filename or "").lower().endswith(".pdf") or not b.startswith(b"%PDF"):
            errors.append({"file": f.filename, "error": "Not a PDF file"})
            continue
        if len(b) > config.MAX_UPLOAD_MB * 1024 * 1024:
            errors.append({"file": f.filename, "error": f"File is larger than {config.MAX_UPLOAD_MB} MB"})
            continue
        pdfs.append((f.filename, b))
    return pdfs


@router.post("/runs")
async def start_upload(sales_csv: UploadFile = File(...), invoices: list[UploadFile] | None = File(None)):
    """Supplier bills are optional: stock checks run on the sales file alone; margin checks need bills."""
    errors = []
    csv_bytes = await sales_csv.read()
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
    run = Run(
        RunInputs(mode="upload", csv_name=sales_csv.filename, csv_bytes=csv_bytes, pdfs=pdfs, store_name="Your store")
    ).start_async()
    return {"run_id": run.run_id, "status": run.status.status, "stages": STAGES}


@router.post("/uploads/validate-csv")
async def validate_csv(sales_csv: UploadFile = File(...)):
    res = load_sales_csv(await sales_csv.read())
    return {"ok": not res.errors, "errors": res.errors, "warnings": res.warnings, "summary": res.summary}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return _run_or_404(run_id)


@router.get("/runs/{run_id}/signals")
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


@router.get("/runs/{run_id}/sources")
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
    }


@router.get("/runs/{run_id}/features")
def list_features(run_id: str):
    run = _run_or_404(run_id)
    return {"run_id": run["run_id"], "features": repo.list_("features", run["run_id"])}


class MatchDecisions(BaseModel):
    decisions: dict[str, str | None]


def _inputs_from_run(run: dict) -> RunInputs:
    """Rebuild the inputs of an earlier run from its stored source files."""
    if run["mode"] == "demo":
        return demo_inputs()
    rdir = repo.run_dir(run["run_id"])
    sources = repo.list_("sources", run["run_id"])
    csv_src = next(s for s in sources if s["type"] == "sales_csv")
    pdfs = [(s["filename"], (rdir / s["filename"]).read_bytes()) for s in sources if s["type"] == "invoice_pdf"]
    return RunInputs(
        mode="upload",
        csv_name=csv_src["filename"],
        csv_bytes=(rdir / csv_src["filename"]).read_bytes(),
        pdfs=pdfs,
        store_name=run.get("store_name", "Your store"),
    )


@router.post("/runs/{run_id}/matches")
def confirm_matches(run_id: str, body: MatchDecisions):
    """Store manual match decisions and re-run the analysis with them (new run id)."""
    inp = _inputs_from_run(_run_or_404(run_id))
    inp.manual_matches = body.decisions
    new = Run(inp).start_async()
    return {"run_id": new.run_id, "status": new.status.status}


@router.post("/runs/{run_id}/invoices")
async def add_invoices(run_id: str, invoices: list[UploadFile] = File(...)):
    """Add supplier bills to an earlier analysis and re-run it with the same sales file (new run id)."""
    run = _run_or_404(run_id)
    if run["mode"] == "demo":
        raise HTTPException(422, "The sample store already includes its supplier bills")
    errors: list[dict] = []
    new_pdfs = await _read_pdfs(invoices, errors)
    if errors:
        raise HTTPException(422, {"errors": errors})
    if not new_pdfs:
        raise HTTPException(422, {"errors": [{"file": None, "error": "Choose at least one supplier bill PDF"}]})
    inp = _inputs_from_run(run)
    existing = {name for name, _ in inp.pdfs}
    inp.pdfs += [(name, b) for name, b in new_pdfs if name not in existing]
    new = Run(inp).start_async()
    return {"run_id": new.run_id, "status": new.status.status, "bills": len(inp.pdfs)}


@router.get("/sources/{run_id}/{source_id}/page/{page}.png")
def page_image(run_id: str, source_id: str, page: int, highlight: str | None = None):
    src = repo.get("sources", run_id, source_id)
    if not src or src["type"] != "invoice_pdf":
        raise HTTPException(404, "Invoice not found")
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
