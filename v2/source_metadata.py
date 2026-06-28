from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def lecture_metadata_from_filename(filename: str | None) -> dict[str, int]:
    if not filename:
        return {}

    name = Path(filename).name
    metadata: dict[str, int] = {}
    week = _first_int_match(name, [r"(\d+)\s*주차", r"week[_\s-]*(\d+)"])
    lecture_no = _first_int_match(name, [r"(\d+)\s*차시", r"lecture[_\s-]*(\d+)"])
    if week is not None:
        metadata["week"] = week
    if lecture_no is not None:
        metadata["lecture_no"] = lecture_no
    return metadata


def enrich_source_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(metadata)
    filename = enriched.get("filename")
    if isinstance(filename, str):
        for key, value in lecture_metadata_from_filename(filename).items():
            enriched.setdefault(key, value)
    return enriched


def _first_int_match(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None
