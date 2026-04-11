from __future__ import annotations

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from huling_guard.train import PoseWindowDataset


def test_pose_window_dataset_sampler_weights_include_hard_interval_weight(tmp_path: Path) -> None:
    manifest = tmp_path / "windows.jsonl"
    rows = [
        {
            "sample_id": "normal_easy",
            "pose_path": str(tmp_path / "easy.npz"),
            "internal_label": "normal",
            "external_label": "adl",
            "start": 0,
            "end": 64,
        },
        {
            "sample_id": "normal_hard",
            "pose_path": str(tmp_path / "hard.npz"),
            "internal_label": "normal",
            "external_label": "adl",
            "start": 0,
            "end": 64,
            "sample_weight": 4.0,
        },
    ]
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    dataset = PoseWindowDataset(manifest_path=manifest, window_size=64)
    weights = dataset.sample_weights().tolist()

    assert weights == pytest.approx([0.5, 2.0])
