from __future__ import annotations

import argparse
import json
from pathlib import Path

from huling_guard.review import build_archive_review_markdown, build_archive_review_queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-manifest", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--min-segment-seconds", type=float, default=0.3)
    parser.add_argument("--min-incident-total", type=int, default=1)
    parser.add_argument("--dominant-drift-only", action="store_true")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--include-non-normal-expected", action="store_true")
    args = parser.parse_args()

    summary = build_archive_review_queue(
        args.processed_manifest.resolve(),
        reference_manifest_path=args.reference_manifest.resolve() if args.reference_manifest else None,
        normal_only=not args.include_non_normal_expected,
        auto_approve=args.auto_approve,
        min_segment_seconds=args.min_segment_seconds,
        top_k=args.top_k,
        min_incident_total=args.min_incident_total,
        dominant_drift_only=args.dominant_drift_only,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)

    markdown = build_archive_review_markdown(summary)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
