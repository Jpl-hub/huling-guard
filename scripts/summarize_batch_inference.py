from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from huling_guard.runtime.batch_summary import enrich_processed_clips, summarize_expected_states


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_line(title: str, value: Any) -> str:
    if isinstance(value, float):
        return f"- {title}: {value:.4f}"
    return f"- {title}: {value}"


def _build_markdown(processed_manifest: dict[str, Any], event_summary: dict[str, Any] | None) -> str:
    clips = enrich_processed_clips(processed_manifest.get("clips", []))
    expected_summary = processed_manifest.get("expected_state_summary") or summarize_expected_states(clips)
    lines = [
        "# 批量视频验证汇总",
        "",
        "## 基本信息",
        _metric_line("视频数量", len(clips)),
    ]

    total_frames = sum(int(clip.get("frames") or 0) for clip in clips)
    lines.append(_metric_line("总帧数", total_frames))
    if expected_summary:
        lines.extend(
            [
                "",
                "## 期望状态摘要",
                _metric_line("含期望状态视频数", expected_summary.get("with_expected_state", 0)),
                (
                    f"- normal 误报会话数: {expected_summary.get('expected_normal_with_incidents', 0)} / "
                    f"{expected_summary.get('expected_normal_total', 0)} "
                    f"({float(expected_summary.get('expected_normal_incident_rate', 0.0)):.4f})"
                ),
                (
                    f"- normal 主导状态偏离数: {expected_summary.get('expected_normal_dominant_non_normal', 0)} / "
                    f"{expected_summary.get('expected_normal_total', 0)} "
                    f"({float(expected_summary.get('expected_normal_dominant_non_normal_rate', 0.0)):.4f})"
                ),
                (
                    f"- 正样本无事件数: {expected_summary.get('expected_positive_without_incidents', 0)} / "
                    f"{expected_summary.get('expected_positive_total', 0)} "
                    f"({float(expected_summary.get('expected_positive_missed_incident_rate', 0.0)):.4f})"
                ),
                (
                    f"- 正样本主导 normal 数: {expected_summary.get('expected_positive_dominant_normal', 0)} / "
                    f"{expected_summary.get('expected_positive_total', 0)} "
                    f"({float(expected_summary.get('expected_positive_dominant_normal_rate', 0.0)):.4f})"
                ),
            ]
        )

    if event_summary is not None:
        lines.extend(
            [
                "",
                "## 事件级指标",
                _metric_line("precision", event_summary.get("precision", 0.0)),
                _metric_line("recall", event_summary.get("recall", 0.0)),
                _metric_line("f1", event_summary.get("f1", 0.0)),
                _metric_line("每小时误报数", event_summary.get("false_positives_per_hour", 0.0)),
                _metric_line("平均绝对延迟(秒)", event_summary.get("mean_abs_delay_seconds", 0.0)),
                "",
                "## 各事件类型",
            ]
        )
        for kind in event_summary.get("kinds", []):
            kind_summary = event_summary["per_kind"][kind]
            lines.append(
                (
                    f"- {kind}: TP={kind_summary['tp']} FP={kind_summary['fp']} FN={kind_summary['fn']} "
                    f"precision={kind_summary['precision']:.4f} "
                    f"recall={kind_summary['recall']:.4f} "
                    f"f1={kind_summary['f1']:.4f}"
                )
            )

    lines.extend(["", "## 视频清单"])
    for clip in clips:
        lines.append(
            (
                f"- {clip['clip_id']}: frames={clip.get('frames', 0)} "
                f"expected_state={clip.get('expected_state') or 'unknown'} "
                f"dominant_state={clip.get('dominant_state') or 'unknown'} "
                f"incident_total={clip.get('incident_total', 0)} "
                f"predictions={clip.get('predictions')} "
                f"annotations={clip.get('annotations') or 'none'}"
            )
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-manifest", type=Path, required=True)
    parser.add_argument("--event-summary", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    processed_manifest = _load_json(args.processed_manifest.resolve())
    event_summary = _load_json(args.event_summary.resolve()) if args.event_summary else None
    markdown = _build_markdown(processed_manifest, event_summary)

    print(markdown, end="")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)


if __name__ == "__main__":
    main()
