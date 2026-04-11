from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from huling_guard.data.manifests import load_jsonl


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_video_batch_manifest(
    source_manifest: Path,
    *,
    internal_labels: tuple[str, ...] | None = None,
    dataset: str | None = None,
    scene_prior: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = load_jsonl(source_manifest)
    wanted_labels = {label.strip() for label in internal_labels or () if label.strip()}
    clips: list[dict[str, Any]] = []

    for row in rows:
        sample_id = str(row.get("sample_id") or "").strip()
        video_ref = row.get("video_ref")
        internal_label = str(row.get("internal_label") or "").strip()
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        dataset_name = str(metadata.get("dataset") or "").strip()
        if not sample_id or not isinstance(video_ref, str) or not video_ref.strip():
            continue
        if wanted_labels and internal_label not in wanted_labels:
            continue
        if dataset is not None and dataset_name != dataset:
            continue

        clip_payload = {
            "clip_id": sample_id,
            "input": video_ref,
            "sample_id": sample_id,
            "expected_state": internal_label or None,
            "expected_incident": None if not internal_label else internal_label != "normal",
        }
        if scene_prior is not None:
            clip_payload["scene_prior"] = scene_prior
        clips.append(clip_payload)
        if limit is not None and len(clips) >= limit:
            break

    return {"clips": clips}


def _build_video_index(reference_manifest: Path | None) -> dict[str, dict[str, Any]]:
    if reference_manifest is None:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(reference_manifest):
        video_ref = row.get("video_ref")
        if not isinstance(video_ref, str) or not video_ref.strip():
            continue
        resolved = str(Path(video_ref).resolve())
        index[resolved] = row
        index[Path(resolved).name] = row
    return index


def _fallback_candidate(
    *,
    clip_id: str,
    duration_seconds: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "candidate_id": f"{clip_id}__full_session_normal",
        "recommended_label": "normal",
        "status": "pending",
        "accepted_label": None,
        "confidence": 1.0,
        "start_time": 0.0,
        "end_time": duration_seconds,
        "reason": reason,
    }


def build_archive_review_queue(
    processed_manifest_path: Path,
    *,
    reference_manifest_path: Path | None = None,
    normal_only: bool = True,
    auto_approve: bool = False,
    min_segment_seconds: float = 0.3,
    top_k: int = 40,
    min_incident_total: int = 1,
    dominant_drift_only: bool = False,
) -> dict[str, Any]:
    processed_manifest = _load_json(processed_manifest_path)
    clips = processed_manifest.get("clips", [])
    reference_index = _build_video_index(reference_manifest_path)
    review_items: list[dict[str, Any]] = []

    for clip in clips:
        input_path = str(clip.get("input") or "").strip()
        session_report_path = clip.get("session_report_json")
        if not input_path or not isinstance(session_report_path, str):
            continue
        report = _load_json(Path(session_report_path))
        expected_state = clip.get("expected_state")
        sample_id = clip.get("sample_id")

        if (not isinstance(sample_id, str) or not sample_id) or expected_state is None:
            matched = reference_index.get(str(Path(input_path).resolve())) or reference_index.get(Path(input_path).name)
            if matched is not None:
                sample_id = sample_id or matched.get("sample_id")
                expected_state = expected_state or matched.get("internal_label")

        expected_state_str = str(expected_state or "").strip() or None
        if normal_only and expected_state_str != "normal":
            continue

        state_segments = report.get("state_segments") or []
        incident_total = int(report.get("incident_total") or 0)
        duration_seconds = float(report.get("duration_seconds") or 0.0)
        dominant_state = str(report.get("dominant_state") or "").strip() or None
        if incident_total < min_incident_total:
            continue
        if dominant_drift_only and (
            dominant_state is None or expected_state_str is None or dominant_state == expected_state_str
        ):
            continue
        candidates: list[dict[str, Any]] = []

        for segment in state_segments:
            state = str(segment.get("state") or "").strip()
            if not state or state == "normal":
                continue
            segment_duration = float(segment.get("duration_seconds") or 0.0)
            if segment_duration < min_segment_seconds:
                continue
            candidates.append(
                {
                    "candidate_id": f"{clip['clip_id']}__{state}__{segment.get('start_timestamp', 0.0):.2f}",
                    "recommended_label": "normal",
                    "status": "approved" if auto_approve else "pending",
                    "accepted_label": "normal" if auto_approve else None,
                    "confidence": float(segment.get("max_confidence") or 0.0),
                    "start_time": float(segment.get("start_timestamp") or 0.0),
                    "end_time": float(segment.get("end_timestamp") or 0.0),
                    "reason": (
                        f"archive_false_positive:{state}->normal; "
                        f"incident_total={incident_total}; segment_duration={segment_duration:.2f}"
                    ),
                }
            )

        if not candidates and incident_total > 0:
            fallback = _fallback_candidate(
                clip_id=str(clip["clip_id"]),
                duration_seconds=duration_seconds,
                reason=f"archive_false_positive:incident_only; incident_total={incident_total}",
            )
            if auto_approve:
                fallback["status"] = "approved"
                fallback["accepted_label"] = "normal"
            candidates.append(fallback)

        if not candidates:
            continue

        hard_score = max(float(candidate["confidence"]) for candidate in candidates)
        review_items.append(
            {
                "clip_id": str(clip["clip_id"]),
                "sample_id": sample_id,
                "input": input_path,
                "expected_state": expected_state_str,
                "dominant_state": dominant_state,
                "incident_total": incident_total,
                "hard_score": hard_score,
                "candidates": candidates,
            }
        )

    ranked = sorted(
        review_items,
        key=lambda item: (item["hard_score"], item["incident_total"]),
        reverse=True,
    )
    return {
        "source_processed_manifest": str(processed_manifest_path),
        "source_reference_manifest": str(reference_manifest_path.resolve()) if reference_manifest_path else None,
        "clip_count": min(top_k, len(ranked)),
        "clips": ranked[:top_k],
    }


def build_archive_review_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 归档误报复查队列",
        "",
        f"- clip_count: {summary['clip_count']}",
        "",
        "## 待复查会话",
    ]
    for clip in summary["clips"]:
        lines.append(
            (
                f"- {clip['clip_id']}: sample_id={clip.get('sample_id') or 'missing'} "
                f"expected={clip.get('expected_state') or 'unknown'} "
                f"dominant={clip.get('dominant_state') or 'unknown'} "
                f"incident_total={clip['incident_total']} "
                f"candidate_count={len(clip['candidates'])}"
            )
        )
    return "\n".join(lines) + "\n"


def export_review_intervals(review_queue_path: Path) -> dict[str, Any]:
    payload = _load_json(review_queue_path)
    clips = payload.get("clips", [])
    intervals: list[dict[str, Any]] = []
    skipped_without_sample = 0

    for clip in clips:
        sample_id = clip.get("sample_id")
        for candidate in clip.get("candidates", []):
            if candidate.get("status") != "approved":
                continue
            label = candidate.get("accepted_label") or candidate.get("recommended_label")
            if not isinstance(sample_id, str) or not sample_id:
                skipped_without_sample += 1
                continue
            intervals.append(
                {
                    "sample_id": sample_id,
                    "label": label,
                    "start_time": float(candidate["start_time"]),
                    "end_time": float(candidate["end_time"]),
                    "source": f"review_queue:{clip['clip_id']}:{candidate['candidate_id']}",
                    "sample_weight": max(1.0, float(candidate.get("sample_weight") or candidate.get("weight") or 1.0)),
                }
            )

    return {
        "source": str(review_queue_path),
        "intervals": intervals,
        "skipped_without_sample": skipped_without_sample,
    }
