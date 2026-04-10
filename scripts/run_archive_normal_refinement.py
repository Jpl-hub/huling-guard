from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from huling_guard.review import (
    build_archive_review_markdown,
    build_archive_review_queue,
    export_review_intervals,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-manifest", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--review-markdown", type=Path)
    parser.add_argument("--interval-output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--min-segment-seconds", type=float, default=0.3)
    parser.add_argument("--min-incident-total", type=int, default=1)
    parser.add_argument("--dominant-drift-only", action="store_true")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--include-non-normal-expected", action="store_true")
    parser.add_argument("--run-training", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--run-name", default="public_plus_ur_archive_refined")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    review_summary = build_archive_review_queue(
        args.processed_manifest.resolve(),
        reference_manifest_path=args.reference_manifest.resolve() if args.reference_manifest else None,
        normal_only=not args.include_non_normal_expected,
        auto_approve=args.auto_approve,
        min_segment_seconds=args.min_segment_seconds,
        top_k=args.top_k,
        min_incident_total=args.min_incident_total,
        dominant_drift_only=args.dominant_drift_only,
    )
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.write_text(
        json.dumps(review_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {args.review_output}", flush=True)

    review_markdown = build_archive_review_markdown(review_summary)
    if args.review_markdown is not None:
        args.review_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.review_markdown.write_text(review_markdown, encoding="utf-8")
        print(f"[write] {args.review_markdown}", flush=True)

    interval_payload = export_review_intervals(args.review_output.resolve())
    args.interval_output.parent.mkdir(parents=True, exist_ok=True)
    args.interval_output.write_text(
        json.dumps(interval_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {args.interval_output}", flush=True)

    interval_count = len(interval_payload.get("intervals", []))
    print(f"[interval_count] {interval_count}", flush=True)

    if not args.run_training:
        return
    if interval_count <= 0:
        print("[training_skipped] no approved intervals", flush=True)
        return

    command = [
        args.python,
        "scripts/run_public_plus_ur_refined_training.py",
        "--python",
        args.python,
        "--repo-root",
        str(repo_root),
        "--data-root",
        str(args.data_root.resolve()),
        "--run-name",
        args.run_name,
        "--seed",
        str(args.seed),
        "--kinematic-feature-set",
        args.kinematic_feature_set,
        "--clip-focal-gamma",
        str(args.clip_focal_gamma),
        "--train-interval-labels",
        str(args.interval_output.resolve()),
        "--train",
    ]
    print("[run]", " ".join(command), flush=True)
    subprocess.run(command, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
