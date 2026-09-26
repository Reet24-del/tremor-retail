"""DuckDB-backed run storage. One JSON document per object keeps the contracts authoritative in Pydantic."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import duckdb

from .. import config

TABLES = [
    "runs",
    "sources",
    "invoices",
    "matches",
    "features",
    "signals",
    "evidence",
    "candidates",
    "reviews",
    "inputs",
    "original_invoices",
    "products",
]
_lock = threading.Lock()
_con = None


def _db():
    global _con
    if _con is None:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        _con = duckdb.connect(str(config.DB_PATH))
        for t in TABLES:
            _con.execute(
                f"CREATE TABLE IF NOT EXISTS {t} (run_id VARCHAR, id VARCHAR, doc JSON, "
                "updated_at TIMESTAMP DEFAULT current_timestamp)"
            )
    return _con


def put(table: str, run_id: str, obj_id: str, doc: dict) -> None:
    with _lock:
        con = _db()
        con.execute(f"DELETE FROM {table} WHERE run_id = ? AND id = ?", [run_id, obj_id])
        con.execute(f"INSERT INTO {table} (run_id, id, doc) VALUES (?, ?, ?)", [run_id, obj_id, json.dumps(doc, default=str)])


def put_many(table: str, run_id: str, docs: dict[str, dict]) -> None:
    with _lock:
        con = _db()
        con.execute(f"DELETE FROM {table} WHERE run_id = ?", [run_id])
        if docs:
            con.executemany(
                f"INSERT INTO {table} (run_id, id, doc) VALUES (?, ?, ?)",
                [[run_id, k, json.dumps(v, default=str)] for k, v in docs.items()],
            )


def get(table: str, run_id: str, obj_id: str) -> dict | None:
    with _lock:
        row = _db().execute(f"SELECT doc FROM {table} WHERE run_id = ? AND id = ?", [run_id, obj_id]).fetchone()
    return json.loads(row[0]) if row else None


def find(table: str, obj_id: str) -> dict | None:
    with _lock:
        row = _db().execute(f"SELECT doc FROM {table} WHERE id = ? ORDER BY updated_at DESC LIMIT 1", [obj_id]).fetchone()
    return json.loads(row[0]) if row else None


def list_(table: str, run_id: str) -> list[dict]:
    with _lock:
        rows = _db().execute(f"SELECT doc FROM {table} WHERE run_id = ? ORDER BY updated_at, id", [run_id]).fetchall()
    return [json.loads(r[0]) for r in rows]


def latest_run_id() -> str | None:
    with _lock:
        row = _db().execute("SELECT run_id FROM runs WHERE id = run_id ORDER BY updated_at DESC LIMIT 1").fetchone()
    return row[0] if row else None


def run_dir(run_id: str) -> Path:
    p = config.RUNTIME_DIR / "runs" / run_id
    p.mkdir(parents=True, exist_ok=True)
    return p
