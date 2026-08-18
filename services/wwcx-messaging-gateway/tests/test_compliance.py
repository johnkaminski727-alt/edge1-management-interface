from datetime import datetime, timezone

from app.compliance import (
    SuppressionRegistry,
    classify_compliance_keyword,
    normalize_compliance_keyword,
)


def test_stop_suppresses_and_start_restores() -> None:
    registry = SuppressionRegistry()

    assert registry.apply("+16045550101", " stop ") == "stop"
    assert registry.may_send("+16045550101") is False

    assert registry.apply("+16045550101", "START") == "start"
    assert registry.may_send("+16045550101") is True


def test_help_does_not_change_suppression() -> None:
    registry = SuppressionRegistry()

    assert registry.apply("+16045550102", "help") == "help"
    assert registry.may_send("+16045550102") is True


def test_normal_message_is_not_a_command() -> None:
    registry = SuppressionRegistry()

    assert registry.apply("+16045550103", "Please stop by tomorrow") is None
    assert registry.may_send("+16045550103") is True


def test_keyword_sets_preserve_existing_contract() -> None:
    assert classify_compliance_keyword(" unsubscribe ") == "stop"
    assert classify_compliance_keyword("yes") == "start"
    assert classify_compliance_keyword("info") == "help"
    assert normalize_compliance_keyword("  stopall  ") == "STOPALL"


def test_stale_keyword_does_not_override_newer_state() -> None:
    registry = SuppressionRegistry()
    newer = datetime(2026, 8, 18, 23, 1, tzinfo=timezone.utc)
    older = datetime(2026, 8, 18, 23, 0, tzinfo=timezone.utc)

    assert registry.apply(
        "+16045550104",
        "START",
        occurred_at=newer,
        message_id="bbbb",
    ) == "start"
    assert registry.apply(
        "+16045550104",
        "STOP",
        occurred_at=older,
        message_id="aaaa",
    ) == "stop"

    assert registry.may_send("+16045550104") is True
    status = registry.status()
    assert status["stale_event_count"] == 1
    assert status["recent_events"][0]["applied"] is False
