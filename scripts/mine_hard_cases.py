from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TARGET_STATES = ("near_fall", "fall", "recovery", "prolonged_lying")
TARGET_INCIDENTS = ("near_fall_warning", "confirmed_fall", "recovery", "prolonged_lying")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_prediction_jsonl(path: Path) -> dict[str, Any]:
    max_state_probs = {state: 0.0 for state in TARGET_STATES}
    first_high_confidence_ts = {state: None for state in TARGET_STATES}
    incident_counts = {kind: 0 for kind in TARGET_INCIDENTS}
    max_risk_score = 0.0
    frames = 0
    last_timestamp = 0.0

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            frames += 1
            timestamp = float(payload.get("timestamp", 0.0))
            last_timestamp = max(last_timestamp, timestamp)
            state_probs = payload.get("state_probs", {})
            max_risk_score = max(max_risk_score, float(payload.get("risk_score", 0.0)))
            for state in TARGET_STATES:
                score = float(state_probs.get(state, 0.0))
                if score > max_state_probs[state]:
                    max_state_probs[state] = score
                if score >= 0.6 and first_high_confidence_ts[state] is None:
                    first_high_confidence_ts[state] = timestamp
            for incident in payload.get("incidents", []):
                kind = str(incident.get("kind"))
                if kind in incident_counts:
                    incident_counts[kind] += 1

    hard_score = (
        max_state_probs["near_fall"] * 0.35
        + max_state_probs["fall"] * 0.35
        + max_state_probs["recovery"] * 0.15
        + max_state_probs["prolonged_lying"] * 0.15
        + max_risk_score * 0.25
    )
    return {
        "frames": frames,
        "duration_seconds": last_timestamp,
        "max_risk_score": max_risk_score,
        "max_state_probs": max_state_probs,
        "first_high_confidence_ts": first_high_confidence_ts,
        "incident_counts": incident_counts,
        "hard_score": hard_score,
    }


def mine_hard_cases(processed_manifest_path: Path) -> dict[str, Any]:
    processed_manifest = _load_json(processed_manifest_path)
    clips = processed_manifest.get("clips", [])
    results: list[dict[str, Any]] = []

    for clip in clips:
        prediction_path = Path(clip["predictions"])
        stats = _scan_prediction_jsonl(prediction_path)
        results.append(
            {
                "clip_id": clip["clip_id"],
                "input": clip.get("input"),
                "annotations": clip.get("annotations"),
                "predictions": str(prediction_path),
                "frames": stats["frames"],
                "duration_seconds": stats["duration_seconds"],
                "max_risk_score": stats["max_risk_score"],
                "max_state_probs": stats["max_state_probs"],
                "first_high_confidence_ts": stats["first_high_confidence_ts"],
                "incident_counts": stats["incident_counts"],
                "hard_score": stats["hard_score"],
            }
        )

    ranked = sorted(results, key=lambda item: item["hard_score"], reverse=True)
    return {
        "clip_count": len(ranked),
        "top_hard_cases": ranked[:20],
        "clips": ranked,
    }


def _build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 难例挖掘汇总",
        "",
        f"- 视频数量: {summary['clip_count']}",
        "",
        "## Top 20 难例",
    ]
    for clip in summary["top_hard_cases"]:
        max_probs = clip["max_state_probs"]
        incidents = clip["incident_counts"]
        lines.append(
            (
                f"- {clip['clip_id']}: hard_score={clip['hard_score']:.4f} "
                f"risk={clip['max_risk_score']:.4f} "
                f"near_fall={max_probs['near_fall']:.4f} "
                f"fall={max_probs['fall']:.4f} "
                f"recovery={max_probs['recovery']:.4f} "
                f"prolonged_lying={max_probs['prolonged_lying']:.4f} "
                f"incidents={incidents}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-manifest", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = mine_hard_cases(args.processed_manifest.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output_json}", flush=True)

    markdown = _build_markdown(summary)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
