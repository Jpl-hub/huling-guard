from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from huling_guard.data.manifests import load_jsonl, write_jsonl


def _subject_value(row: dict[str, Any], subject_key: str) -> str:
    metadata = row.get("metadata")
    if subject_key == "dataset_subject":
        if not isinstance(metadata, dict):
            raise KeyError("dataset_subject requires metadata.dataset and metadata.subject")
        dataset = metadata.get("dataset")
        subject = metadata.get("subject")
        if dataset is None or subject is None:
            raise KeyError("dataset_subject requires metadata.dataset and metadata.subject")
        return f"{dataset}:{subject}"
    if isinstance(metadata, dict) and subject_key in metadata:
        return str(metadata[subject_key])
    if subject_key in row:
        return str(row[subject_key])
    raise KeyError(f"subject key '{subject_key}' not present in row")


@dataclass(slots=True)
class SubjectSplitResult:
    train_count: int
    val_count: int


def split_manifest_by_subject(
    input_path: str | Path,
    train_output_path: str | Path,
    val_output_path: str | Path,
    val_subjects: set[str],
    subject_key: str = "subject",
) -> SubjectSplitResult:
    train_rows: list[dict[str, Any]] = []
    val_rows: list[dict[str, Any]] = []
    for row in load_jsonl(input_path):
        subject = _subject_value(row, subject_key)
        if subject in val_subjects:
            val_rows.append(row)
        else:
            train_rows.append(row)
    return SubjectSplitResult(
        train_count=write_jsonl(train_output_path, train_rows),
        val_count=write_jsonl(val_output_path, val_rows),
    )


def filter_manifest_by_sample_ids(
    input_path: str | Path,
    sample_ids: set[str],
    output_path: str | Path,
) -> int:
    rows = [row for row in load_jsonl(input_path) if str(row.get("sample_id")) in sample_ids]
    return write_jsonl(output_path, rows)


def split_pose_manifest_by_raw_split(
    raw_train_path: str | Path,
    raw_val_path: str | Path,
    pose_manifest_path: str | Path,
    train_output_path: str | Path,
    val_output_path: str | Path,
) -> SubjectSplitResult:
    train_ids = {str(row["sample_id"]) for row in load_jsonl(raw_train_path)}
    val_ids = {str(row["sample_id"]) for row in load_jsonl(raw_val_path)}
    return SubjectSplitResult(
        train_count=filter_manifest_by_sample_ids(pose_manifest_path, train_ids, train_output_path),
        val_count=filter_manifest_by_sample_ids(pose_manifest_path, val_ids, val_output_path),
    )
