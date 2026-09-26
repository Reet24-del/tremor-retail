"""Sales and stock CSV validation and normalization (PRD 10.1).

Original CSV line numbers are preserved in `source_row` (header is line 1) so evidence
always resolves back to the uploaded file.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field

import pandas as pd

REQUIRED = [
    "transaction_id",
    "transaction_date",
    "product_id",
    "product_name",
    "quantity_sold",
    "unit_selling_price",
    "opening_stock",
    "closing_stock",
]
OPTIONAL_NUMERIC = ["recorded_damage", "recorded_returns"]
OPTIONAL_TEXT = ["sale_channel", "customer_reference"]
CHANNELS = {"cash", "upi", "card", "credit"}


@dataclass
class CsvResult:
    df: pd.DataFrame | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _rows(mask: pd.Series, df: pd.DataFrame, limit: int = 8) -> str:
    rows = df.loc[mask, "source_row"].tolist()
    more = f" and {len(rows) - limit} more" if len(rows) > limit else ""
    return ", ".join(str(r) for r in rows[:limit]) + more


def load_sales_csv(content: bytes) -> CsvResult:
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        return CsvResult(None, [f"Could not read the file as CSV: {exc}"])
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return CsvResult(
            None, [f"Missing required column: {c}" for c in missing], summary={"columns": list(df.columns), "row_count": len(df)}
        )
    if df.empty:
        return CsvResult(None, ["The file has a header but no rows."])

    df = df.copy()
    df["source_row"] = range(2, len(df) + 2)
    errors: list[str] = []
    if "currency" in df.columns and (~df["currency"].str.strip().str.upper().eq("INR")).any():
        errors.append("Unsupported currency in currency column; only INR is supported")
    warnings: list[str] = []

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce").dt.date
    bad = df["transaction_date"].isna()
    if bad.any():
        errors.append(f"Invalid transaction_date on rows {_rows(bad, df)}")

    for col in ["quantity_sold", "unit_selling_price", "opening_stock", "closing_stock", *OPTIONAL_NUMERIC]:
        if col not in df.columns:
            df[col] = 0.0
            continue
        raw = df[col].replace("", "0" if col in OPTIONAL_NUMERIC else None)
        df[col] = pd.to_numeric(raw, errors="coerce")
        bad = df[col].isna() | ~df[col].map(lambda value: math.isfinite(float(value)))
        if bad.any():
            errors.append(f"Invalid number in {col} on rows {_rows(bad, df)}")
        neg = df[col] < 0
        if neg.any():
            errors.append(f"Negative value in {col} on rows {_rows(neg, df)} (returns belong in recorded_returns)")

    zero_price = (df["quantity_sold"] > 0) & (df["unit_selling_price"] <= 0)
    if zero_price.any():
        errors.append(f"unit_selling_price must be above zero when items were sold, rows {_rows(zero_price, df)}")

    if "sale_channel" in df.columns:
        badc = (df["sale_channel"] != "") & (~df["sale_channel"].str.lower().isin(CHANNELS))
        if badc.any():
            warnings.append(f"Unknown sale_channel on rows {_rows(badc, df)}; ignored")

    dup = df.duplicated(subset=["transaction_id"], keep="first")
    if dup.any():
        warnings.append(f"Duplicate transaction_id on rows {_rows(dup, df)}; excluded from calculations")
        df = df[~dup]

    for c in ("product_id", "product_name", "transaction_id"):
        blank = df[c].str.strip() == ""
        if blank.any():
            errors.append(f"Blank {c} on rows {_rows(blank, df)}")

    if errors:
        return CsvResult(None, errors, warnings, {"row_count": len(df)})

    dates = df["transaction_date"]
    summary = {
        "row_count": len(df),
        "columns": [c for c in df.columns if c != "source_row"],
        "date_from": str(min(dates)),
        "date_to": str(max(dates)),
        "currency": "INR",
        "product_count": int(df["product_id"].nunique()),
    }
    return CsvResult(df.reset_index(drop=True), errors, warnings, summary)
