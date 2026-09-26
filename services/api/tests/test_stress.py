"""Regression tests on generated random stores (scripts/random_store.py)."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("TREMOR_DISABLE_LLM", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from random_store import generate_store

from app.pipeline.evaluate import run_evaluation


def test_pending_match_does_not_create_fake_stock_signal():
    """Seed 1017: the bulk line needs match review. Its stock must not be reported as a discrepancy."""
    d = Path(tempfile.mkdtemp()) / "store_1017"
    generate_store(1017, d)
    rep = run_evaluation(d, persist=False)
    assert rep["counts"]["decoys_escalated"] == 0
    assert not [i for i in rep["items"] if i["kind"] == "false_positive" and i["actual"] == "inventory_discrepancy"]


def test_generator_is_deterministic():
    a, b = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    generate_store(1234, a)
    generate_store(1234, b)
    assert (a / "sales_stock.csv").read_bytes() == (b / "sales_stock.csv").read_bytes()
    assert (a / "labels" / "signals.json").read_text() == (b / "labels" / "signals.json").read_text()
