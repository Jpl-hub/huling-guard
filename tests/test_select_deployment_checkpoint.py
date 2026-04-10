import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import select_deployment_checkpoint as selector


def test_select_deployment_checkpoint_prefers_best_sample_macro_f1(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    checkpoint_a = run_dir / "checkpoints" / "epoch_003_macro_f1_0.4100.pt"
    checkpoint_b = run_dir / "checkpoints" / "epoch_007_macro_f1_0.4700.pt"
    checkpoint_a.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_a.write_bytes(b"a")
    checkpoint_b.write_bytes(b"b")

    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "best_epoch": 7,
                "selection_metric": "macro_f1",
                "best_metrics": {"macro_f1": 0.47},
                "candidate_checkpoints": [
                    {
                        "epoch": 3,
                        "selection_metric": "macro_f1",
                        "selection_scope": "eval",
                        "metric_value": 0.41,
                        "checkpoint_path": str(checkpoint_a),
                    },
                    {
                        "epoch": 7,
                        "selection_metric": "macro_f1",
                        "selection_scope": "eval",
                        "metric_value": 0.47,
                        "checkpoint_path": str(checkpoint_b),
                    },
                ],
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "history.json").write_text(
        json.dumps(
            [
                {"epoch": 3, "eval": {"macro_f1": 0.41}},
                {"epoch": 7, "eval": {"macro_f1": 0.47}},
            ],
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    train_config = tmp_path / "train.yaml"
    runtime_template = tmp_path / "runtime_template.yaml"
    runtime_output = tmp_path / "runtime_output.yaml"
    train_config.write_text("data: {}\nmodel: {}\ntraining: {}\n", encoding="utf-8")
    runtime_template.write_text("runtime: {}\n", encoding="utf-8")

    sample_summaries = {
        str(checkpoint_a.resolve()): {
            "num_samples": 10,
            "num_windows": 20,
            "accuracy": 0.72,
            "macro_f1": 0.58,
            "weighted_f1": 0.70,
            "per_class": {
                "fall": {"f1": 0.61},
                "recovery": {"f1": 0.10},
                "prolonged_lying": {"f1": 0.44},
            },
        },
        str(checkpoint_b.resolve()): {
            "num_samples": 10,
            "num_windows": 20,
            "accuracy": 0.75,
            "macro_f1": 0.63,
            "weighted_f1": 0.73,
            "per_class": {
                "fall": {"f1": 0.59},
                "recovery": {"f1": 0.20},
                "prolonged_lying": {"f1": 0.41},
            },
        },
    }

    def fake_evaluate_sample_classification(*, train_config_path: Path, checkpoint_path: Path, device: str):
        assert train_config_path == train_config.resolve()
        assert device == "cuda"
        return sample_summaries[str(checkpoint_path.resolve())]

    def fake_calibrate_runtime_thresholds(
        *,
        train_config_path: str | Path,
        runtime_config_path: str | Path,
        checkpoint_path: str | Path,
        output_path: str | Path,
        device: str = "cuda",
        threshold_step: float = 0.02,
    ) -> Path:
        assert Path(checkpoint_path).name == "selected.pt"
        Path(output_path).write_text("runtime: {}\n", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr(selector, "evaluate_sample_classification", fake_evaluate_sample_classification)
    monkeypatch.setattr(selector, "calibrate_runtime_thresholds", fake_calibrate_runtime_thresholds)

    summary = selector.select_deployment_checkpoint(
        run_dir=run_dir,
        train_config_path=train_config,
        runtime_template_path=runtime_template,
        runtime_output_path=runtime_output,
        device="cuda",
    )

    assert summary["selected"]["epoch"] == 7
    assert Path(summary["selected"]["checkpoint_path"]).is_file()
    assert Path(summary["selected"]["checkpoint_path"]).read_bytes() == b"b"
    assert runtime_output.is_file()
