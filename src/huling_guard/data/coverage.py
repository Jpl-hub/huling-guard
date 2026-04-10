from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from huling_guard.data.manifests import load_jsonl, write_jsonl


@dataclass(slots=True)
class PoseCoverageSummary:
    raw_manifest_path: Path
    pose_manifest_path: Path
    raw_count: int
    pose_count: int
    matched_count: int
    missing_pose_count: int
    extra_pose_count: int
    missing_pose_sample_ids: list[str]
    extra_pose_sample_ids: list[str]

    @property
    def coverage_ratio(self) -> float:
        if self.raw_count == 0:
            return 1.0
        return self.matched_count / self.raw_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_manifest_path": str(self.raw_manifest_path),
            "pose_manifest_path": str(self.pose_manifest_path),
            "raw_count": self.raw_count,
            "pose_count": self.pose_count,
            "matched_count": self.matched_count,
            "missing_pose_count": self.missing_pose_count,
            "extra_pose_count": self.extra_pose_count,
            "coverage_ratio": self.coverage_ratio,
            "missing_pose_sample_ids": self.missing_pose_sample_ids,
            "extra_pose_sample_ids": self.extra_pose_sample_ids,
        }


def summarize_pose_manifest_coverage(
    raw_manifest_path: str | Path,
    pose_manifest_path: str | Path,
) -> PoseCoverageSummary:
    raw_path = Path(raw_manifest_path)
    pose_path = Path(pose_manifest_path)

    raw_rows = load_jsonl(raw_path)
    pose_rows = load_jsonl(pose_path)
    raw_ids = [str(row["sample_id"]) for row in raw_rows]
    pose_ids = [str(row["sample_id"]) for row in pose_rows]

    raw_id_set = set(raw_ids)
    pose_id_set = set(pose_ids)
    missing_pose_ids = sorted(raw_id_set.difference(pose_id_set))
    extra_pose_ids = sorted(pose_id_set.difference(raw_id_set))

    return PoseCoverageSummary(
        raw_manifest_path=raw_path,
        pose_manifest_path=pose_path,
        raw_count=len(raw_ids),
        pose_count=len(pose_ids),
        matched_count=len(raw_id_set.intersection(pose_id_set)),
        missing_pose_count=len(missing_pose_ids),
        extra_pose_count=len(extra_pose_ids),
        missing_pose_sample_ids=missing_pose_ids,
        extra_pose_sample_ids=extra_pose_ids,
    )


def export_missing_pose_entries(
    raw_manifest_path: str | Path,
    pose_manifest_path: str | Path,
    output_path: str | Path,
) -> PoseCoverageSummary:
    summary = summarize_pose_manifest_coverage(
        raw_manifest_path=raw_manifest_path,
        pose_manifest_path=pose_manifest_path,
    )
    if summary.missing_pose_count == 0:
        write_jsonl(output_path, [])
        return summary

    missing_ids = set(summary.missing_pose_sample_ids)
    missing_rows = [
        row for row in load_jsonl(raw_manifest_path) if str(row["sample_id"]) in missing_ids
    ]
    write_jsonl(output_path, missing_rows)
    return summary
