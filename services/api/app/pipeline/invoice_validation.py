"""Conservative source checks. An arithmetic identity alone is not source evidence."""

import re
from collections import Counter
from decimal import Decimal

FOREIGN_CURRENCY = re.compile(r"\b(?:USD|EUR|GBP|AED|CAD|AUD|JPY|CNY|CHF|SGD|NZD|PKR|BDT|NPR)\b|[$€£¥]", re.I)
NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w.])")


def unsupported_currency(text: str) -> bool:
    return bool(FOREIGN_CURRENCY.search(text))


def numeric_fields_present(line: dict, text: str) -> bool:
    # Multiplicity matters: one occurrence of 10 cannot prove both quantity and rate.
    tail = text.split(line["raw_description"], 1)[-1]
    available = Counter(Decimal(m.group().replace(",", "")) for m in NUMBER.finditer(tail))
    wanted = Counter(Decimal(str(line[k])) for k in ("quantity", "unit_cost", "line_total"))
    if line.get("tax_amount"):
        wanted[Decimal(str(line["tax_amount"]))] += 1
    return not (wanted - available)
