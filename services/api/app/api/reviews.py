from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ..models.contracts import Review, ReviewIn
from ..pipeline.evaluate import run_evaluation
from ..storage import repository as repo

router = APIRouter(prefix="/api")


@router.post("/signals/{signal_id}/reviews")
def create_review(signal_id: str, body: ReviewIn):
    sig = repo.find("signals", signal_id)
    if not sig:
        raise HTTPException(404, "Signal not found")
    if body.outcome in ("confirmed", "dismissed") and len(body.reason.strip()) < 3:
        raise HTTPException(422, "A short reason is required to confirm or dismiss")
    review = Review(
        review_id=f"rev_{uuid.uuid4().hex[:10]}",
        signal_id=signal_id,
        run_id=sig["run_id"],
        outcome=body.outcome,
        reason=body.reason.strip(),
        created_at=datetime.now(UTC),
    )
    repo.put("reviews", sig["run_id"], review.review_id, review.model_dump(mode="json"))
    return review.model_dump(mode="json")


@router.get("/runs/{run_id}/reviews")
def list_reviews(run_id: str):
    if run_id == "latest":
        run_id = repo.latest_run_id() or ""
    sigs = {s["signal_id"]: s for s in repo.list_("signals", run_id)}
    out = []
    for r in sorted(repo.list_("reviews", run_id), key=lambda r: r["created_at"], reverse=True):
        s = sigs.get(r["signal_id"], {})
        out.append(
            {
                **r,
                "signal_title": s.get("title"),
                "severity": s.get("severity"),
                "amount": s.get("financial_impact", {}).get("amount"),
            }
        )
    return {"run_id": run_id, "reviews": out}


@router.post("/evaluation/demo")
def evaluation_demo():
    return run_evaluation()


@router.get("/evaluation/latest")
def evaluation_latest():
    rep = repo.get("runs", "evaluation", "latest")
    if not rep:
        raise HTTPException(404, "No evaluation has been run yet")
    return rep
