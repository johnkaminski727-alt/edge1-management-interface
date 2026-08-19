from app.models import Channel, Direction, NormalizedMessage
from app.outbound_policy import OutboundPolicy


def message(**overrides: object) -> NormalizedMessage:
    values: dict[str, object] = {
        "provider": "simulator",
        "provider_event_id": "policy-1",
        "direction": Direction.OUTBOUND,
        "channel": Channel.SMS,
        "from": "+16045550101",
        "to": ["+16045550102"],
        "text": "hello",
    }
    values.update(overrides)
    return NormalizedMessage.model_validate(values)


def policy(**overrides: object) -> OutboundPolicy:
    values: dict[str, object] = {
        "enabled": True,
        "authorized_senders": "+16045550101",
        "destination_prefixes": "+1",
        "max_recipients": 1,
        "max_text_chars": 1600,
        "hourly_message_limit": 10,
        "daily_message_limit": 25,
    }
    values.update(overrides)
    return OutboundPolicy.from_values(**values)


def test_policy_allows_authorized_bounded_message() -> None:
    assert policy().evaluate(message()) is None


def test_policy_fails_closed_when_disabled_or_unconfigured() -> None:
    assert policy(enabled=False).evaluate(message()) == "outbound_policy_disabled"
    assert policy(authorized_senders="").evaluate(message()) == "authorized_sender_allowlist_empty"
    assert policy(destination_prefixes="").evaluate(message()) == "destination_allowlist_empty"


def test_policy_blocks_sender_destination_recipient_and_size() -> None:
    assert policy().evaluate(message(**{"from": "+13065550101"})) == "sender_not_authorized"
    assert policy().evaluate(message(**{"to": ["+442071234567"]})) == "destination_not_authorized"
    assert policy().evaluate(message(**{"to": ["+16045550102", "+16045550103"]})) == "recipient_limit_exceeded"
    assert policy(max_text_chars=4).evaluate(message(text="hello")) == "message_size_limit_exceeded"


def test_policy_bounds_config_values() -> None:
    bounded = policy(
        max_recipients=1000,
        max_text_chars=100000,
        hourly_message_limit=1000000,
        daily_message_limit=10000000,
    )
    assert bounded.max_recipients == 32
    assert bounded.max_text_chars == 10000
    assert bounded.hourly_message_limit == 100000
    assert bounded.daily_message_limit == 1000000
