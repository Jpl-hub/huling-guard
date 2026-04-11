from __future__ import annotations

import argparse
from pathlib import Path

from huling_guard.data.transition_mining import (
    TransitionMiningConfig,
    build_transition_interval_labels,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从跌倒正样本中自动挖掘 near_fall / recovery 过渡区间")
    parser.add_argument("--pose-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-label",
        dest="include_labels",
        action="append",
        default=None,
        help="允许挖掘过渡区间的原始内部标签，可重复传入；默认 fall 和 prolonged_lying",
    )
    parser.add_argument("--source", default="auto_transition_miner:v1")
    parser.add_argument("--min-frames", type=int, default=16)
    parser.add_argument("--min-pose-confidence", type=float, default=0.2)
    parser.add_argument("--near-fall-lead-seconds", type=float, default=0.9)
    parser.add_argument("--near-fall-tail-gap-seconds", type=float, default=0.12)
    parser.add_argument("--near-fall-min-seconds", type=float, default=0.35)
    parser.add_argument("--min-drop-delta", type=float, default=0.08)
    parser.add_argument("--min-downward-velocity", type=float, default=0.05)
    parser.add_argument("--recovery-window-seconds", type=float, default=1.2)
    parser.add_argument("--recovery-min-seconds", type=float, default=0.35)
    parser.add_argument("--min-recovery-lift", type=float, default=0.06)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_labels = tuple(args.include_labels) if args.include_labels else ("fall", "prolonged_lying")
    payload = build_transition_interval_labels(
        pose_manifest_path=args.pose_manifest,
        output_path=args.output,
        config=TransitionMiningConfig(
            include_labels=include_labels,
            source=str(args.source),
            min_frames=int(args.min_frames),
            min_pose_confidence=float(args.min_pose_confidence),
            near_fall_lead_seconds=float(args.near_fall_lead_seconds),
            near_fall_tail_gap_seconds=float(args.near_fall_tail_gap_seconds),
            near_fall_min_seconds=float(args.near_fall_min_seconds),
            min_drop_delta=float(args.min_drop_delta),
            min_downward_velocity=float(args.min_downward_velocity),
            recovery_window_seconds=float(args.recovery_window_seconds),
            recovery_min_seconds=float(args.recovery_min_seconds),
            min_recovery_lift=float(args.min_recovery_lift),
        ),
    )
    print(
        f"[transition-mining] scanned={payload['samples_scanned']} eligible={payload['eligible_samples']} "
        f"intervals={payload['interval_count']} per_label={payload['per_label']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
