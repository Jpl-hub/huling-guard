from __future__ import annotations

import torch
import torch.nn.functional as F


def build_class_balance_weights(
    class_counts: torch.Tensor,
    beta: float,
) -> torch.Tensor:
    counts = class_counts.to(dtype=torch.float32)
    if counts.ndim != 1:
        raise ValueError('class_counts must be a 1D tensor')
    if not 0.0 <= beta < 1.0:
        raise ValueError('class balance beta must satisfy 0 <= beta < 1')

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


def _normalized_sample_weights(
    sample_weights: torch.Tensor | None,
    *,
    reference: torch.Tensor,
) -> torch.Tensor | None:
    if sample_weights is None:
        return None
    weights = sample_weights.to(device=reference.device, dtype=reference.dtype).reshape(-1)
    mean = weights.mean().clamp_min(1e-6)
    return weights / mean


def compute_losses(
    outputs: dict[str, torch.Tensor],
    label_ids: torch.Tensor,
    risk_targets: torch.Tensor,
    frame_quality_targets: torch.Tensor | None = None,
    padding_mask: torch.Tensor | None = None,
    class_weights: torch.Tensor | None = None,
    sample_weights: torch.Tensor | None = None,
    clip_focal_gamma: float = 0.0,
    risk_loss_weight: float = 0.3,
    quality_loss_weight: float = 0.15,
) -> dict[str, torch.Tensor]:
    normalized_weights = _normalized_sample_weights(sample_weights, reference=outputs['clip_logits'])

    ce = F.cross_entropy(
        outputs['clip_logits'],
        label_ids,
        weight=class_weights,
        reduction='none',
    )
    if clip_focal_gamma > 0.0:
        probs = torch.softmax(outputs['clip_logits'], dim=-1)
        pt = probs.gather(dim=1, index=label_ids.unsqueeze(1)).squeeze(1).clamp_min(1e-6)
        clip_terms = torch.pow(1.0 - pt, clip_focal_gamma) * ce
    else:
        clip_terms = ce
    if normalized_weights is not None:
        clip_loss = (clip_terms * normalized_weights).mean()
    else:
        clip_loss = clip_terms.mean()

    risk_terms = F.binary_cross_entropy_with_logits(
        outputs['risk_logits'],
        risk_targets,
        reduction='none',
    )
    if normalized_weights is not None:
        risk_loss = (risk_terms * normalized_weights).mean()
    else:
        risk_loss = risk_terms.mean()

    quality_loss = clip_loss.new_zeros(())
    if (
        quality_loss_weight > 0.0
        and frame_quality_targets is not None
        and 'frame_quality_logits' in outputs
    ):
        quality_terms = F.binary_cross_entropy_with_logits(
            outputs['frame_quality_logits'],
            frame_quality_targets,
            reduction='none',
        )
        if normalized_weights is not None:
            sample_weight_matrix = normalized_weights.unsqueeze(1)
        else:
            sample_weight_matrix = torch.ones_like(quality_terms)[:, :1]
        if padding_mask is not None:
            valid_mask = (~padding_mask).to(dtype=quality_terms.dtype)
            weighted_mask = valid_mask * sample_weight_matrix
            denom = weighted_mask.sum().clamp_min(1.0)
            quality_loss = (quality_terms * weighted_mask).sum() / denom
        else:
            quality_loss = (quality_terms * sample_weight_matrix).mean()

    total = clip_loss + (risk_loss_weight * risk_loss) + (quality_loss_weight * quality_loss)
    return {
        'total': total,
        'clip_loss': clip_loss,
        'risk_loss': risk_loss,
        'quality_loss': quality_loss,
    }
