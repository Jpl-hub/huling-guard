import json
from pathlib import Path

from huling_guard.runtime.batch_manifest import load_batch_video_manifest


def test_load_batch_video_manifest_resolves_relative_paths(tmp_path: Path) -> None:
    manifest_path = tmp_path / "batch_manifest.json"
    payload = {
        "clips": [
            {
                "clip_id": "clip_a",
                "input": "videos/clip_a.mp4",
                "sample_id": "public__clip_a",
                "expected_state": "normal",
                "expected_incident": False,
                "annotations": "annotations/clip_a.json",
                "scene_prior": "priors/room_a.json",
            },
            {
                "input": "videos/clip_b.mp4",
            },
        ]
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    items = load_batch_video_manifest(manifest_path)

    assert len(items) == 2
    assert items[0].clip_id == "clip_a"
    assert items[0].sample_id == "public__clip_a"
    assert items[0].expected_state == "normal"
    assert items[0].expected_incident is False
    assert items[0].input_path == (tmp_path / "videos" / "clip_a.mp4").resolve()
    assert items[0].annotations_path == (tmp_path / "annotations" / "clip_a.json").resolve()
    assert items[0].scene_prior_path == (tmp_path / "priors" / "room_a.json").resolve()
    assert items[1].clip_id == "clip_b"
    assert items[1].sample_id is None
    assert items[1].expected_state is None
    assert items[1].expected_incident is None
    assert items[1].annotations_path is None
    assert items[1].scene_prior_path is None
