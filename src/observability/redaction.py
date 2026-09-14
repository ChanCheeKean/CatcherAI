from __future__ import annotations

import re
from typing import Any

from domain.events import Redaction

SECRET_RE = re.compile(r"\b(?:sk|sess|proj)-[A-Za-z0-9_-]{12,}\b")
PAN_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
PROHIBITED_KEYS = {
    "race",
    "color",
    "religion",
    "national_origin",
    "sex",
    "marital_status",
    "birth_year",
    "zip_code",
}


def _redact_text(value: str) -> tuple[str, list[str]]:
    categories: list[str] = []
    redacted = SECRET_RE.sub("[REDACTED_SECRET]", value)
    if redacted != value:
        categories.append("secret")
    without_pan = PAN_RE.sub("[REDACTED_PAN]", redacted)
    if without_pan != redacted:
        categories.append("pan")
    return without_pan, categories


def redact(value: Any, path: str = "$") -> tuple[Any, list[Redaction]]:
    records: list[Redaction] = []
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in PROHIBITED_KEYS:
                output[key] = "[REDACTED_PROHIBITED_BASIS]"
                records.append(Redaction(path=child_path, category="prohibited_basis"))
            else:
                output[key], child = redact(item, child_path)
                records.extend(child)
        return output, records
    if isinstance(value, list):
        output_list = []
        for index, item in enumerate(value):
            redacted, child = redact(item, f"{path}[{index}]")
            output_list.append(redacted)
            records.extend(child)
        return output_list, records
    if isinstance(value, str):
        redacted, categories = _redact_text(value)
        records.extend(Redaction(path=path, category=category) for category in categories)
        return redacted, records
    return value, records
