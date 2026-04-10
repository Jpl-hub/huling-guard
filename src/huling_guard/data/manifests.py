from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from huling_guard.taxonomy import map_external_label


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return len(rows)


def normalize_internal_label(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    external_label = normalized.get("external_label")
    if isinstance(external_label, str) and external_label.strip():
        normalized["internal_label"] = map_external_label(external_label)
    return normalized


def merge_jsonl_manifests(
    input_paths: list[str | Path],
    output_path: str | Path,
    dedupe_by: str = "sample_id",
) -> int:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for input_path in input_paths:
        for row in load_jsonl(input_path):
            key = str(row.get(dedupe_by))
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalize_internal_label(row))
    return write_jsonl(output_path, merged)
