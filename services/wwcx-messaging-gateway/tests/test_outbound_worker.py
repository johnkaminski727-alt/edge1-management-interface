from uuid import UUID

from app.models import Channel, Direction, NormalizedMessage
from app.outbound_policy import OutboundPolicy
from app.outbound_worker import parse_provider_allowlist, run_once
from app.persistence import ClaimedOutboundJob
from app.providers import SendResult


JOB_ID = UUID("22222222-2222-2222-2222-222222222222")
EVENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def outbound_message(*, provider: str = "simulator", channel: Channel = Channel.SMS) -> NormalizedMessage:
    return NormalizedMessage(
        event_id=EVENT_ID,
        provider=provider,
        provider_event_id="unit-outbound-1",
        direction=Direction.OUTBOUND,
        channel=channel,
        **{"from": "+16045550101", "to": ["+16045550102"]},
        text="queued test message",
    )


def authorized_policy(**overrides: object) -> OutboundPolicy:
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


class FakeRateLimiter:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason
        self.calls = 0

    def reserve(
        self,
        job_id: UUID,
        message: NormalizedMessage,
        *,
        hourly_limit: int,
        daily_limit: int,
    ) -> str | None:
        self.calls += 1
        return self.reason


class FakeStore:
    def __init__(self, message: NormalizedMessage, *, paused: bool = False, suppressed: list[str] | None = None) -> None:
        self.job = ClaimedOutboundJob(JOB_ID, message, 1)
        self.paused = paused
        self.suppressed = suppressed or []
        self.completed: tuple[UUID, str] | None = None
        self.blocked: tuple[UUID, str, str] | None = None
        self.retried: tuple[UUID, str, int, int] | None = None

    def get_control_state(self) -> dict[str, object]:
        return {"paused": self.paused}

    def claim_outbound_job(self) -> ClaimedOutboundJob | None:
        return self.job

    def suppressed_recipients(self, recipients: list[str]) -> list[str]:
        return self.suppressed

    def complete_outbound_job(self, job_id: UUID, provider_message_id: str) -> None:
        self.completed = (job_id, provider_message_id)

    def block_outbound_job(self, job_id: UUID, reason: str, status: str = "blocked") -> None:
        self.blocked = (job_id, reason, status)

    def retry_outbound_job(
        self,
        job_id: UUID,
        error: str,
        *,
        delay_seconds: int = 60,
        max_attempts: int = 5,
    ) -> str:
        self.retried = (job_id, error, delay_seconds, max_attempts)
        return "pending"


class FakeProvider:
    def __init__(self, *, accepted: bool = True, raises: bool = False) -> None:
        self.accepted = accepted
        self.raises = raises
        self.calls = 0

    def send(self, message: NormalizedMessage) -> SendResult:
        self.calls += 1
        if self.raises:
            raise RuntimeError("provider unavailable")
        return SendResult(provider_message_id=f"fake-{message.event_id}", accepted=self.accepted)


def run(
    store: FakeStore,
    providers: dict[str, FakeProvider],
    allowed_providers: set[str],
    *,
    policy: OutboundPolicy | None = None,
    limiter: FakeRateLimiter | None = None,
    retry_delay_seconds: int = 60,
    max_attempts: int = 5,
) -> dict[str, object]:
    return run_once(
        store,
        providers,
        allowed_providers,
        policy or authorized_policy(),
        limiter or FakeRateLimiter(),
        retry_delay_seconds=retry_delay_seconds,
        max_attempts=max_attempts,
    )


def test_parse_provider_allowlist_defaults_to_simulator() -> None:
    assert parse_provider_allowlist(None) == {"simulator"}
    assert parse_provider_allowlist(" simulator, telnyx ,, ") == {"simulator", "telnyx"}


def test_run_once_sends_allowlisted_authorized_simulator_job() -> None:
    store = FakeStore(outbound_message())
    provider = FakeProvider()
    limiter = FakeRateLimiter()
    result = run(store, {"simulator": provider}, {"simulator"}, limiter=limiter)
    assert result["status"] == "sent"
    assert provider.calls == 1
    assert limiter.calls == 1
    assert store.completed == (JOB_ID, f"fake-{EVENT_ID}")


def test_run_once_respects_pause_before_claiming_send() -> None:
    store = FakeStore(outbound_message(), paused=True)
    provider = FakeProvider()
    result = run(store, {"simulator": provider}, {"simulator"})
    assert result == {"status": "paused"}
    assert provider.calls == 0


def test_run_once_blocks_provider_outside_allowlist() -> None:
    store = FakeStore(outbound_message(provider="telnyx"))
    provider = FakeProvider()
    result = run(store, {"telnyx": provider}, {"simulator"})
    assert result["reason"] == "provider_not_allowlisted"
    assert provider.calls == 0


def test_run_once_blocks_when_authorization_policy_disabled() -> None:
    store = FakeStore(outbound_message())
    provider = FakeProvider()
    result = run(
        store,
        {"simulator": provider},
        {"simulator"},
        policy=authorized_policy(enabled=False),
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "outbound_policy_disabled"
    assert provider.calls == 0


def test_run_once_blocks_unauthorized_destination() -> None:
    message = outbound_message()
    message.recipients = ["+442071234567"]
    store = FakeStore(message)
    provider = FakeProvider()
    result = run(store, {"simulator": provider}, {"simulator"})
    assert result["reason"] == "destination_not_authorized"
    assert provider.calls == 0


def test_run_once_blocks_suppressed_recipient_before_rate_reservation() -> None:
    store = FakeStore(outbound_message(), suppressed=["+16045550102"])
    provider = FakeProvider()
    limiter = FakeRateLimiter()
    result = run(store, {"simulator": provider}, {"simulator"}, limiter=limiter)
    assert result["status"] == "suppressed"
    assert provider.calls == 0
    assert limiter.calls == 0


def test_run_once_quarantines_mms_media_before_rate_reservation() -> None:
    message = outbound_message(channel=Channel.MMS)
    message.media = [{"url": "https://example.invalid/media.jpg", "content_type": "image/jpeg"}]
    store = FakeStore(message)
    provider = FakeProvider()
    limiter = FakeRateLimiter()
    result = run(store, {"simulator": provider}, {"simulator"}, limiter=limiter)
    assert result["status"] == "quarantined"
    assert provider.calls == 0
    assert limiter.calls == 0


def test_run_once_blocks_rate_limited_message() -> None:
    store = FakeStore(outbound_message())
    provider = FakeProvider()
    limiter = FakeRateLimiter("hourly_message_limit_exceeded")
    result = run(store, {"simulator": provider}, {"simulator"}, limiter=limiter)
    assert result["status"] == "rate_limited"
    assert result["reason"] == "hourly_message_limit_exceeded"
    assert provider.calls == 0


def test_run_once_requeues_provider_exception_after_reservation() -> None:
    store = FakeStore(outbound_message())
    provider = FakeProvider(raises=True)
    limiter = FakeRateLimiter()
    result = run(
        store,
        {"simulator": provider},
        {"simulator"},
        limiter=limiter,
        retry_delay_seconds=17,
        max_attempts=3,
    )
    assert result["status"] == "pending"
    assert result["reason"] == "provider_error"
    assert limiter.calls == 1
    assert store.retried is not None
    assert store.retried[2:] == (17, 3)
