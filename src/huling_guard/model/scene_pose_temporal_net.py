from __future__ import annotations

import math

import torch
from torch import nn


class ResidualTemporalBlock(nn.Module):
    def __init__(self, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
        )
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        residual = inputs
        outputs = self.net(inputs.transpose(1, 2)).transpose(1, 2)
        outputs = self.dropout(outputs) + residual
        return self.norm(outputs)


class SinusoidalPositionEncoding(nn.Module):
    def __init__(self, hidden_dim: int, max_length: int = 512) -> None:
        super().__init__()
        position = torch.arange(max_length).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, hidden_dim, 2, dtype=torch.float32) * (-math.log(10000.0) / hidden_dim)
        )
        encoding = torch.zeros(max_length, hidden_dim)
        encoding[:, 0::2] = torch.sin(position * div_term)
        encoding[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('encoding', encoding.unsqueeze(0), persistent=False)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return inputs + self.encoding[:, : inputs.size(1)]


class ScenePoseTemporalNet(nn.Module):
    def __init__(
        self,
        num_joints: int = 17,
        pose_dim: int = 3,
        kinematic_dim: int = 8,
        scene_dim: int = 8,
        quality_dim: int = 3,
        hidden_dim: int = 192,
        num_heads: int = 6,
        depth: int = 4,
        dropout: float = 0.1,
        num_classes: int = 5,
    ) -> None:
        super().__init__()
        joint_hidden = hidden_dim // 2
        self.num_joints = num_joints
        self.quality_dim = max(0, int(quality_dim))
        self.pose_encoder = nn.Sequential(
            nn.Linear(pose_dim, joint_hidden),
            nn.GELU(),
            nn.Linear(joint_hidden, joint_hidden),
        )
        fusion_in_features = joint_hidden + kinematic_dim + scene_dim + self.quality_dim
        self.fusion = nn.Linear(fusion_in_features, hidden_dim)
        self.temporal_blocks = nn.ModuleList(
            ResidualTemporalBlock(hidden_dim=hidden_dim, dropout=dropout) for _ in range(depth)
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation='gelu',
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=max(1, depth // 2),
            enable_nested_tensor=False,
        )
        self.position_encoding = SinusoidalPositionEncoding(hidden_dim=hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.frame_head = nn.Linear(hidden_dim, num_classes)
        self.quality_head = (
            nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
            )
            if self.quality_dim > 0
            else None
        )
        self.clip_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )
        self.risk_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def _build_quality_features(self, confidences: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mean_confidence = confidences.mean(dim=-1, keepdim=True)
        visible_joint_ratio = (confidences >= 0.35).float().mean(dim=-1, keepdim=True)
        confident_joint_ratio = (confidences >= 0.60).float().mean(dim=-1, keepdim=True)
        quality_features = torch.cat(
            [mean_confidence, visible_joint_ratio, confident_joint_ratio],
            dim=-1,
        )
        frame_quality_prior = torch.clamp(
            (0.60 * mean_confidence) + (0.40 * visible_joint_ratio),
            min=0.05,
            max=1.0,
        )
        return quality_features, frame_quality_prior

    def _select_quality_features(self, quality_features: torch.Tensor) -> torch.Tensor | None:
        if self.quality_dim <= 0:
            return None
        if quality_features.size(-1) >= self.quality_dim:
            return quality_features[..., : self.quality_dim]
        padding = torch.zeros(
            *quality_features.shape[:-1],
            self.quality_dim - quality_features.size(-1),
            device=quality_features.device,
            dtype=quality_features.dtype,
        )
        return torch.cat([quality_features, padding], dim=-1)

    def _quality_weighted_spatial_summary(
        self,
        joint_tokens: torch.Tensor,
        confidences: torch.Tensor,
    ) -> torch.Tensor:
        weights = confidences.unsqueeze(-1).clamp(0.0, 1.0)
        denom = weights.sum(dim=2).clamp_min(1e-6)
        return (joint_tokens * weights).sum(dim=2) / denom

    def _masked_pool(
        self,
        inputs: torch.Tensor,
        padding_mask: torch.Tensor | None,
        frame_quality: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if padding_mask is None and frame_quality is None:
            return inputs.mean(dim=1)

        if frame_quality is None:
            weights = torch.ones(inputs.shape[:2], device=inputs.device, dtype=inputs.dtype)
        else:
            weights = frame_quality.squeeze(-1).to(dtype=inputs.dtype)

        if padding_mask is not None:
            weights = weights.masked_fill(padding_mask, 0.0)

        weights = weights.unsqueeze(-1)
        denom = weights.sum(dim=1).clamp_min(1e-6)
        return (inputs * weights).sum(dim=1) / denom

    def forward(
        self,
        poses: torch.Tensor,
        kinematics: torch.Tensor,
        scene_features: torch.Tensor,
        padding_mask: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        _, _, joints, _ = poses.shape
        if joints != self.num_joints:
            raise ValueError(f'expected {self.num_joints} joints, got {joints}')

        confidences = poses[..., 2].clamp(0.0, 1.0)
        joint_tokens = self.pose_encoder(poses)
        spatial_summary = self._quality_weighted_spatial_summary(joint_tokens, confidences)
        quality_features, frame_quality_prior = self._build_quality_features(confidences)

        fusion_parts = [spatial_summary, kinematics, scene_features]
        selected_quality = self._select_quality_features(quality_features)
        if selected_quality is not None:
            fusion_parts.append(selected_quality)
        fused = torch.cat(fusion_parts, dim=-1)

        outputs = self.fusion(fused)
        outputs = self.position_encoding(outputs)
        for block in self.temporal_blocks:
            outputs = block(outputs)
        outputs = self.transformer(outputs, src_key_padding_mask=padding_mask)
        outputs = self.norm(outputs)

        frame_quality_prior = frame_quality_prior.squeeze(-1)
        if self.quality_head is not None:
            frame_quality_logits = self.quality_head(outputs).squeeze(-1)
            learned_frame_quality = torch.sigmoid(frame_quality_logits)
            frame_quality = torch.clamp(
                (0.55 * frame_quality_prior) + (0.45 * learned_frame_quality),
                min=0.0,
                max=1.0,
            )
        else:
            frame_quality = frame_quality_prior
            frame_quality_logits = torch.logit(frame_quality.clamp(1e-4, 1 - 1e-4))

        pooled = self._masked_pool(outputs, padding_mask, frame_quality=frame_quality.unsqueeze(-1))
        return {
            'frame_logits': self.frame_head(outputs),
            'clip_logits': self.clip_head(pooled),
            'risk_logits': self.risk_head(pooled).squeeze(-1),
            'embedding': pooled,
            'frame_quality': frame_quality,
            'frame_quality_prior': frame_quality_prior,
            'frame_quality_logits': frame_quality_logits,
        }
