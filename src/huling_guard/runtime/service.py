from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
import uvicorn

from huling_guard.contracts import ScenePrior
from huling_guard.events import EventEngine, EventThresholds
from huling_guard.features import get_kinematic_feature_dim
from huling_guard.model import ScenePoseTemporalNet
from huling_guard.runtime.api import create_runtime_app
from huling_guard.runtime.pipeline import RealtimePipeline
from huling_guard.settings import AppSettings, load_settings


@dataclass(slots=True)
class RuntimeLaunchConfig:
    train_config_path: Path
    runtime_config_path: Path
    checkpoint_path: Path
    scene_prior_path: Path | None = None
    archive_root: Path | None = None
    device: str = "cuda"
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass(slots=True)
class RuntimeResources:
    train_settings: AppSettings
    runtime_settings: AppSettings
    model: ScenePoseTemporalNet
    device: str


def _build_model(settings: AppSettings, checkpoint_path: Path, device: str) -> ScenePoseTemporalNet:
    if settings.data is None or settings.model is None:
        raise ValueError("train config must contain data and model sections")
    expected_kinematic_dim = get_kinematic_feature_dim(settings.model.kinematic_feature_set)
    if settings.model.kinematic_dim != expected_kinematic_dim:
        raise ValueError(
            "model.kinematic_dim does not match model.kinematic_feature_set "
            f"({settings.model.kinematic_dim} != {expected_kinematic_dim})"
        )
    model = ScenePoseTemporalNet(
        num_joints=settings.data.num_joints,
        pose_dim=settings.model.pose_dim,
        kinematic_dim=settings.model.kinematic_dim,
        scene_dim=settings.model.scene_dim,
        hidden_dim=settings.model.hidden_dim,
        num_heads=settings.model.num_heads,
        depth=settings.model.depth,
        dropout=settings.model.dropout,
    )
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def _load_scene_prior(runtime_settings: AppSettings, explicit_path: Path | None) -> ScenePrior | None:
    scene_prior_path = explicit_path
    if scene_prior_path is None and runtime_settings.room is not None:
        scene_prior_path = runtime_settings.room.prior_path
    if scene_prior_path is None:
        return None
    return ScenePrior.load(scene_prior_path)


def load_runtime_resources(config: RuntimeLaunchConfig) -> RuntimeResources:
    train_settings = load_settings(config.train_config_path)
    runtime_settings = load_settings(config.runtime_config_path)
    if train_settings.data is None or runtime_settings.runtime is None:
        raise ValueError("train config must have data settings and runtime config must have runtime settings")
    if runtime_settings.runtime.window_size != train_settings.data.window_size:
        raise ValueError(
            "runtime window_size must match training window_size "
            f"({runtime_settings.runtime.window_size} != {train_settings.data.window_size})"
        )

    model = _build_model(
        settings=train_settings,
        checkpoint_path=config.checkpoint_path,
        device=config.device,
    )
    return RuntimeResources(
        train_settings=train_settings,
        runtime_settings=runtime_settings,
        model=model,
        device=config.device,
    )


def build_runtime_pipeline_from_resources(
    resources: RuntimeResources,
    *,
    scene_prior_path: Path | None = None,
) -> RealtimePipeline:
    if resources.train_settings.data is None or resources.runtime_settings.runtime is None:
        raise ValueError("runtime resources are missing data/runtime settings")
    runtime_settings = resources.runtime_settings
    scene_prior = _load_scene_prior(runtime_settings, scene_prior_path)
    thresholds = EventThresholds(
        near_fall_threshold=runtime_settings.runtime.near_fall_threshold,
        fall_threshold=runtime_settings.runtime.fall_threshold,
        recovery_threshold=runtime_settings.runtime.recovery_threshold,
        prolonged_lying_threshold=runtime_settings.runtime.prolonged_lying_threshold,
        prolonged_lying_seconds=float(runtime_settings.runtime.prolonged_lying_seconds),
        warning_cooldown_seconds=float(runtime_settings.runtime.warning_cooldown_seconds),
    )
    return RealtimePipeline(
        model=resources.model,
        scene_prior=scene_prior,
        event_engine=EventEngine(thresholds),
        device=resources.device,
        window_size=runtime_settings.runtime.window_size,
        inference_stride=runtime_settings.runtime.inference_stride,
        kinematic_feature_set=resources.train_settings.model.kinematic_feature_set,
    )


def build_runtime_pipeline(config: RuntimeLaunchConfig) -> RealtimePipeline:
    resources = load_runtime_resources(config)
    return build_runtime_pipeline_from_resources(
        resources,
        scene_prior_path=config.scene_prior_path,
    )


def serve_runtime(config: RuntimeLaunchConfig) -> None:
    pipeline = build_runtime_pipeline(config)
    app = create_runtime_app(pipeline, archive_root=config.archive_root)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")
