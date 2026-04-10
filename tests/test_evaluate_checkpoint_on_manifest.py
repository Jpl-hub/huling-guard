from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

torch = pytest.importorskip("torch")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_checkpoint_on_manifest as checkpoint_eval


class _DummyDataset:
    def __init__(
        self,
        *,
        manifest_path: Path,
        window_size: int,
        kinematic_feature_set: str,
        expected_kinematic_dim: int,
    ) -> None:
        assert manifest_path.name == "eval.jsonl"
        assert window_size == 4
        assert kinematic_feature_set == "v1"
        assert expected_kinematic_dim == 6
        self.entries = [
            SimpleNamespace(sample_id="sample_a"),
            SimpleNamespace(sample_id="sample_a"),
            SimpleNamespace(sample_id="sample_b"),
        ]
        self._rows = [
            {
                "poses": torch.zeros((4, 17, 2), dtype=torch.float32),
                "kinematics": torch.zeros((4, 6), dtype=torch.float32),
                "scene_features": torch.zeros((4, 8), dtype=torch.float32),
                "padding_mask": torch.zeros(4, dtype=torch.bool),
                "label_id": torch.tensor(1, dtype=torch.long),
            },
            {
                "poses": torch.zeros((4, 17, 2), dtype=torch.float32),
                "kinematics": torch.zeros((4, 6), dtype=torch.float32),
                "scene_features": torch.zeros((4, 8), dtype=torch.float32),
                "padding_mask": torch.zeros(4, dtype=torch.bool),
                "label_id": torch.tensor(1, dtype=torch.long),
            },
            {
                "poses": torch.zeros((4, 17, 2), dtype=torch.float32),
                "kinematics": torch.zeros((4, 6), dtype=torch.float32),
                "scene_features": torch.zeros((4, 8), dtype=torch.float32),
                "padding_mask": torch.zeros(4, dtype=torch.bool),
                "label_id": torch.tensor(3, dtype=torch.long),
            },
        ]

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        return self._rows[index]


class _DummyModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self._logits = [
            torch.tensor([0.0, 8.0, 0.0, 0.0, 0.0], dtype=torch.float32),
            torch.tensor([0.0, 7.0, 0.0, 0.0, 0.0], dtype=torch.float32),
            torch.tensor([0.0, 0.0, 0.0, 9.0, 0.0], dtype=torch.float32),
        ]
        self._offset = 0

    def forward(
        self,
        *,
        poses: torch.Tensor,
        kinematics: torch.Tensor,
        scene_features: torch.Tensor,
        padding_mask: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        batch_size = poses.shape[0]
        logits = torch.stack(self._logits[self._offset : self._offset + batch_size], dim=0)
        self._offset += batch_size
        return {"clip_logits": logits}


def test_evaluate_checkpoint_on_manifest_builds_window_and_sample_summaries(monkeypatch) -> None:
    settings = SimpleNamespace(
        data=SimpleNamespace(window_size=4),
        model=SimpleNamespace(kinematic_feature_set="v1"),
        training=SimpleNamespace(batch_size=2, num_workers=0, pin_memory=False, amp=False),
    )

    monkeypatch.setattr(checkpoint_eval, "load_settings", lambda _: settings)
    monkeypatch.setattr(checkpoint_eval, "PoseWindowDataset", _DummyDataset)
    monkeypatch.setattr(checkpoint_eval, "get_kinematic_feature_dim", lambda _: 6)
    monkeypatch.setattr(
        checkpoint_eval,
        "_build_model",
        lambda *, train_config_path, checkpoint_path, device: _DummyModel(),
    )

    summary = checkpoint_eval.evaluate_checkpoint_on_manifest(
        train_config_path=Path("train.yaml"),
        checkpoint_path=Path("selected.pt"),
        eval_manifest_path=Path("eval.jsonl"),
        device="cpu",
    )

    assert summary["window"]["accuracy"] == 1.0
    assert summary["sample"]["accuracy"] == 1.0
    assert summary["sample"]["num_samples"] == 2
    assert summary["sample"]["num_windows"] == 3
    assert summary["sample"]["per_class"]["fall"]["support"] == 1
    assert summary["sample"]["per_class"]["prolonged_lying"]["support"] == 1


def test_build_markdown_renders_window_and_sample_sections() -> None:
    markdown = checkpoint_eval.build_markdown(
        {
            "checkpoint_path": "selected.pt",
            "eval_manifest_path": "val.jsonl",
            "window": {"accuracy": 0.9, "macro_f1": 0.8, "weighted_f1": 0.85},
            "sample": {
                "accuracy": 0.88,
                "macro_f1": 0.77,
                "weighted_f1": 0.81,
                "num_samples": 12,
                "num_windows": 48,
            },
        }
    )

    assert "# Checkpoint 重评估" in markdown
    assert "## 窗口级指标" in markdown
    assert "## 样本级指标" in markdown
    assert "- num_samples: 12" in markdown
