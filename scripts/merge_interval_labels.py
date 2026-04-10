from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_interval_labels(input_paths: list[Path]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float, float, str]] = set()
    sources: list[str] = []

    for input_path in input_paths:
        payload = _load_json(input_path.resolve())
        sources.append(str(input_path.resolve()))
        for item in payload.get("intervals", []):
            key = (
                str(item["sample_id"]),
                str(item["label"]),
                float(item["start_time"]),
                float(item["end_time"]),
                str(item.get("source") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "sample_id": key[0],
                    "label": key[1],
                    "start_time": key[2],
                    "end_time": key[3],
                    "source": key[4],
                }
            )

    merged.sort(key=lambda item: (item["sample_id"], item["start_time"], item["end_time"], item["label"]))
    return {
        "sources": sources,
        "intervals": merged,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = merge_interval_labels(args.inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)


if __name__ == "__main__":
    main()
