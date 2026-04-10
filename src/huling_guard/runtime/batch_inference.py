from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from huling_guard.evaluation import load_event_evaluation_manifest, summarize_event_corpus
from huling_guard.runtime.batch_manifest import load_batch_video_manifest
from huling_guard.runtime.release import load_runtime_release_bundle
from huling_guard.runtime.rtmo import RTMOPoseEstimator
from huling_guard.runtime.batch_summary import load_session_report, summarize_expected_states
from huling_guard.runtime.service import (
    RuntimeLaunchConfig,
    build_runtime_pipeline_from_resources,
    load_runtime_resources,
)
from huling_guard.runtime.video_inference import run_video_inference_with_runtime

def run_release_video_batch(
    *,
    release_dir: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
    device: str = "cuda",
    rtmo_device: str = "cuda:0",
    write_video: bool = False,
    tolerance_seconds: float = 2.0,
) -> dict[str, Any]:
    bundle = load_runtime_release_bundle(release_dir)
    launch = RuntimeLaunchConfig(
        train_config_path=bundle.train_config_path,
        runtime_config_path=bundle.runtime_config_path,
        checkpoint_path=bundle.checkpoint_path,
        device=device,
    )
    resources = load_runtime_resources(launch)
    estimator = RTMOPoseEstimator(device=rtmo_device)
    clips = load_batch_video_manifest(manifest_path)

    output_root = Path(output_dir).resolve()
    prediction_root = output_root / "predictions"
    video_root = output_root / "videos"
    report_root = output_root / "reports"
    session_report_root = report_root / "sessions"
    prediction_root.mkdir(parents=True, exist_ok=True)
    if write_video:
        video_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    session_report_root.mkdir(parents=True, exist_ok=True)

    evaluation_clips: list[dict[str, Any]] = []
    processed_clips: list[dict[str, Any]] = []
    pipeline_cache: dict[str, Any] = {}

    for index, clip in enumerate(clips, start=1):
        prior_key = str(clip.scene_prior_path) if clip.scene_prior_path is not None else "__default__"
        pipeline = pipeline_cache.get(prior_key)
        if pipeline is None:
            pipeline = build_runtime_pipeline_from_resources(
                resources,
                scene_prior_path=clip.scene_prior_path,
            )
            pipeline_cache[prior_key] = pipeline

        output_jsonl = prediction_root / f"{clip.clip_id}.jsonl"
        output_video = video_root / f"{clip.clip_id}.mp4" if write_video else None
        session_report_json = session_report_root / f"{clip.clip_id}.json"
        session_report_markdown = session_report_root / f"{clip.clip_id}.md"
        frame_count = run_video_inference_with_runtime(
            input_path=clip.input_path,
            pipeline=pipeline,
            estimator=estimator,
            output_jsonl=output_jsonl,
            output_video=output_video,
            output_report_json=session_report_json,
            output_report_markdown=session_report_markdown,
        )
        session_report = load_session_report(session_report_json)
        processed_clips.append(
            {
                "clip_id": clip.clip_id,
                "sample_id": clip.sample_id,
                "expected_state": clip.expected_state,
                "expected_incident": clip.expected_incident,
                "input": str(clip.input_path),
                "predictions": str(output_jsonl),
                "output_video": str(output_video) if output_video is not None else None,
                "annotations": str(clip.annotations_path) if clip.annotations_path is not None else None,
                "scene_prior": str(clip.scene_prior_path) if clip.scene_prior_path is not None else None,
                "frames": frame_count,
                "duration_seconds": float(session_report.get("duration_seconds") or 0.0),
                "dominant_state": session_report.get("dominant_state"),
                "incident_total": int(session_report.get("incident_total") or 0),
                "peak_risk_score": float(session_report.get("peak_risk_score") or 0.0),
                "session_report_json": str(session_report_json),
                "session_report_markdown": str(session_report_markdown),
            }
        )
        if clip.annotations_path is not None:
            evaluation_clips.append(
                {
                    "clip_id": clip.clip_id,
                    "predictions": str(output_jsonl),
                    "annotations": str(clip.annotations_path),
                }
            )
        print(f"[batch-video] {index}/{len(clips)} clip_id={clip.clip_id} frames={frame_count}", flush=True)

    processed_manifest = {
        "release_dir": str(Path(release_dir).resolve()),
        "clips": processed_clips,
        "expected_state_summary": summarize_expected_states(processed_clips),
    }
    processed_manifest_path = report_root / "batch_predictions_manifest.json"
    processed_manifest_path.write_text(
        json.dumps(processed_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    markdown_lines = [
        "# 批量视频验证汇总",
        "",
        "## 基本信息",
        f"- 视频数量: {len(processed_clips)}",
        f"- 事件容忍窗口: {tolerance_seconds:.2f}s",
        "",
        "## 期望状态摘要",
    ]
    expected_summary = processed_manifest["expected_state_summary"]
    markdown_lines.extend(
        [
            f"- 含期望状态视频数: {expected_summary['with_expected_state']}",
            (
                f"- normal 误报会话数: {expected_summary['expected_normal_with_incidents']} / "
                f"{expected_summary['expected_normal_total']} "
                f"({expected_summary['expected_normal_incident_rate']:.4f})"
            ),
            (
                f"- normal 主导状态偏离数: {expected_summary['expected_normal_dominant_non_normal']} / "
                f"{expected_summary['expected_normal_total']} "
                f"({expected_summary['expected_normal_dominant_non_normal_rate']:.4f})"
            ),
            (
                f"- 正样本无事件数: {expected_summary['expected_positive_without_incidents']} / "
                f"{expected_summary['expected_positive_total']} "
                f"({expected_summary['expected_positive_missed_incident_rate']:.4f})"
            ),
            (
                f"- 正样本主导 normal 数: {expected_summary['expected_positive_dominant_normal']} / "
                f"{expected_summary['expected_positive_total']} "
                f"({expected_summary['expected_positive_dominant_normal_rate']:.4f})"
            ),
            "",
            "## 视频清单",
        ]
    )
    for clip in processed_clips:
        markdown_lines.append(
            (
                f"- {clip['clip_id']}: frames={clip['frames']} "
                f"expected_state={clip['expected_state'] or 'unknown'} "
                f"dominant_state={clip['dominant_state'] or 'unknown'} "
                f"incident_total={clip['incident_total']} "
                f"predictions={clip['predictions']} "
                f"annotations={clip['annotations'] or 'none'} "
                f"session_report={clip['session_report_markdown']}"
            )
        )

    result: dict[str, Any] = {
        "clip_count": len(processed_clips),
        "processed_manifest": str(processed_manifest_path),
        "expected_state_summary": expected_summary,
    }
    if evaluation_clips:
        evaluation_manifest = {"clips": evaluation_clips}
        evaluation_manifest_path = report_root / "event_evaluation_manifest.json"
        evaluation_manifest_path.write_text(
            json.dumps(evaluation_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary = summarize_event_corpus(
            clips=load_event_evaluation_manifest(evaluation_manifest_path),
            tolerance_seconds=tolerance_seconds,
        )
        summary_path = report_root / "event_corpus_summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["event_evaluation_manifest"] = str(evaluation_manifest_path)
        result["event_summary"] = str(summary_path)
        result["event_metrics"] = {
            "precision": summary["precision"],
            "recall": summary["recall"],
            "f1": summary["f1"],
            "false_positives_per_hour": summary["false_positives_per_hour"],
            "mean_abs_delay_seconds": summary["mean_abs_delay_seconds"],
        }
        markdown_lines[6:6] = [
            "## 事件级指标",
            f"- precision: {summary['precision']:.4f}",
            f"- recall: {summary['recall']:.4f}",
            f"- f1: {summary['f1']:.4f}",
            f"- 每小时误报数: {summary['false_positives_per_hour']:.4f}",
            f"- 平均绝对延迟(秒): {summary['mean_abs_delay_seconds']:.4f}",
            "",
        ]
    markdown_path = report_root / "batch_validation_summary.md"
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    result["summary_markdown"] = str(markdown_path)
    return result
