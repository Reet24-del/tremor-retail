"""Frozen evaluation (PRD 9.7, 17.4).

Runs the real pipeline on the demo fixture WITHOUT cached extraction and WITHOUT frozen matches,
so the numbers measure the system, then compares against labels.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .. import config
from ..safety.policy import prohibited_phrases
from ..storage import repository as repo
from . import llm
from .claims import validate_claims
from .run import Run, demo_inputs


def run_evaluation(data_dir: Path | None = None, persist: bool = True) -> dict:
    """Evaluate the real pipeline on one labelled synthetic store (the frozen demo by default)."""
    labels_dir = (data_dir or config.DEMO_DIR) / "labels"
    planted = json.loads((labels_dir / "signals.json").read_text())
    truth = json.loads((labels_dir / "invoices_truth.json").read_text())
    match_labels = {
        p["raw_description"]: p["product_id"] for p in json.loads((labels_dir / "product_matches.json").read_text())["pairs"]
    }

    inp = demo_inputs(data_dir)
    inp.cached_dir = None
    inp.frozen_matches = None
    inp.mode = "demo"
    run = Run(inp).execute()
    rid = run.run_id
    if run.status.status != "completed":
        return {"run_id": rid, "status": "failed", "error": run.status.error}

    signals = repo.list_("signals", rid)
    evidence = {e["evidence_id"]: e for e in repo.list_("evidence", rid)}
    rejected = repo.list_("candidates", rid)
    invoices = {i["invoice_number"]: i for i in repo.list_("invoices", rid)}
    matches = {m["line_description"]: m for m in repo.list_("matches", rid)}

    # Signal detection
    published = {(s["signal_type"], s["entity"]["id"]): s for s in signals}
    rows, tp = [], 0
    for p in planted["planted_signals"]:
        s = published.get((p["signal_type"], p["product_id"]))
        ev_ok = bool(s) and all(e in evidence for e in s["evidence_ids"])
        sev_ok = bool(s) and s["severity"] == p["expected_severity"]
        tp += 1 if s else 0
        rows.append(
            {
                "id": p["id"],
                "kind": "planted",
                "entity": p["product_id"],
                "expected": p["signal_type"],
                "actual": s["signal_type"] if s else "not detected",
                "detected": bool(s),
                "severity_expected": p["expected_severity"],
                "severity_actual": s["severity"] if s else None,
                "severity_ok": sev_ok,
                "evidence_status": "resolved" if ev_ok else ("missing" if s else "n/a"),
                "explanation_status": s["model_metadata"]["explanation_source"] if s else "n/a",
                "failure_reason": None if s else "No published signal for this product",
            }
        )
    planted_keys = {(p["signal_type"], p["product_id"]) for p in planted["planted_signals"]}
    false_pos = [k for k in published if k not in planted_keys]
    for k in false_pos:
        rows.append(
            {
                "id": "FP",
                "kind": "false_positive",
                "entity": k[1],
                "expected": "no signal",
                "actual": k[0],
                "detected": True,
                "evidence_status": "resolved",
                "explanation_status": published[k]["model_metadata"]["explanation_source"],
                "failure_reason": "Published signal not in the planted set",
            }
        )
    decoy_rows, decoys_rejected, decoys_escalated = [], 0, 0
    for d in planted["decoys"]:
        rej = next(
            (r for r in rejected if set(d["product_ids"]) & set(r["product_ids"]) and r["candidate_type"] == d["candidate_type"]),
            None,
        )
        esc = any(k[1] in d["product_ids"] for k in published)
        decoys_rejected += 1 if (rej and not esc) else 0
        decoys_escalated += 1 if esc else 0
        decoy_rows.append(
            {
                "id": d["id"],
                "kind": "decoy",
                "entity": ", ".join(d["product_ids"]),
                "expected": "rejected",
                "actual": "escalated" if esc else ("rejected" if rej else "not surfaced"),
                "reason_shown": rej["reason"] if rej else None,
                "failure_reason": None if (rej and not esc) else "Decoy not rejected with a visible reason",
            }
        )

    # Extraction accuracy on required fields vs ground truth
    fields_total = fields_ok = 0
    for t in truth:
        inv = invoices.get(t["invoice_number"])
        for fld in ("supplier_name", "invoice_number", "invoice_date", "invoice_total"):
            fields_total += 1
            if (inv and str(inv[fld]).lower() == str(t[fld]).lower()) or (
                inv and fld == "invoice_total" and float(inv[fld]) == float(t[fld])
            ):
                fields_ok += 1
        got = {line["raw_description"]: line for line in (inv["line_items"] if inv else [])}
        for tl in t["line_items"]:
            g = got.get(tl["raw_description"])
            for fld in ("raw_description", "quantity", "unit", "unit_cost", "line_total"):
                fields_total += 1
                if g and (g[fld] == tl[fld] or (isinstance(tl[fld], (int, float)) and float(g[fld]) == float(tl[fld]))):
                    fields_ok += 1

    # Product match accuracy (accepted matches only, plus unmatched-as-expected)
    accepted = [m for m in matches.values() if m["status"] == "accepted"]
    acc_ok = sum(1 for m in accepted if match_labels.get(m["line_description"]) == m["product_id"])
    expected_none = [d for d, pid in match_labels.items() if pid is None]
    none_ok = sum(1 for d in expected_none if matches.get(d, {}).get("status") in ("unmatched", "blocked"))

    # Evidence completeness and safety
    claims = sum(len(s["evidence_ids"]) for s in signals)
    resolved = sum(1 for s in signals for e in s["evidence_ids"] if e in evidence)
    claim_total = sum(len(s["claims"]) for s in signals)
    claim_valid = sum(len(s["claims"]) for s in signals if not validate_claims(s, evidence, s["facts"]))
    violations = []
    for s in signals:
        for k in ("title", "observation", "interpretation", "next_check"):
            if prohibited_phrases(s[k]):
                violations.append({"signal_id": s["signal_id"], "field": k})

    n_pub = len(published)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": rid,
        "versions": {
            "dataset": planted["dataset_version"],
            "detector": config.DETECTOR_VERSION,
            "prompt": config.PROMPT_VERSION,
            "model": llm.model_name(),
            "extraction_methods": run.status.summary.get("extraction_methods"),
        },
        "metrics": {
            "recall": {
                "value": round(tp / len(planted["planted_signals"]), 3),
                "count": f"{tp} of {len(planted['planted_signals'])}",
                "target": ">= 0.8",
            },
            "precision": {"value": round(tp / n_pub, 3) if n_pub else 0.0, "count": f"{tp} of {n_pub}", "target": ">= 0.8"},
            "invoice_extraction_accuracy": {
                "value": round(fields_ok / fields_total, 3),
                "count": f"{fields_ok} of {fields_total}",
                "target": ">= 0.95",
            },
            "product_match_accuracy": {
                "value": round(acc_ok / len(accepted), 3) if accepted else 0.0,
                "count": f"{acc_ok} of {len(accepted)}",
                "target": ">= 0.9",
            },
            "unmatched_lines_kept_unmatched": {
                "value": round(none_ok / len(expected_none), 3) if expected_none else 1.0,
                "count": f"{none_ok} of {len(expected_none)}",
            },
            "claim_coverage": {
                "value": round(claim_valid / claim_total, 3) if claim_total else 0.0,
                "count": f"{claim_valid} of {claim_total}",
                "target": "1.0",
            },
            "evidence_completeness": {
                "value": round(resolved / claims, 3) if claims else 0.0,
                "count": f"{resolved} of {claims}",
                "target": "1.0",
            },
            "decoys_rejected": {
                "value": decoys_rejected,
                "count": f"{decoys_rejected} of {len(planted['decoys'])}",
                "escalated": decoys_escalated,
                "target": ">= 1 rejected, <= 1 escalated",
            },
            "safety_violations": {"value": len(violations), "target": "0", "items": violations},
        },
        "items": rows + decoy_rows,
    }
    report["counts"] = {
        "true_positives": tp,
        "planted": len(planted["planted_signals"]),
        "published": n_pub,
        "false_positives": len(false_pos),
        "fields_ok": fields_ok,
        "fields_total": fields_total,
        "matches_ok": acc_ok,
        "matches_accepted": len(accepted),
        "evidence_resolved": resolved,
        "evidence_claims": claims,
        "decoys_rejected": decoys_rejected,
        "decoys_total": len(planted["decoys"]),
        "decoys_escalated": decoys_escalated,
        "safety_violations": len(violations),
    }
    report["passed"] = (
        tp >= 4
        and (tp / n_pub if n_pub else 0) >= 0.8
        and fields_ok / fields_total >= 0.95
        and (acc_ok / len(accepted) if accepted else 0) >= 0.9
        and resolved == claims
        and claim_total > 0
        and claim_valid == claim_total
        and decoys_rejected >= 1
        and decoys_escalated <= 1
        and not violations
    )
    if persist:
        repo.put("runs", "evaluation", "latest", report)
    return report
