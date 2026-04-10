from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
testclient = pytest.importorskip("fastapi.testclient")
pytest.importorskip("torch")

from huling_guard.events import EventThresholds
from huling_guard.events import Incident
from huling_guard.runtime.api import create_runtime_app
from huling_guard.runtime.archive_store import RuntimeArchiveStore
from huling_guard.runtime.pipeline import PipelineSnapshot


class _DummyPipeline:
    def __init__(self) -> None:
        self.window_size = 64
        self.inference_stride = 4
        self.device = "cpu"
        self.kinematic_feature_set = "v2"
        self.scene_prior = object()
        self.event_engine = SimpleNamespace(thresholds=EventThresholds())
        self.last_keypoints = None
        self._snapshot = PipelineSnapshot(
            timestamp=12.5,
            ready=True,
            observed_frames=64,
            window_size=64,
            window_span_seconds=2.1,
            state_probs={
                "normal": 0.1,
                "near_fall": 0.2,
                "fall": 0.6,
                "recovery": 0.05,
                "prolonged_lying": 0.05,
            },
            predicted_state="fall",
            confidence=0.6,
            risk_score=0.81,
            incidents=[],
        )

    def push_pose(self, keypoints, timestamp: float) -> PipelineSnapshot:
        self.last_keypoints = keypoints
        self._snapshot = PipelineSnapshot(
            timestamp=timestamp,
            ready=True,
            observed_frames=64,
            window_size=64,
            window_span_seconds=2.2,
            state_probs=self._snapshot.state_probs,
            predicted_state="fall",
            confidence=0.6,
            risk_score=0.81,
            incidents=[
                Incident(
                    kind="confirmed_fall",
                    timestamp=timestamp,
                    confidence=0.91,
                    payload={"source": "test"},
                )
            ],
        )
        return self._snapshot

    def reset(self) -> None:
        self._snapshot = PipelineSnapshot(
            timestamp=0.0,
            ready=False,
            observed_frames=0,
            window_size=64,
            window_span_seconds=0.0,
        )


def test_runtime_api_exposes_meta_and_dashboard() -> None:
    app = create_runtime_app(_DummyPipeline())
    client = testclient.TestClient(app)

    meta = client.get("/meta")
    assert meta.status_code == 200
    assert meta.json()["kinematic_feature_set"] == "v2"
    assert meta.json()["scene_prior_loaded"] is True

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "护龄智守值守台" in dashboard.text
    assert "面向家庭照护和护理值守使用" in dashboard.text
    assert "状态概率" in dashboard.text
    assert "当前会话" in dashboard.text
    assert "重置当前会话" in dashboard.text
    assert "面板预览" in dashboard.text

    system_profile = client.get("/system-profile")
    assert system_profile.status_code == 200
    assert system_profile.json()["product_name"] == "护龄智守"
    assert system_profile.json()["runtime_profile"]["device"] == "cpu"

    push = client.post(
        "/pose-frame",
        json={"timestamp": 18.2, "keypoints": [[0.0, 0.0, 1.0] for _ in range(17)]},
    )
    assert push.status_code == 200

    summary = client.get("/summary")
    assert summary.status_code == 200
    assert summary.json()["incident_total"] == 1
    assert summary.json()["last_incident"]["kind"] == "confirmed_fall"

    timeline = client.get("/timeline?limit=10")
    assert timeline.status_code == 200
    assert timeline.json()["count"] == 1
    assert timeline.json()["items"][0]["predicted_state"] == "fall"

    session_report = client.get("/session-report")
    assert session_report.status_code == 200
    assert session_report.json()["incident_counts"]["confirmed_fall"] == 1
    assert session_report.json()["dominant_state"] == "fall"

    session_report_markdown = client.get("/session-report.md")
    assert session_report_markdown.status_code == 200
    assert "# 会话报告" in session_report_markdown.text
    assert "confirmed_fall" in session_report_markdown.text

    reset = client.post("/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"

    summary_after_reset = client.get("/summary")
    assert summary_after_reset.status_code == 200
    assert summary_after_reset.json()["incident_total"] == 0


def test_runtime_api_normalizes_pose_frame_when_frame_size_is_provided() -> None:
    pipeline = _DummyPipeline()
    app = create_runtime_app(pipeline)
    client = testclient.TestClient(app)

    push = client.post(
        "/pose-frame",
        json={
            "timestamp": 1.0,
            "frame_width": 1920,
            "frame_height": 1080,
            "keypoints": [[960.0, 540.0, 1.0] for _ in range(17)],
        },
    )

    assert push.status_code == 200
    assert pipeline.last_keypoints is not None
    assert pipeline.last_keypoints.shape == (17, 3)
    assert float(pipeline.last_keypoints[0, 0]) == pytest.approx(0.5)
    assert float(pipeline.last_keypoints[0, 1]) == pytest.approx(0.5)


def test_runtime_api_archives_sessions(tmp_path) -> None:
    archive_root = tmp_path / "runtime_archive"
    app = create_runtime_app(_DummyPipeline(), archive_root=archive_root)
    client = testclient.TestClient(app)

    meta = client.get("/meta")
    assert meta.status_code == 200
    assert meta.json()["archive_enabled"] is True
    assert meta.json()["archive_backend"] == "sqlite"

    push = client.post(
        "/pose-frame",
        json={"timestamp": 19.6, "keypoints": [[0.0, 0.0, 1.0] for _ in range(17)]},
    )
    assert push.status_code == 200

    archive = client.post("/archive-session")
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"
    session_id = archive.json()["record"]["session_id"]

    archives = client.get("/archives")
    assert archives.status_code == 200
    assert archives.json()["count"] == 1
    assert archives.json()["items"][0]["session_id"] == session_id

    RuntimeArchiveStore(archive_root).archive_report(
        {
            "session_name": "archived_normal",
            "source_path": "runtime://imported",
            "total_frames": 32,
            "ready_frames": 32,
            "warmup_frames": 0,
            "ready_ratio": 1.0,
            "start_timestamp": 0.0,
            "end_timestamp": 1.2,
            "duration_seconds": 1.2,
            "peak_risk": {
                "timestamp": 0.5,
                "predicted_state": "normal",
                "risk_score": 0.12,
                "confidence": 0.88,
            },
            "mean_risk_score": 0.08,
            "mean_confidence": 0.86,
            "dominant_state": "normal",
            "predicted_state_counts": {"normal": 32},
            "incident_total": 0,
            "incident_counts": {},
            "first_incident": None,
            "last_incident": None,
            "recent_incidents": [],
            "top_risk_moments": [],
            "state_segments": [],
            "longest_segments": [],
        }
    )

    fall_only_archives = client.get("/archives?dominant_state=fall&incidents_only=true")
    assert fall_only_archives.status_code == 200
    assert fall_only_archives.json()["count"] == 1
    assert fall_only_archives.json()["items"][0]["session_id"] == session_id

    archive_summary = client.get("/archives/summary")
    assert archive_summary.status_code == 200
    assert archive_summary.json()["archive_total"] == 2
    assert archive_summary.json()["sessions_with_incidents"] == 1
    assert archive_summary.json()["dominant_state_counts"]["fall"] == 1
    assert archive_summary.json()["dominant_state_counts"]["normal"] == 1

    archive_report = client.get(f"/archives/{session_id}")
    assert archive_report.status_code == 200
    assert archive_report.json()["session_id"] == session_id
    assert archive_report.json()["incident_counts"]["confirmed_fall"] == 1

    archive_markdown = client.get(f"/archives/{session_id}/markdown")
    assert archive_markdown.status_code == 200
    assert "# 会话报告" in archive_markdown.text
    assert "confirmed_fall" in archive_markdown.text
    assert (archive_root / "runtime_sessions.sqlite3").exists()
