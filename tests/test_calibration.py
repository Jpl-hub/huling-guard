from pathlib import Path

from huling_guard.calibration import _sync_runtime_payload_with_train_settings, select_best_threshold
from huling_guard.settings import AppSettings, DataSettings


def test_select_best_threshold_prefers_high_f1() -> None:
    labels = [1, 1, 0, 0]
    scores = [0.92, 0.73, 0.61, 0.15]

    result = select_best_threshold(
        labels,
        scores,
        default_threshold=0.6,
        threshold_grid=[0.4, 0.6, 0.8],
    )

    assert result["threshold"] == 0.6
    assert result["f1"] > 0.0
    assert result["selected"] is True


def test_select_best_threshold_keeps_default_without_support() -> None:
    labels = [0, 0, 0]
    scores = [0.4, 0.6, 0.1]

    result = select_best_threshold(
        labels,
        scores,
        default_threshold=0.55,
        threshold_grid=[0.2, 0.4, 0.6],
    )

    assert result["threshold"] == 0.55
    assert result["support"] == 0
    assert result["selected"] is False


def test_sync_runtime_payload_with_train_settings_updates_window_size() -> None:
    payload = {
        "runtime": {
            "window_size": 64,
            "inference_stride": 4,
        }
    }
    settings = AppSettings(
        data=DataSettings(
            manifest_path=Path("train.jsonl"),
            eval_manifest_path=None,
            window_size=32,
            stride=8,
            num_joints=17,
        )
    )

    updated = _sync_runtime_payload_with_train_settings(payload, settings)

    assert updated["runtime"]["window_size"] == 32
    assert updated["runtime"]["inference_stride"] == 4
