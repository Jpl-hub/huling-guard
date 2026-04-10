from __future__ import annotations

import torch
import torch.nn.functional as F


def build_class_balance_weights(
    class_counts: torch.Tensor,
    beta: float,
) -> torch.Tensor:
    counts = class_counts.to(dtype=torch.float32)
    if counts.ndim != 1:
        raise ValueError("class_counts must be a 1D tensor")
    if not 0.0 <= beta < 1.0:
        raise ValueError("class balance beta must satisfy 0 <= beta < 1")

    if beta == 0.0:
        weights = torch.ones_like(counts)
        weights[counts == 0] = 0.0
        return weights

    effective_num = 1.0 - torch.pow(torch.full_like(counts, beta), counts)
    weights = torch.zeros_like(counts)
    valid = counts > 0
    weights[valid] = (1.0 - beta) / effective_num[valid]
    if valid.any():
        weights[valid] = weights[valid] * (valid.sum() / weights[valid].sum().clamp_min(1e-12))
    return weights


def compute_losses(
    outputs: dict[str, torch.Tensor],
    label_ids: torch.Tensor,
    risk_targets: torch.Tensor,
    class_weights: torch.Tensor | None = None,
    clip_focal_gamma: float = 0.0,
    risk_loss_weight: float = 0.3,
) -> dict[str, torch.Tensor]:
    if clip_focal_gamma > 0.0:
        ce = F.cross_entropy(
            outputs["clip_logits"],
            label_ids,
            weight=class_weights,
            reduction="none",
        )
        probs = torch.softmax(outputs["clip_logits"], dim=-1)
        pt = probs.gather(dim=1, index=label_ids.unsqueeze(1)).squeeze(1).clamp_min(1e-6)
        focal_factor = torch.pow(1.0 - pt, clip_focal_gamma)
        clip_loss = (focal_factor * ce).mean()
    else:
        clip_loss = F.cross_entropy(outputs["clip_logits"], label_ids, weight=class_weights)
    risk_loss = F.binary_cross_entropy_with_logits(outputs["risk_logits"], risk_targets)
    total = clip_loss + risk_loss_weight * risk_loss
    return {
        "total": total,
        "clip_loss": clip_loss,
        "risk_loss": risk_loss,
    }
