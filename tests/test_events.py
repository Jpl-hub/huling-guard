from huling_guard.events import EventEngine, EventThresholds, Incident


def test_event_engine_emits_fall_and_long_lie() -> None:
    engine = EventEngine(
        EventThresholds(
            near_fall_threshold=0.5,
            fall_threshold=0.7,
            prolonged_lying_threshold=0.6,
            prolonged_lying_seconds=5,
            warning_cooldown_seconds=2,
            fall_confirm_hits=2,
        )
    )

    near = engine.update(
        1.0,
        {
            "normal": 0.1,
            "near_fall": 0.8,
            "fall": 0.0,
            "recovery": 0.0,
            "prolonged_lying": 0.1,
        },
    )
    fall1 = engine.update(
        2.0,
        {
            "normal": 0.0,
            "near_fall": 0.1,
            "fall": 0.75,
            "recovery": 0.0,
            "prolonged_lying": 0.15,
        },
    )
    fall2 = engine.update(
        3.0,
        {
            "normal": 0.0,
            "near_fall": 0.1,
            "fall": 0.85,
            "recovery": 0.0,
            "prolonged_lying": 0.2,
        },
    )
    long_lie = engine.update(
        8.5,
        {
            "normal": 0.0,
            "near_fall": 0.0,
            "fall": 0.1,
            "recovery": 0.0,
            "prolonged_lying": 0.9,
        },
    )

    assert near[0].kind == "near_fall_warning"
    assert fall1 == []
    assert fall2[0].kind == "confirmed_fall"
    assert long_lie[0].kind == "prolonged_lying"


def test_incident_to_dict_preserves_payload() -> None:
    incident = Incident(
        kind="confirmed_fall",
        timestamp=12.5,
        confidence=0.91,
        payload={"state_probs": {"fall": 0.91}},
    )

    assert incident.to_dict() == {
        "kind": "confirmed_fall",
        "timestamp": 12.5,
        "confidence": 0.91,
        "payload": {"state_probs": {"fall": 0.91}},
    }
