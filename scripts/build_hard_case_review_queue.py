from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATE_WINDOW_SECONDS = {
    "near_fall": 2.0,
    "fall": 3.0,
    "recovery": 2.5,
    "prolonged_lying": 4.0,
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_review_queue(
    hard_cases_path: Path,
    *,
    top_k: int = 20,
    min_state_probability: float = 0.55,
) -> dict[str, Any]:
    payload = _load_json(hard_cases_path)
    clips = payload.get("clips") or payload.get("top_hard_cases") or []
    review_items: list[dict[str, Any]] = []

    for clip in clips[:top_k]:
        candidates: list[dict[str, Any]] = []
        duration_seconds = float(clip.get("duration_seconds") or 0.0)
        max_state_probs = clip.get("max_state_probs", {})
        first_ts = clip.get("first_high_confidence_ts", {})
        for state, window_seconds in STATE_WINDOW_SECONDS.items():
            score = float(max_state_probs.get(state, 0.0))
            timestamp = first_ts.get(state)
            if timestamp is None or score < min_state_probability:
                continue
            center = float(timestamp)
            half = window_seconds / 2.0
            start_time = max(0.0, center - half)
            end_time = min(duration_seconds if duration_seconds > 0 else center + half, center + half)
            candidates.append(
                {
                    "candidate_id": f"{clip['clip_id']}__{state}",
                    "recommended_label": state,
                    "status": "pending",
                    "accepted_label": None,
                    "confidence": score,
                    "start_time": start_time,
                    "end_time": end_time,
                    "reason": f"max_{state}={score:.4f}",
                }
            )
        if not candidates:
            continue
        review_items.append(
            {
                "clip_id": clip["clip_id"],
                "sample_id": clip.get("sample_id"),
                "input": clip.get("input"),
                "predictions": clip.get("predictions"),
                "annotations": clip.get("annotations"),
                "hard_score": clip.get("hard_score"),
                "candidates": candidates,
            }
        )

    return {
        "source": str(hard_cases_path),
        "clip_count": len(review_items),
        "clips": review_items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hard-cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-state-probability", type=float, default=0.55)
    args = parser.parse_args()

    queue = build_review_queue(
        args.hard_cases.resolve(),
        top_k=args.top_k,
        min_state_probability=args.min_state_probability,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)


if __name__ == "__main__":
    main()
