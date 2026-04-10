import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mine_hard_cases import mine_hard_cases


def test_mine_hard_cases_ranks_by_hard_score(tmp_path: Path) -> None:
    pred_a = tmp_path / "a.jsonl"
    pred_b = tmp_path / "b.jsonl"
    manifest = tmp_path / "processed_manifest.json"

    pred_a.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": 1.0,
                        "risk_score": 0.3,
                        "state_probs": {
                            "near_fall": 0.2,
                            "fall": 0.15,
                            "recovery": 0.1,
                            "prolonged_lying": 0.05,
                        },
                        "incidents": [],
                    }
                ),
                json.dumps(
                    {
                        "timestamp": 2.0,
                        "risk_score": 0.4,
                        "state_probs": {
                            "near_fall": 0.5,
                            "fall": 0.2,
                            "recovery": 0.15,
                            "prolonged_lying": 0.1,
                        },
                        "incidents": [{"kind": "near_fall_warning"}],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    pred_b.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": 1.5,
                        "risk_score": 0.7,
                        "state_probs": {
                            "near_fall": 0.3,
                            "fall": 0.82,
                            "recovery": 0.2,
                            "prolonged_lying": 0.65,
                        },
                        "incidents": [{"kind": "confirmed_fall"}, {"kind": "prolonged_lying"}],
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {"clip_id": "clip_a", "predictions": str(pred_a)},
                    {"clip_id": "clip_b", "predictions": str(pred_b)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = mine_hard_cases(manifest)

    assert summary["clip_count"] == 2
    assert summary["clips"][0]["clip_id"] == "clip_b"
    assert summary["clips"][0]["incident_counts"]["confirmed_fall"] == 1
    assert summary["clips"][1]["incident_counts"]["near_fall_warning"] == 1
