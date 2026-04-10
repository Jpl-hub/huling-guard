from __future__ import annotations

import argparse
import json
from pathlib import Path

from huling_guard.data import export_missing_pose_entries, summarize_pose_manifest_coverage


def build_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Pose 覆盖率检查",
        "",
        f"- raw_manifest: {summary['raw_manifest_path']}",
        f"- pose_manifest: {summary['pose_manifest_path']}",
        f"- raw_count: {summary['raw_count']}",
        f"- pose_count: {summary['pose_count']}",
        f"- matched_count: {summary['matched_count']}",
        f"- coverage_ratio: {summary['coverage_ratio']:.4f}",
        f"- missing_pose_count: {summary['missing_pose_count']}",
        f"- extra_pose_count: {summary['extra_pose_count']}",
    ]
    if summary["missing_pose_count"]:
        lines.extend(["", "## 缺失样本", *[f"- {sample_id}" for sample_id in summary["missing_pose_sample_ids"][:20]]])
        if summary["missing_pose_count"] > 20:
            lines.append(f"- ... 其余 {summary['missing_pose_count'] - 20} 条省略")
    if summary["extra_pose_count"]:
        lines.extend(["", "## 额外 pose 样本", *[f"- {sample_id}" for sample_id in summary["extra_pose_sample_ids"][:20]]])
        if summary["extra_pose_count"] > 20:
            lines.append(f"- ... 其余 {summary['extra_pose_count'] - 20} 条省略")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-manifest", type=Path, required=True)
    parser.add_argument("--pose-manifest", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-missing-raw-manifest", type=Path)
    args = parser.parse_args()

    if args.output_missing_raw_manifest is not None:
        summary = export_missing_pose_entries(
            raw_manifest_path=args.raw_manifest.resolve(),
            pose_manifest_path=args.pose_manifest.resolve(),
            output_path=args.output_missing_raw_manifest.resolve(),
        ).to_dict()
    else:
        summary = summarize_pose_manifest_coverage(
            raw_manifest_path=args.raw_manifest.resolve(),
            pose_manifest_path=args.pose_manifest.resolve(),
        ).to_dict()
    markdown = build_markdown(summary)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.output_json}", flush=True)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    if args.output_missing_raw_manifest is not None:
        print(f"[write] {args.output_missing_raw_manifest}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
