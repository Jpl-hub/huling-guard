from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--shard-manifest-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_rows(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            sample_id = str(row.get("sample_id"))
            if sample_id in seen:
                continue
            seen.add(sample_id)
            merged.append(row)

    base_manifest = args.base_manifest.resolve()
    if base_manifest.is_file():
        add_rows(load_jsonl(base_manifest))
    for shard_manifest in sorted(args.shard_manifest_dir.resolve().glob("*.jsonl")):
        add_rows(load_jsonl(shard_manifest))

    count = write_jsonl(args.output.resolve(), merged)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "rows": count,
                "shard_manifest_dir": str(args.shard_manifest_dir.resolve()),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
