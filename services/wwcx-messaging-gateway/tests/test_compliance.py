from app.compliance import SuppressionRegistry


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
