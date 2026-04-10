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
        self.register_buffer("encoding", encoding.unsqueeze(0), persistent=False)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return inputs + self.encoding[:, : inputs.size(1)]


class ScenePoseTemporalNet(nn.Module):
    def __init__(
        self,
        num_joints: int = 17,
        pose_dim: int = 3,
        kinematic_dim: int = 8,
        scene_dim: int = 8,
        hidden_dim: int = 192,
        num_heads: int = 6,
        depth: int = 4,
        dropout: float = 0.1,
        num_classes: int = 5,
    ) -> None:
        super().__init__()
        joint_hidden = hidden_dim // 2
        self.num_joints = num_joints
        self.pose_encoder = nn.Sequential(
            nn.Linear(pose_dim, joint_hidden),
            nn.GELU(),
            nn.Linear(joint_hidden, joint_hidden),
        )
        self.fusion = nn.Linear(joint_hidden + kinematic_dim + scene_dim, hidden_dim)
        self.temporal_blocks = nn.ModuleList(
            ResidualTemporalBlock(hidden_dim=hidden_dim, dropout=dropout) for _ in range(depth)
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
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

    def _masked_pool(self, inputs: torch.Tensor, padding_mask: torch.Tensor | None) -> torch.Tensor:
        if padding_mask is None:
            return inputs.mean(dim=1)
        valid = (~padding_mask).float().unsqueeze(-1)
        denom = valid.sum(dim=1).clamp_min(1.0)
        return (inputs * valid).sum(dim=1) / denom

    def forward(
        self,
        poses: torch.Tensor,
        kinematics: torch.Tensor,
        scene_features: torch.Tensor,
        padding_mask: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        _, _, joints, _ = poses.shape
        if joints != self.num_joints:
            raise ValueError(f"expected {self.num_joints} joints, got {joints}")

        joint_tokens = self.pose_encoder(poses)
        spatial_summary = joint_tokens.mean(dim=2)
        fused = torch.cat([spatial_summary, kinematics, scene_features], dim=-1)
        outputs = self.fusion(fused)
        outputs = self.position_encoding(outputs)
        for block in self.temporal_blocks:
            outputs = block(outputs)
        outputs = self.transformer(outputs, src_key_padding_mask=padding_mask)
        outputs = self.norm(outputs)
        pooled = self._masked_pool(outputs, padding_mask)
        return {
            "frame_logits": self.frame_head(outputs),
            "clip_logits": self.clip_head(pooled),
            "risk_logits": self.risk_head(pooled).squeeze(-1),
            "embedding": pooled,
        }
