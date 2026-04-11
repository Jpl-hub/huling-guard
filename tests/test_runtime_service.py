from pathlib import Path

import pytest

pytest.importorskip("torch")

from huling_guard.runtime.service import _resolve_runtime_config_relative_paths
from huling_guard.settings import AppSettings, RoomSettings


def test_runtime_config_relative_room_prior_resolves_from_config_directory(tmp_path: Path) -> None:
    runtime_config = tmp_path / "release" / "config" / "runtime_config.yaml"
    settings = AppSettings(
        room=RoomSettings(
            prior_path=Path("sample_room_prior.json"),
            camera_name="sample_room",
        )
    )

    _resolve_runtime_config_relative_paths(settings, runtime_config)

    assert settings.room is not None
    assert settings.room.prior_path == (runtime_config.parent / "sample_room_prior.json").resolve()


def test_runtime_config_absolute_room_prior_is_kept(tmp_path: Path) -> None:
    runtime_config = tmp_path / "release" / "config" / "runtime_config.yaml"
    absolute_prior = (tmp_path / "priors" / "room.json").resolve()
    settings = AppSettings(
        room=RoomSettings(
            prior_path=absolute_prior,
            camera_name="sample_room",
        )
    )

    _resolve_runtime_config_relative_paths(settings, runtime_config)

    assert settings.room is not None
    assert settings.room.prior_path == absolute_prior
