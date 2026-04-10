from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from huling_guard.data.manifests import load_jsonl
from huling_guard.data.pose_io import load_pose_archive


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("samples"), list):
        return payload["samples"]
    nested_sample = payload.get("sample")
    if isinstance(nested_sample, dict) and isinstance(nested_sample.get("samples"), list):
        return nested_sample["samples"]
    return []


def _build_manifest_index(sample_manifest_path: Path) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(sample_manifest_path)
    return {str(row["sample_id"]): row for row in rows}


def _resolve_duration_seconds(entry: dict[str, Any]) -> float:
    pose_path = entry.get("pose_path")
    if not isinstance(pose_path, str) or not pose_path:
        return 0.0
    _, payload = load_pose_archive(pose_path)
    timestamps = payload.get("timestamps")
    if timestamps is not None:
        values = np.asarray(timestamps, dtype=np.float32).reshape(-1)
        if values.size > 0:
            return float(values[-1])
    num_frames = int(entry.get("num_frames") or 0)
    return float(max(0, num_frames - 1))


def _sample_hard_score(*, label_prob: float, predicted_prob: float, correct: bool) -> float:
    if correct:
        return max(0.0, 1.0 - predicted_prob)
    return max(0.0, 1.0 - label_prob)


def build_sample_review_queue(
    sample_summary_path: Path,
    sample_manifest_path: Path,
    *,
    top_k: int = 40,
    focus_labels: tuple[str, ...] = ("near_fall", "fall", "recovery", "prolonged_lying"),
    include_correct: bool = False,
    max_predicted_confidence: float = 0.8,
) -> dict[str, Any]:
    payload = _load_json(sample_summary_path)
    samples = _extract_samples(payload)
    manifest_index = _build_manifest_index(sample_manifest_path)
    review_items: list[dict[str, Any]] = []
    normalized_focus = {label.strip() for label in focus_labels if label.strip()}

    for sample in samples:
        sample_id = str(sample.get("sample_id") or "").strip()
        if not sample_id or sample_id not in manifest_index:
            continue

        label_name = str(sample["label_name"])
        predicted_name = str(sample["predicted_name"])
        mean_probs = [float(value) for value in sample.get("mean_probs", [])]
        label_id = int(sample["label_id"])
        predicted_id = int(sample["predicted_id"])
        correct = label_id == predicted_id
        predicted_prob = mean_probs[predicted_id]
        label_prob = mean_probs[label_id]

        if normalized_focus and label_name not in normalized_focus and predicted_name not in normalized_focus:
            continue
        if correct and (not include_correct or predicted_prob > max_predicted_confidence):
            continue

        manifest_entry = manifest_index[sample_id]
        duration_seconds = _resolve_duration_seconds(manifest_entry)
        hard_score = _sample_hard_score(
            label_prob=label_prob,
            predicted_prob=predicted_prob,
            correct=correct,
        )
        review_items.append(
            {
                "clip_id": sample_id,
                "sample_id": sample_id,
                "pose_path": manifest_entry.get("pose_path"),
                "feature_path": manifest_entry.get("feature_path"),
                "hard_score": hard_score,
                "label_name": label_name,
                "predicted_name": predicted_name,
                "window_count": int(sample.get("window_count") or 0),
                "mean_probs": mean_probs,
                "candidates": [
                    {
                        "candidate_id": f"{sample_id}__full_sample",
                        "recommended_label": predicted_name,
                        "status": "pending",
                        "accepted_label": None,
                        "confidence": predicted_prob,
                        "start_time": 0.0,
                        "end_time": duration_seconds,
                        "reason": (
                            f"sample_confusion:{label_name}->{predicted_name}; "
                            f"label_prob={label_prob:.4f}; predicted_prob={predicted_prob:.4f}"
                        ),
                    }
                ],
            }
        )

    ranked = sorted(
        review_items,
        key=lambda item: (
            item["hard_score"],
            item["candidates"][0]["confidence"],
        ),
        reverse=True,
    )
    return {
        "source_sample_summary": str(sample_summary_path),
        "source_sample_manifest": str(sample_manifest_path),
        "clip_count": min(top_k, len(ranked)),
        "clips": ranked[:top_k],
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 样本级复查队列",
        "",
        f"- clip_count: {summary['clip_count']}",
        "",
        "## 待复查样本",
    ]
    for clip in summary["clips"]:
        candidate = clip["candidates"][0]
        lines.append(
            (
                f"- {clip['sample_id']}: hard_score={clip['hard_score']:.4f} "
                f"label={clip['label_name']} predicted={clip['predicted_name']} "
                f"confidence={candidate['confidence']:.4f} "
                f"window_count={clip['window_count']}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-summary", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument(
        "--focus-labels",
        nargs="*",
        default=["near_fall", "fall", "recovery", "prolonged_lying"],
    )
    parser.add_argument("--include-correct", action="store_true")
    parser.add_argument("--max-predicted-confidence", type=float, default=0.8)
    args = parser.parse_args()

    summary = build_sample_review_queue(
        args.sample_summary.resolve(),
        args.sample_manifest.resolve(),
        top_k=args.top_k,
        focus_labels=tuple(args.focus_labels),
        include_correct=args.include_correct,
        max_predicted_confidence=args.max_predicted_confidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)

    markdown = build_markdown(summary)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
