from __future__ import annotations

import pytest

torch = pytest.importorskip('torch')

from huling_guard.model.losses import compute_losses


def test_compute_losses_masks_padded_quality_frames() -> None:
    outputs = {
        'clip_logits': torch.tensor([[2.0, -1.0]], dtype=torch.float32),
        'risk_logits': torch.tensor([0.5], dtype=torch.float32),
        'frame_quality_logits': torch.tensor([[2.0, -2.0, 0.0]], dtype=torch.float32),
    }
    losses = compute_losses(
        outputs=outputs,
        label_ids=torch.tensor([0], dtype=torch.long),
        risk_targets=torch.tensor([1.0], dtype=torch.float32),
        frame_quality_targets=torch.tensor([[1.0, 1.0, 0.0]], dtype=torch.float32),
        padding_mask=torch.tensor([[False, False, True]], dtype=torch.bool),
        quality_loss_weight=0.2,
    )
    assert 'quality_loss' in losses
    assert float(losses['quality_loss'].item()) > 0.0
    assert float(losses['total'].item()) > float(losses['clip_loss'].item())
