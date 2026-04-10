from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from huling_guard.runtime import RuntimeArchiveStore, run_release_video_batch


def _format_summary_markdown(summary: dict[str, Any]) -> str:
    import_summary = summary["import_summary"]
    archive_summary = summary["archive_summary"]
    lines = [
        "# 运行时归档构建摘要",
        "",
        "## 推理批次",
        f"- 视频数量: {summary['batch_result']['clip_count']}",
        f"- 处理清单: {summary['batch_result']['processed_manifest']}",
        f"- 批量汇总: {summary['batch_result']['summary_markdown']}",
        "",
        "## 归档导入",
        f"- 发现报告数: {import_summary['discovered_count']}",
        f"- 新增归档数: {import_summary['imported_count']}",
        f"- 跳过重复数: {import_summary['skipped_count']}",
        f"- 错误数: {import_summary['error_count']}",
        "",
        "## 当前归档概览",
        f"- 历史总会话数: {archive_summary['archive_total']}",
        f"- 含事件会话数: {archive_summary['sessions_with_incidents']}",
        f"- 累计事件数: {archive_summary['total_incidents']}",
        f"- 平均会话时长: {archive_summary['mean_duration_seconds']:.2f} 秒",
        f"- 历史峰值风险: {archive_summary['max_peak_risk_score']:.4f}",
        "",
        "## 主导状态分布",
    ]
    state_counts = archive_summary.get("dominant_state_counts") or {}
    if state_counts:
        for state, count in state_counts.items():
            lines.append(f"- {state}: {count}")
    else:
        lines.append("- 无")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="批量生成运行时历史归档")
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--rtmo-device", default="cuda:0")
    parser.add_argument("--tolerance-seconds", type=float, default=2.0)
    parser.add_argument("--write-video", action="store_true")
    parser.add_argument("--summary-json")
    parser.add_argument("--summary-markdown")
    args = parser.parse_args()

    batch_result = run_release_video_batch(
        release_dir=args.release_dir,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        device=args.device,
        rtmo_device=args.rtmo_device,
        write_video=args.write_video,
        tolerance_seconds=args.tolerance_seconds,
    )
    processed_manifest_path = Path(batch_result["processed_manifest"])
    processed_manifest = json.loads(processed_manifest_path.read_text(encoding="utf-8"))
    session_report_inputs = [
        clip["session_report_json"]
        for clip in processed_manifest.get("clips", [])
        if clip.get("session_report_json")
    ]

    archive_store = RuntimeArchiveStore(args.archive_root)
    import_summary = archive_store.import_report_files(session_report_inputs)
    archive_summary = archive_store.summarize_archives()

    summary = {
        "batch_result": batch_result,
        "import_summary": import_summary,
        "archive_summary": archive_summary,
    }

    summary_json_path = Path(args.summary_json) if args.summary_json else Path(args.output_dir) / "reports" / "archive_materialization_summary.json"
    summary_markdown_path = Path(args.summary_markdown) if args.summary_markdown else Path(args.output_dir) / "reports" / "archive_materialization_summary.md"
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_markdown_path.write_text(_format_summary_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), end="")


if __name__ == "__main__":
    main()
