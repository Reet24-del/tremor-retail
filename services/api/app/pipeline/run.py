"""Run controller: one repeatable pipeline execution with visible stages (PRD 8.3, 14.2)."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .. import config
from ..models.contracts import STAGES, DataIssue, Invoice, RunStatus, Source
from ..storage import repository as repo
from . import llm
from .claims import build_claims, financial_impact
from .correlate import build_signal_drafts
from .detect import detect
from .explain import explain, severity_for
from .explain_hi import translate_hi
from .features import Purchase, build_features
from .ingest import load_sales_csv
from .invoice_extract import _build, extract_invoice, read_pdf_rows
from .product_match import match_all
from .retained import save_inputs
from .validate_signal import validate

DATASET_DEMO = "demo-fixture-v1"


@dataclass
class RunInputs:
    mode: str
    csv_name: str
    csv_bytes: bytes
    pdfs: list[tuple[str, bytes]]
    calendar: dict = field(default_factory=dict)
    store_name: str = "Your store"
    cached_dir: Path | None = None
    frozen_matches: dict | None = None
    manual_matches: dict = field(default_factory=dict)
    dataset_version: str = "upload"
    invoice_corrections: dict = field(default_factory=dict)
    original_extractions: dict = field(default_factory=dict)
    parent_run_id: str | None = None


def now() -> datetime:
    return datetime.now(UTC)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower()).strip("_")


def demo_inputs(data_dir: Path | None = None) -> RunInputs:
    """Inputs for a bundled synthetic store. Defaults to the frozen demo fixture."""
    d = data_dir or config.DEMO_DIR
    frozen = {
        p["raw_description"]: p["product_id"] for p in json.loads((d / "labels" / "product_matches.json").read_text())["pairs"]
    }
    cal = json.loads((d / "calendar.json").read_text())
    return RunInputs(
        mode="demo",
        csv_name="sales_stock.csv",
        csv_bytes=(d / "sales_stock.csv").read_bytes(),
        pdfs=[(p.name, p.read_bytes()) for p in sorted((d / "invoices").glob("*.pdf"))],
        calendar=cal,
        store_name=cal.get("store", "Sample grocery store"),
        cached_dir=d / "cached_extraction",
        frozen_matches=frozen,
        dataset_version=json.loads((d / "labels" / "signals.json").read_text()).get("dataset_version", DATASET_DEMO),
    )


class Run:
    def __init__(self, inputs: RunInputs, run_id: str | None = None):
        self.inputs = inputs
        self.run_id = run_id or f"run_{now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        self.status = RunStatus(
            run_id=self.run_id,
            mode=inputs.mode,
            status="running",
            current_stage=STAGES[0],
            completed_stages=[],
            started_at=now(),
            dataset_version=inputs.dataset_version,
            configuration_version=config.CONFIG_VERSION,
            store_name=inputs.store_name,
            parent_run_id=inputs.parent_run_id,
        )
        save_inputs(self.run_id, inputs)
        self.status.retryable = True
        self._save_status()

    def _save_status(self):
        repo.put("runs", self.run_id, self.run_id, self.status.model_dump(mode="json"))

    def _stage(self, name: str):
        if self.status.current_stage and self.status.current_stage != name:
            self.status.completed_stages.append(self.status.current_stage)
        self.status.current_stage = name
        self._save_status()

    def start_async(self):
        threading.Thread(target=self.execute, daemon=True).start()
        return self

    def execute(self):
        try:
            self._execute()
        except Exception as exc:
            self.status.status = "failed"
            self.status.failed_stage = self.status.current_stage
            self.status.error = "Analysis failed at " + str(self.status.current_stage)
            if isinstance(exc, ValueError):
                self.status.error += f": {exc}"
            self.status.issues.append(
                DataIssue(
                    code="pipeline_failed",
                    message=self.status.error,
                    action="Correct the indicated data or retry the retained inputs",
                )
            )
            self.status.completed_at = now()
            self._save_status()
        return self

    def _execute(self):
        inp, rid = self.inputs, self.run_id
        rdir = repo.run_dir(rid)

        # 1. Validating records
        self._stage("validating_records")
        csv_res = load_sales_csv(inp.csv_bytes)
        csv_id = f"src_{_slug(inp.csv_name)}"
        (rdir / inp.csv_name).write_bytes(inp.csv_bytes)
        repo.put(
            "sources",
            rid,
            csv_id,
            Source(
                source_id=csv_id,
                type="sales_csv",
                filename=inp.csv_name,
                content_hash=hashlib.sha256(inp.csv_bytes).hexdigest(),
                uploaded_at=now(),
                row_count=csv_res.summary.get("row_count"),
                status="error" if csv_res.errors else ("warning" if csv_res.warnings else "ok"),
                messages=csv_res.errors + csv_res.warnings,
                summary=csv_res.summary,
            ).model_dump(mode="json"),
        )
        if csv_res.errors:
            raise ValueError("Sales CSV failed validation: " + "; ".join(csv_res.errors[:3]))
        self.status.warnings += csv_res.warnings
        df = csv_res.df

        # 2. Reading supplier bills
        self._stage("reading_supplier_bills")
        invoices, line_index, methods = [], {}, set()
        unreadable = False
        for name, content in inp.pdfs:
            sid = f"src_{_slug(name)}_{hashlib.sha256(name.encode()).hexdigest()[:8]}"
            path = rdir / name
            path.write_bytes(content)
            cached = (inp.cached_dir / f"{Path(name).stem}.json") if inp.cached_dir else None
            original = inp.original_extractions.get(sid)
            if original:
                inv = Invoice.model_validate(original["invoice"])
                warns, method = original["warnings"], original["method"]
            else:
                inv, warns, method = extract_invoice(sid, content, cached)
                original = {
                    "source_id": sid,
                    "invoice": inv.model_dump(mode="json") if inv else None,
                    "warnings": warns,
                    "method": method,
                }
            repo.put("original_invoices", rid, sid, original)
            correction = inp.invoice_corrections.get(sid)
            try:
                pdf_rows, pages = read_pdf_rows(content)
            except Exception:
                pdf_rows, pages = [], 0
            if correction:
                inv, warns = _build(sid, correction["invoice"], pdf_rows, "manual", confirmed=True)
                method = "manual"
            methods.add(method)
            repo.put(
                "sources",
                rid,
                sid,
                Source(
                    source_id=sid,
                    type="invoice_pdf",
                    filename=name,
                    content_hash=hashlib.sha256(content).hexdigest(),
                    uploaded_at=now(),
                    page_count=pages,
                    status="error" if inv is None else ("warning" if warns or inv.validation_status == "needs_review" else "ok"),
                    messages=warns,
                    summary={
                        "path": str(path),
                        "extraction_method": method,
                        "supplier_name": inv.supplier_name if inv else None,
                        "invoice_number": inv.invoice_number if inv else None,
                        "invoice_date": str(inv.invoice_date) if inv else None,
                        "line_count": len(inv.line_items) if inv else 0,
                    },
                ).model_dump(mode="json"),
            )
            if inv is None or inv.validation_status == "needs_review":
                self.status.issues.append(
                    DataIssue(
                        code="invoice_unreadable" if inv is None else "invoice_confirmation_required",
                        message="; ".join(warns) or "Invoice fields require confirmation",
                        action="Replace the PDF" if inv is None else "Confirm or correct the invoice fields",
                        file=name,
                        source_id=sid,
                        field="invoice",
                        status="needs_data" if inv is None else "needs_review",
                    )
                )
            if inv is None:
                unreadable = True
                self.status.warnings.append(f"{name}: could not be read; excluded from analysis")
                continue
            invoices.append(inv)
            repo.put("invoices", rid, sid, inv.model_dump(mode="json"))
            for line in inv.line_items:
                line_index[line.line_id] = (inv, line)
        if not invoices and self.inputs.pdfs:
            raise ValueError("No supplier invoices could be read; upload readable digital PDFs")
        if not invoices:
            self.status.warnings.append(
                "No supplier bills were used: stock was checked from the sales file alone and margin checks were skipped."
            )
        if invoices and len({i.invoice_date for i in invoices}) < 2:
            self.status.warnings.append("Only one invoice date: cost changes cannot be established without a baseline")

        # 3. Matching products
        self._stage("matching_products")
        products = df[["product_id", "product_name"]].drop_duplicates("product_id").to_dict("records")
        repo.put_many("products", rid, {p["product_id"]: p for p in products})
        matches = match_all(
            [line.raw_description for i in invoices for line in i.line_items],
            products,
            frozen=inp.frozen_matches,
            manual=inp.manual_matches,
        )
        if any(m.semantic_backend == "fallback_lexicon" for m in matches.values()):
            self.status.warnings.append("Embedding model unavailable; using explicitly labelled lexicon matching")
        repo.put_many("matches", rid, {m.match_id: m.model_dump(mode="json") for m in matches.values()})

        # 4. Calculating financial features
        self._stage("calculating_features")
        purchases: dict[str, list[Purchase]] = {}
        held_products = set()
        for inv in invoices:
            for line in inv.line_items:
                m = matches[line.raw_description]
                if inv.validation_status == "needs_review" or line.validation_status == "needs_review":
                    if m.product_id:
                        held_products.add(m.product_id)
                    continue
                if m.status == "accepted" and m.product_id:
                    purchases.setdefault(m.product_id, []).append(
                        Purchase(
                            inv.invoice_date,
                            line.unit_cost,
                            line.quantity,
                            line.line_id,
                            inv.source_id,
                            inv.invoice_number,
                            inv.supplier_name,
                            line.extraction_confidence,
                            m.confidence,
                        )
                    )
        features = build_features(df, purchases)
        for m in matches.values():
            if m.status in ("needs_review", "unmatched", "blocked"):
                self.status.issues.append(
                    DataIssue(
                        code="product_match_required",
                        message=m.reason or "Product is unmatched",
                        action="Select a compatible product or leave the line unmatched",
                        field="product_id",
                        product_id=m.product_id,
                        status="needs_review",
                    )
                )
        for pid, feature in features.items():
            if feature.conflicting_line_ids:
                held_products.add(pid)
                self.status.issues.append(
                    DataIssue(
                        code="conflicting_invoice_costs",
                        message="Different costs on the same date",
                        action="Inspect and correct the cited invoices; no cost is selected automatically",
                        product_id=pid,
                        line_ids=feature.conflicting_line_ids,
                        status="unresolved",
                    )
                )
            elif not feature.has_baseline:
                self.status.issues.append(
                    DataIssue(
                        code="missing_baseline",
                        message="Two distinct invoice dates are required",
                        action="Supply an earlier and a current invoice for this product",
                        product_id=pid,
                    )
                )
            if feature.days < 7:
                self.status.issues.append(
                    DataIssue(
                        code="insufficient_history",
                        message="Fewer than seven days of sales history",
                        action="Supply more history; only a direct cost comparison is available",
                        product_id=pid,
                    )
                )
        repo.put_many("features", rid, {pid: f.as_row() for pid, f in features.items()})

        # 5. Finding unusual changes
        self._stage("finding_unusual_changes")
        pending = {m.product_id for m in matches.values() if m.status != "accepted" and m.product_id}
        held_products |= pending
        pending |= held_products
        # Unknown deliveries can create false stock shortages for any product.
        unknown_deliveries = unreadable or any(m.status == "unmatched" and m.method != "manual" for m in matches.values())
        stock_pending = set(features) if unknown_deliveries else pending
        cands = detect(features, df, inp.calendar, pending_products=stock_pending)
        for candidate in cands:
            if unreadable or set(candidate.product_ids) & held_products:
                candidate.rejected_reason = "Needs data: resolve invoice extraction or conflicting costs before publication"

        # 6. Linking evidence
        self._stage("linking_evidence")
        drafts, evidence, rejected = build_signal_drafts(rid, cands, features, df, csv_id, inp.calendar)
        for ev in evidence.values():
            if ev["source_type"] == "invoice_pdf":
                inv, line = line_index[ev["locator"]["line_id"]]
                ev["locator"] = {
                    "line_id": line.line_id,
                    "page": line.page_number,
                    "bbox": line.bbox,
                    "source_text": line.source_text,
                }
                ev["excerpt"] = {
                    "supplier_name": inv.supplier_name,
                    "invoice_number": inv.invoice_number,
                    "invoice_date": str(inv.invoice_date),
                    **line.model_dump(mode="json"),
                    "extraction_method": inv.extraction_method,
                    "match": matches[line.raw_description].model_dump(mode="json"),
                }

        # 7. Preparing signals
        self._stage("preparing_signals")
        published, used_evidence = {}, {}
        for d in drafts:
            c, f, facts = d["candidate"], d["features"], d["facts"]
            text, source, notes = explain(c.candidate_type, facts)
            self.status.warnings += notes
            ev_ids = d["evidence_ids"]
            comps = {
                "extraction_confidence": round(min([p.confidence for p in f.purchases], default=0), 2),
                "match_confidence": round(min([p.match_confidence for p in f.purchases], default=0), 2),
                "source_corroboration": 1.0
                if len({evidence[e]["source_type"] for e in ev_ids} & {"sales_csv", "invoice_pdf"}) == 2
                else 0.5,
                "data_completeness": round(f.completeness, 2),
                "anomaly_strength": round(min(abs(c.anomaly_score) / 6.0, 1.0), 2),
            }
            impact = financial_impact(c.candidate_type, facts)
            limitations = [
                "Synthetic demo data" if inp.mode == "demo" else "Based only on the uploaded files",
                "Excludes tax, delivery charges, rebates and damaged stock unless recorded in the files",
                "Estimated amounts compare with the prior purchase cost; they are not an accounting loss",
            ]
            if f.days < 7:
                limitations.append("Insufficient history: direct cost comparison, not a statistical trend")
            if "cached" in {
                evidence[e].get("excerpt", {}).get("extraction_method")
                for e in ev_ids
                if evidence[e]["source_type"] == "invoice_pdf"
            }:
                limitations.append("Invoice fields come from cached validated extraction (verified against the PDF text)")
            if c.candidate_type == "inventory_discrepancy" and f.stock_mode == "inferred":
                limitations.append(
                    "Checked from the sales and stock file alone: deliveries were inferred from stock increases. "
                    "Add this supplier's bills to confirm."
                )
            hindi, hi_notes = translate_hi(c.candidate_type, facts, limitations, impact["label"])
            self.status.warnings.extend(f"{f.product_name}: {n}" for n in hi_notes)
            sig = {
                "signal_id": d["signal_id"],
                "run_id": rid,
                "signal_type": c.candidate_type,
                "status": "new",
                "severity": severity_for(c.candidate_type, facts),
                "evidence_strength": round(sum(comps.values()) / len(comps), 2),
                "evidence_strength_components": comps,
                "entity": {"type": "product", "id": f.product_id, "display_name": f.product_name},
                **text,
                "financial_impact": impact,
                "evidence_ids": ev_ids,
                "rejected_explanations": d["rejected_explanations"],
                "limitations": limitations,
                "facts": facts,
                "ranking": c.ranking,
                "model_metadata": {
                    "detector_version": config.DETECTOR_VERSION,
                    "prompt_version": config.PROMPT_VERSION,
                    "model_name": llm.model_name(),
                    "explanation_source": source,
                    "extraction_method": ",".join(sorted(methods)),
                },
                "translations": {"hi": hindi} if hindi else {},
            }
            sig["claims"] = build_claims(sig)
            ok, problems = validate(sig, evidence, facts)
            if ok is None:
                self.status.warnings.append(f"Signal for {f.product_name} blocked from publication: {'; '.join(problems)}")
                continue
            published[ok.signal_id] = ok.model_dump(mode="json")
            for e in ev_ids + [x for a in d["rejected_explanations"] for x in a["evidence_ids"]]:
                used_evidence[e] = evidence[e]
        repo.put_many("signals", rid, published)
        repo.put_many("evidence", rid, used_evidence)
        repo.put_many("candidates", rid, {r.candidate_id: r.model_dump(mode="json") for r in rejected})

        self.status.summary = {
            "records_analysed": len(df),
            "products": int(df["product_id"].nunique()),
            "invoices_read": len(invoices),
            "invoice_lines": len(line_index),
            "date_from": csv_res.summary["date_from"],
            "date_to": csv_res.summary["date_to"],
            "signals": len(published),
            "rejected_candidates": len(rejected),
            "amount_requiring_investigation": round(sum(s["financial_impact"]["amount"] for s in published.values()), 2),
            "extraction_methods": sorted(methods),
            "bills_uploaded": len(invoices),
            "margin_check": (
                "skipped_no_bills"
                if not invoices
                else ("needs_more_bills" if len({i.invoice_date for i in invoices}) < 2 else "done")
            ),
            "llm_enabled": llm.enabled(),
            "issue_count": len(self.status.issues),
            "ready_for_review": bool(self.status.issues),
            "matches": {
                s: sum(1 for m in matches.values() if m.status == s) for s in ("accepted", "needs_review", "unmatched", "blocked")
            },
        }
        self.status.completed_stages.append("preparing_signals")
        self.status.current_stage = None
        self.status.status = "completed"
        self.status.completed_at = now()
        self._save_status()
