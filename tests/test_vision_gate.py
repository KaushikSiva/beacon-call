from beacon_call.vision_gate import PresenceGate


def test_requires_three_confirmations() -> None:
    gate = PresenceGate(required_hits=3, threshold=0.66)
    assert gate.observe(person_present=True, confidence=0.80, now=1.0) is False
    assert gate.observe(person_present=True, confidence=0.82, now=1.4) is False
    assert gate.observe(person_present=True, confidence=0.84, now=1.8) is True


def test_low_confidence_resets_streak() -> None:
    gate = PresenceGate(required_hits=2, threshold=0.66)
    gate.observe(person_present=True, confidence=0.90, now=1.0)
    assert gate.observe(person_present=True, confidence=0.40, now=1.2) is False
    assert gate.streak == 0


def test_cooldown_prevents_duplicate_incident() -> None:
    gate = PresenceGate(required_hits=2, threshold=0.66, cooldown_seconds=20)
    gate.observe(person_present=True, confidence=0.90, now=1.0)
    assert gate.observe(person_present=True, confidence=0.90, now=1.2) is True
    assert gate.observe(person_present=True, confidence=0.90, now=2.0) is False
    assert gate.observe(person_present=True, confidence=0.90, now=2.2) is False
