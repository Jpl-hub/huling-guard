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


def test_compute_losses_keeps_same_result_with_uniform_sample_weights() -> None:
    outputs = {
        'clip_logits': torch.tensor([[1.2, -0.3], [0.4, -0.2]], dtype=torch.float32),
        'risk_logits': torch.tensor([0.1, -0.4], dtype=torch.float32),
        'frame_quality_logits': torch.tensor([[0.2, 0.4], [-0.1, 0.3]], dtype=torch.float32),
    }
    kwargs = dict(
        outputs=outputs,
        label_ids=torch.tensor([0, 0], dtype=torch.long),
        risk_targets=torch.tensor([1.0, 0.0], dtype=torch.float32),
        frame_quality_targets=torch.tensor([[1.0, 1.0], [0.0, 1.0]], dtype=torch.float32),
        padding_mask=torch.tensor([[False, False], [False, False]], dtype=torch.bool),
        quality_loss_weight=0.2,
    )

    baseline = compute_losses(**kwargs)
    weighted = compute_losses(sample_weights=torch.tensor([1.0, 1.0], dtype=torch.float32), **kwargs)

    for key in ('clip_loss', 'risk_loss', 'quality_loss', 'total'):
        assert float(weighted[key].item()) == pytest.approx(float(baseline[key].item()))



def test_compute_losses_applies_sample_weights_to_all_loss_terms() -> None:
    outputs = {
        'clip_logits': torch.tensor([[1.0, -1.0], [5.0, -5.0]], dtype=torch.float32),
        'risk_logits': torch.tensor([0.0, -5.0], dtype=torch.float32),
        'frame_quality_logits': torch.tensor([[0.0, 0.0], [5.0, 5.0]], dtype=torch.float32),
    }
    kwargs = dict(
        outputs=outputs,
        label_ids=torch.tensor([1, 0], dtype=torch.long),
        risk_targets=torch.tensor([1.0, 0.0], dtype=torch.float32),
        frame_quality_targets=torch.tensor([[1.0, 1.0], [1.0, 1.0]], dtype=torch.float32),
        padding_mask=torch.tensor([[False, False], [False, False]], dtype=torch.bool),
        quality_loss_weight=0.2,
    )

    baseline = compute_losses(**kwargs)
    weighted = compute_losses(sample_weights=torch.tensor([3.0, 1.0], dtype=torch.float32), **kwargs)

    assert float(weighted['clip_loss'].item()) > float(baseline['clip_loss'].item())
    assert float(weighted['risk_loss'].item()) > float(baseline['risk_loss'].item())
    assert float(weighted['quality_loss'].item()) > float(baseline['quality_loss'].item())
    assert float(weighted['total'].item()) > float(baseline['total'].item())
