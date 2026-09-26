from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.responses import EvidenceResponse, SignalDetail
from ..storage import repository as repo

router = APIRouter(prefix="/api")


def latest_review(run_id: str, signal_id: str) -> dict | None:
    reviews = [r for r in repo.list_("reviews", run_id) if r["signal_id"] == signal_id]
    return sorted(reviews, key=lambda r: r["created_at"])[-1] if reviews else None


def with_review_status(sig: dict) -> dict:
    r = latest_review(sig["run_id"], sig["signal_id"])
    if r:
        sig = {**sig, "status": r["outcome"]}
    return sig


@router.get("/signals/{signal_id}", response_model=SignalDetail)
def get_signal(signal_id: str):
    sig = repo.find("signals", signal_id)
    if not sig:
        raise HTTPException(404, "Signal not found")
    sig = with_review_status(sig)
    ids = list(dict.fromkeys(sig["evidence_ids"] + [e for a in sig["rejected_explanations"] for e in a["evidence_ids"]]))
    evidence = {}
    for e in ids:
        doc = repo.get("evidence", sig["run_id"], e)
        if doc:
            evidence[e] = {k: doc[k] for k in ("evidence_id", "source_id", "source_type", "label", "locator")}
    reviews = sorted(
        [r for r in repo.list_("reviews", sig["run_id"]) if r["signal_id"] == signal_id],
        key=lambda r: r["created_at"],
        reverse=True,
    )
    return {"signal": sig, "evidence": evidence, "reviews": reviews}


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str):
    doc = repo.find("evidence", evidence_id)
    if not doc:
        raise HTTPException(404, "Evidence not found")
    if doc["source_type"] == "invoice_pdf":
        loc = doc["locator"]
        bbox = ",".join(str(v) for v in (loc.get("bbox") or []))
        run_id = repo.find("signals", doc["signal_id"])["run_id"]
        doc = {
            **doc,
            "page_image_url": f"/api/sources/{run_id}/{doc['source_id']}/page/{loc['page']}.png"
            + (f"?highlight={bbox}" if bbox else ""),
        }
    return doc
