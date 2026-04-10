from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EventRecord:
    kind: str
    timestamp: float
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "timestamp": self.timestamp,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True, slots=True)
class EventEvaluationClip:
    clip_id: str
    predictions_path: Path
    annotations_path: Path
    duration_seconds: float | None = None


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def load_annotation_events(path: str | Path) -> tuple[list[EventRecord], float | None]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("annotation file must be a JSON object")

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("annotation file must contain an 'events' array")

    duration_seconds = payload.get("duration_seconds")
    if duration_seconds is not None:
        duration_seconds = float(duration_seconds)

    events: list[EventRecord] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise ValueError("each annotation event must be an object")
        kind = item.get("kind")
        timestamp = item.get("timestamp")
        if not isinstance(kind, str) or timestamp is None:
            raise ValueError("each annotation event must contain 'kind' and 'timestamp'")
        events.append(EventRecord(kind=kind, timestamp=float(timestamp)))

    events.sort(key=lambda event: (event.timestamp, event.kind))
    return events, duration_seconds


def load_prediction_events(path: str | Path) -> tuple[list[EventRecord], float]:
    file_path = Path(path)
    events: list[EventRecord] = []
    seen: set[tuple[str, int]] = set()
    duration_seconds = 0.0

    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            timestamp = float(record.get("timestamp", 0.0))
            duration_seconds = max(duration_seconds, timestamp)
            for incident in record.get("incidents", []):
                kind = str(incident["kind"])
                event_timestamp = float(incident["timestamp"])
                dedupe_key = (kind, int(round(event_timestamp * 1000)))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                confidence = incident.get("confidence")
                events.append(
                    EventRecord(
                        kind=kind,
                        timestamp=event_timestamp,
                        confidence=float(confidence) if confidence is not None else None,
                    )
                )

    events.sort(key=lambda event: (event.timestamp, event.kind))
    return events, duration_seconds


def summarize_event_detection(
    ground_truth_events: list[EventRecord],
    predicted_events: list[EventRecord],
    *,
    tolerance_seconds: float,
    duration_seconds: float,
) -> dict[str, Any]:
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    kinds = sorted({event.kind for event in ground_truth_events} | {event.kind for event in predicted_events})
    per_kind: dict[str, dict[str, Any]] = {}
    overall_delays: list[float] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for kind in kinds:
        gt_events = [event for event in ground_truth_events if event.kind == kind]
        pred_events = [event for event in predicted_events if event.kind == kind]
        used_predictions: set[int] = set()
        delays: list[float] = []

        for gt_event in gt_events:
            best_index = -1
            best_distance = float("inf")
            best_delay = 0.0
            for index, pred_event in enumerate(pred_events):
                if index in used_predictions:
                    continue
                delay = pred_event.timestamp - gt_event.timestamp
                distance = abs(delay)
                if distance > tolerance_seconds:
                    continue
                if distance < best_distance:
                    best_distance = distance
                    best_index = index
                    best_delay = delay
            if best_index >= 0:
                used_predictions.add(best_index)
                delays.append(best_delay)

        tp = len(delays)
        fp = len(pred_events) - tp
        fn = len(gt_events) - tp
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)

        per_kind[kind] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": len(gt_events),
            "predictions": len(pred_events),
            "mean_delay_seconds": _safe_div(sum(delays), len(delays)),
            "mean_abs_delay_seconds": _safe_div(sum(abs(delay) for delay in delays), len(delays)),
        }
        overall_delays.extend(delays)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    precision = _safe_div(total_tp, total_tp + total_fp)
    recall = _safe_div(total_tp, total_tp + total_fn)
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    return {
        "kinds": kinds,
        "tolerance_seconds": tolerance_seconds,
        "duration_seconds": duration_seconds,
        "duration_hours": duration_seconds / 3600.0,
        "total_ground_truth": len(ground_truth_events),
        "total_predictions": len(predicted_events),
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_delay_seconds": _safe_div(sum(overall_delays), len(overall_delays)),
        "mean_abs_delay_seconds": _safe_div(sum(abs(delay) for delay in overall_delays), len(overall_delays)),
        "false_positives_per_hour": _safe_div(total_fp, duration_seconds / 3600.0),
        "per_kind": per_kind,
    }


def load_event_evaluation_manifest(path: str | Path) -> list[EventEvaluationClip]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation manifest must be a JSON object")
    raw_clips = payload.get("clips")
    if not isinstance(raw_clips, list):
        raise ValueError("evaluation manifest must contain a 'clips' array")

    base_dir = manifest_path.parent
    clips: list[EventEvaluationClip] = []
    for index, item in enumerate(raw_clips):
        if not isinstance(item, dict):
            raise ValueError("each clip entry must be an object")
        clip_id = item.get("clip_id") or item.get("video_id") or f"clip_{index:04d}"
        predictions_path = item.get("predictions")
        annotations_path = item.get("annotations")
        if not isinstance(predictions_path, str) or not isinstance(annotations_path, str):
            raise ValueError("each clip entry must contain 'predictions' and 'annotations'")
        duration_seconds = item.get("duration_seconds")
        clips.append(
            EventEvaluationClip(
                clip_id=str(clip_id),
                predictions_path=(base_dir / predictions_path).resolve(),
                annotations_path=(base_dir / annotations_path).resolve(),
                duration_seconds=float(duration_seconds) if duration_seconds is not None else None,
            )
        )
    return clips


def summarize_event_corpus(
    clips: list[EventEvaluationClip],
    *,
    tolerance_seconds: float,
) -> dict[str, Any]:
    if not clips:
        raise ValueError("clips must not be empty")

    clip_summaries: list[dict[str, Any]] = []
    kinds: set[str] = set()
    total_duration_seconds = 0.0
    total_tp = 0
    total_fp = 0
    total_fn = 0
    delay_sum = 0.0
    abs_delay_sum = 0.0
    matched_events = 0
    per_kind_counts: dict[str, dict[str, float]] = {}

    for clip in clips:
        ground_truth_events, annotated_duration = load_annotation_events(clip.annotations_path)
        predicted_events, inferred_duration = load_prediction_events(clip.predictions_path)
        duration_seconds = clip.duration_seconds
        if duration_seconds is None:
            duration_seconds = annotated_duration if annotated_duration is not None else inferred_duration
        summary = summarize_event_detection(
            ground_truth_events=ground_truth_events,
            predicted_events=predicted_events,
            tolerance_seconds=tolerance_seconds,
            duration_seconds=float(duration_seconds),
        )
        summary["clip_id"] = clip.clip_id
        summary["predictions_path"] = str(clip.predictions_path)
        summary["annotations_path"] = str(clip.annotations_path)
        clip_summaries.append(summary)

        total_duration_seconds += float(duration_seconds)
        total_tp += int(summary["tp"])
        total_fp += int(summary["fp"])
        total_fn += int(summary["fn"])
        matched_events += int(summary["tp"])
        delay_sum += float(summary["mean_delay_seconds"]) * int(summary["tp"])
        abs_delay_sum += float(summary["mean_abs_delay_seconds"]) * int(summary["tp"])

        for kind in summary["kinds"]:
            kinds.add(kind)
            kind_summary = summary["per_kind"][kind]
            accumulator = per_kind_counts.setdefault(
                kind,
                {
                    "tp": 0.0,
                    "fp": 0.0,
                    "fn": 0.0,
                    "support": 0.0,
                    "predictions": 0.0,
                    "delay_sum": 0.0,
                    "abs_delay_sum": 0.0,
                },
            )
            accumulator["tp"] += float(kind_summary["tp"])
            accumulator["fp"] += float(kind_summary["fp"])
            accumulator["fn"] += float(kind_summary["fn"])
            accumulator["support"] += float(kind_summary["support"])
            accumulator["predictions"] += float(kind_summary["predictions"])
            accumulator["delay_sum"] += float(kind_summary["mean_delay_seconds"]) * float(kind_summary["tp"])
            accumulator["abs_delay_sum"] += float(kind_summary["mean_abs_delay_seconds"]) * float(
                kind_summary["tp"]
            )

    per_kind: dict[str, dict[str, Any]] = {}
    for kind in sorted(kinds):
        counts = per_kind_counts[kind]
        tp = int(counts["tp"])
        fp = int(counts["fp"])
        fn = int(counts["fn"])
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        per_kind[kind] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": int(counts["support"]),
            "predictions": int(counts["predictions"]),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mean_delay_seconds": _safe_div(counts["delay_sum"], tp),
            "mean_abs_delay_seconds": _safe_div(counts["abs_delay_sum"], tp),
        }

    precision = _safe_div(total_tp, total_tp + total_fp)
    recall = _safe_div(total_tp, total_tp + total_fn)
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    return {
        "clips": clip_summaries,
        "clip_count": len(clip_summaries),
        "kinds": sorted(kinds),
        "tolerance_seconds": tolerance_seconds,
        "duration_seconds": total_duration_seconds,
        "duration_hours": total_duration_seconds / 3600.0,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_delay_seconds": _safe_div(delay_sum, matched_events),
        "mean_abs_delay_seconds": _safe_div(abs_delay_sum, matched_events),
        "false_positives_per_hour": _safe_div(total_fp, total_duration_seconds / 3600.0),
        "per_kind": per_kind,
    }


def format_event_evaluation(summary: dict[str, Any]) -> str:
    lines = [
        "事件级评估摘要",
        f"事件容忍窗口: {summary['tolerance_seconds']:.2f}s",
        f"视频时长: {summary['duration_seconds']:.2f}s",
        (
            "总体: "
            f"TP={summary['tp']} FP={summary['fp']} FN={summary['fn']} "
            f"precision={summary['precision']:.4f} "
            f"recall={summary['recall']:.4f} "
            f"f1={summary['f1']:.4f} "
            f"fp_per_hour={summary['false_positives_per_hour']:.4f}"
        ),
        (
            "延迟: "
            f"mean={summary['mean_delay_seconds']:.4f}s "
            f"mean_abs={summary['mean_abs_delay_seconds']:.4f}s"
        ),
    ]
    for kind in summary["kinds"]:
        kind_summary = summary["per_kind"][kind]
        lines.append(
            (
                f"- {kind}: TP={kind_summary['tp']} FP={kind_summary['fp']} FN={kind_summary['fn']} "
                f"precision={kind_summary['precision']:.4f} "
                f"recall={kind_summary['recall']:.4f} "
                f"f1={kind_summary['f1']:.4f} "
                f"mean_delay={kind_summary['mean_delay_seconds']:.4f}s"
            )
        )
    return "\n".join(lines) + "\n"


def format_event_corpus_evaluation(summary: dict[str, Any]) -> str:
    lines = [
        "批量事件级评估摘要",
        f"视频数量: {summary['clip_count']}",
        f"事件容忍窗口: {summary['tolerance_seconds']:.2f}s",
        f"总时长: {summary['duration_seconds']:.2f}s",
        (
            "总体: "
            f"TP={summary['tp']} FP={summary['fp']} FN={summary['fn']} "
            f"precision={summary['precision']:.4f} "
            f"recall={summary['recall']:.4f} "
            f"f1={summary['f1']:.4f} "
            f"fp_per_hour={summary['false_positives_per_hour']:.4f}"
        ),
        (
            "延迟: "
            f"mean={summary['mean_delay_seconds']:.4f}s "
            f"mean_abs={summary['mean_abs_delay_seconds']:.4f}s"
        ),
    ]
    for kind in summary["kinds"]:
        kind_summary = summary["per_kind"][kind]
        lines.append(
            (
                f"- {kind}: TP={kind_summary['tp']} FP={kind_summary['fp']} FN={kind_summary['fn']} "
                f"precision={kind_summary['precision']:.4f} "
                f"recall={kind_summary['recall']:.4f} "
                f"f1={kind_summary['f1']:.4f} "
                f"mean_delay={kind_summary['mean_delay_seconds']:.4f}s"
            )
        )
    return "\n".join(lines) + "\n"
