from __future__ import annotations

import argparse
import json
from pathlib import Path

from huling_guard.review import export_review_intervals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = export_review_intervals(args.review_queue.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)


if __name__ == "__main__":
    main()
