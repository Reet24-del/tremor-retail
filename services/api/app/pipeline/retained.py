"""Immutable input snapshots used by retries and correction runs."""

import re
from dataclasses import asdict

from ..storage import repository as repo


def safe_filename(name: str | None) -> str:
    base = (name or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    if not base or len(base) > 180:
        raise ValueError("Filename must contain 1 to 180 safe characters")
    return base


def save_inputs(run_id, inputs):
    directory = repo.run_dir(run_id)
    files = [(inputs.csv_name, inputs.csv_bytes), *inputs.pdfs]
    names = [safe_filename(name) for name, _ in files]
    if len(set(n.lower() for n in names)) != len(names):
        raise ValueError("Uploaded filenames must be distinct after normalization")
    inputs.csv_name = names[0]
    inputs.pdfs = list(zip(names[1:], [b for _, b in inputs.pdfs], strict=True))
    for name, (_, content) in zip(names, files, strict=True):
        (directory / name).write_bytes(content)
    snapshot = asdict(inputs)
    snapshot.pop("csv_bytes")
    snapshot["pdfs"] = names[1:]
    snapshot["cached_dir"] = str(inputs.cached_dir) if inputs.cached_dir else None
    repo.put("inputs", run_id, "manifest", snapshot)


def load_inputs(run_id):
    from pathlib import Path

    from .run import RunInputs

    data = repo.get("inputs", run_id, "manifest")
    if data is None:
        raise ValueError("Retained inputs are unavailable; upload the files again")
    directory = repo.run_dir(run_id)
    data["csv_bytes"] = (directory / data["csv_name"]).read_bytes()
    data["pdfs"] = [(name, (directory / name).read_bytes()) for name in data["pdfs"]]
    data["cached_dir"] = Path(data["cached_dir"]) if data["cached_dir"] else None
    # Preserve the original model output; failed extractions may be retried.
    data["original_extractions"] = {
        item["source_id"]: item for item in repo.list_("original_invoices", run_id) if item.get("invoice")
    }
    data["parent_run_id"] = run_id
    return RunInputs(**data)
