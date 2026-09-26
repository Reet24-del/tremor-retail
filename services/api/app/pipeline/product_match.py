"""Product matching across the CSV and invoice lines (PRD 9.3, 13.2).

Sequence: normalize -> block incompatible pack sizes -> exact -> fuzzy (RapidFuzz) ->
semantic (lexicon expansion, or sentence embeddings when TREMOR_EMBEDDINGS=1) -> thresholds.
"""

from __future__ import annotations

import os
import re

from rapidfuzz import fuzz

from .. import config
from ..models.contracts import ProductMatch

# Regional / trade abbreviations -> common words (the "semantic" layer without a model)
LEXICON = {
    "haldi": "turmeric",
    "mirch": "chilli",
    "lal": "red",
    "pwd": "powder",
    "sooji": "suji",
    "rava": "suji",
    "masuri": "masoori",
    "kachi": "mustard",
    "ghani": "oil",
    "atta": "atta",
    "pkt": "",
    "pet": "",
    "chitra": "",
    "premium": "",
    "yellow": "",
    "thick": "",
    "loose": "",
    "pack": "",
    "bag": "",
    "tin": "",
    "jar": "",
    "m30": "",
    "easy": "",
    "wash": "",
    "strong": "",
    "teeth": "",
    "antiseptic": "liquid",
    "power": "",
    "plus": "",
    "classic": "classic",
    "salted": "",
    "cola": "coca cola",
    "4x100g": "400 g",
    "biscuit": "",
    "noodles": "",
    "bar": "bar",
    "soap": "",
    "water": "",
    "toothpaste": "",
    "mango": "",
    "cooking": "",
    "bulk": "",
    "order": "",
}
UNIT_ALIASES = {
    "ltr": "l",
    "litre": "l",
    "liter": "l",
    "lt": "l",
    "l": "l",
    "ml": "ml",
    "kg": "kg",
    "kgs": "kg",
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
}
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ltr|litre|liter|lt|ml|kgs|kg|gms|gm|grams|gram|g|l)\b")


MULTI_RE = re.compile(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(ltr|litre|liter|lt|ml|kgs|kg|gms|gm|grams|gram|g|l)\b")


def size_of(text: str) -> tuple[float, str] | None:
    t = MULTI_RE.sub(lambda m: f"{int(m.group(1)) * float(m.group(2)):g} {m.group(3)}", text.lower())
    m = SIZE_RE.search(t)
    if not m:
        return None
    val, unit = float(m.group(1)), UNIT_ALIASES[m.group(2)]
    if unit == "kg":
        return val * 1000, "g"
    if unit == "l":
        return val * 1000, "ml"
    return val, unit


def normalize(text: str) -> str:
    t = MULTI_RE.sub(" ", text.lower())
    t = re.sub(r"\([^)]*\)", " ", t)
    t = SIZE_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    words = []
    for w in t.split():
        rep = LEXICON.get(w, w)
        if rep:
            words.append(rep)
    return " ".join(words).strip()


_embedder = None


def _semantic(a: str, b: str) -> float:
    """0-100. Embeddings if enabled, otherwise lexicon-normalized token similarity."""
    global _embedder
    if os.getenv("TREMOR_EMBEDDINGS") == "1":
        try:
            if _embedder is None:
                from sentence_transformers import SentenceTransformer

                _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            va, vb = _embedder.encode([a, b], normalize_embeddings=True)
            return float((va * vb).sum()) * 100
        except Exception:
            pass
    return float(fuzz.token_set_ratio(normalize(a), normalize(b)))


def match_line(desc: str, products: list[dict]) -> ProductMatch:
    """products: [{product_id, product_name}]"""
    dsize = size_of(desc)
    dnorm = normalize(desc)
    best = None
    blocked_best = None
    for p in products:
        psize = size_of(p["product_name"])
        size_ok = dsize is None or psize is None or (dsize[1] == psize[1] and abs(dsize[0] - psize[0]) < 1e-6)
        pnorm = normalize(p["product_name"])
        exact = dnorm == pnorm and size_ok
        fz = float(fuzz.token_sort_ratio(desc.lower(), p["product_name"].lower()))
        sem = _semantic(desc, p["product_name"])
        size_score = 100.0 if (dsize and psize and size_ok) else (60.0 if size_ok else 0.0)
        combined = 0.35 * fz + 0.45 * sem + 0.20 * size_score
        cand = {"p": p, "fuzzy": fz, "semantic": sem, "size": size_score, "combined": combined, "exact": exact}
        if not size_ok:
            if blocked_best is None or combined > blocked_best["combined"]:
                blocked_best = cand
            continue
        if best is None or (cand["exact"], cand["combined"]) > (best["exact"], best["combined"]):
            best = cand
    mid = f"m_{re.sub(r'[^a-z0-9]+', '_', desc.lower()).strip('_')}"
    if best is None or best["combined"] < config.COMBINED_REVIEW:
        reason = "No compatible shop product found"
        if blocked_best and blocked_best["semantic"] >= 80:
            reason = f"Pack size conflicts with {blocked_best['p']['product_name']}; not matched without unit conversion evidence"
            return ProductMatch(
                match_id=mid,
                line_description=desc,
                product_id=None,
                product_name=None,
                method="none",
                scores={k: round(blocked_best[k], 1) for k in ("fuzzy", "semantic", "size", "combined")},
                confidence=0.0,
                status="blocked",
                reason=reason,
            )
        scores = {k: round(best[k], 1) for k in ("fuzzy", "semantic", "size", "combined")} if best else {}
        return ProductMatch(
            match_id=mid,
            line_description=desc,
            product_id=None,
            product_name=None,
            method="none",
            scores=scores,
            confidence=0.0,
            status="unmatched",
            reason=reason,
        )
    scores = {k: round(best[k], 1) for k in ("fuzzy", "semantic", "size", "combined")}
    if best["exact"]:
        method, status, conf = "exact", "accepted", 1.0
    elif best["fuzzy"] >= config.FUZZY_AUTO_ACCEPT:
        method, status, conf = "fuzzy", "accepted", round(best["fuzzy"] / 100, 2)
    elif best["combined"] >= config.COMBINED_AUTO_ACCEPT:
        method, status, conf = "semantic", "accepted", round(best["combined"] / 100, 2)
    else:
        method, status, conf = "semantic", "needs_review", round(best["combined"] / 100, 2)
    return ProductMatch(
        match_id=mid,
        line_description=desc,
        product_id=best["p"]["product_id"],
        product_name=best["p"]["product_name"],
        method=method,
        scores=scores,
        confidence=conf,
        status=status,
        reason="" if status == "accepted" else "Medium confidence; confirm this match",
    )


def match_all(
    descriptions: list[str],
    products: list[dict],
    frozen: dict[str, str | None] | None = None,
    manual: dict[str, str | None] | None = None,
) -> dict[str, ProductMatch]:
    out = {}
    names = {p["product_id"]: p["product_name"] for p in products}
    for d in sorted(set(descriptions)):
        m = match_line(d, products)
        override = (manual or {}).get(d, "__none__")
        if override != "__none__":
            m = m.model_copy(
                update={
                    "product_id": override,
                    "product_name": names.get(override),
                    "method": "manual",
                    "status": "accepted" if override else "unmatched",
                    "confidence": 1.0 if override else 0.0,
                    "reason": "Confirmed by user",
                }
            )
        elif frozen is not None and d in frozen:
            fid = frozen[d]
            if fid != m.product_id or m.status != "accepted":
                m = m.model_copy(
                    update={
                        "product_id": fid,
                        "product_name": names.get(fid),
                        "method": "frozen" if fid else m.method,
                        "status": "accepted" if fid else ("blocked" if m.status == "blocked" else "unmatched"),
                        "reason": "Frozen demo match" if fid else m.reason,
                    }
                )
        out[d] = m
    return out
