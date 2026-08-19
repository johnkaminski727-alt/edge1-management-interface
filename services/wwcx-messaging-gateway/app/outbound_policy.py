from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import psycopg

from .models import NormalizedMessage


@dataclass(frozen=True)
class OutboundPolicy:
    enabled: bool
    authorized_senders: frozenset[str]
    destination_prefixes: tuple[str, ...]
    max_recipients: int = 1
    max_text_chars: int = 1600
    hourly_message_limit: int = 10
    daily_message_limit: int = 25

    @classmethod
    def from_values(
        cls,
        *,
        enabled: bool,
        authorized_senders: str | None,
        destination_prefixes: str | None,
        max_recipients: int = 1,
        max_text_chars: int = 1600,
        hourly_message_limit: int = 10,
        daily_message_limit: int = 25,
    ) -> "OutboundPolicy":
        return cls(
            enabled=bool(enabled),
            authorized_senders=frozenset(
                item.strip() for item in (authorized_senders or "").split(",") if item.strip()
            ),
            destination_prefixes=tuple(
                item.strip() for item in (destination_prefixes or "").split(",") if item.strip()
            ),
            max_recipients=max(1, min(int(max_recipients), 32)),
            max_text_chars=max(1, min(int(max_text_chars), 10000)),
            hourly_message_limit=max(1, min(int(hourly_message_limit), 100000)),
            daily_message_limit=max(1, min(int(daily_message_limit), 1000000)),
        )

    def evaluate(self, message: NormalizedMessage) -> str | None:
        if not self.enabled:
            return "outbound_policy_disabled"
        if not self.authorized_senders:
            return "authorized_sender_allowlist_empty"
        if message.sender not in self.authorized_senders:
            return "sender_not_authorized"
        if not self.destination_prefixes:
            return "destination_allowlist_empty"
        if len(message.recipients) > self.max_recipients:
            return "recipient_limit_exceeded"
        if len(message.text) > self.max_text_chars:
            return "message_size_limit_exceeded"
        if any(
            not any(recipient.startswith(prefix) for prefix in self.destination_prefixes)
            for recipient in message.recipients
        ):
            return "destination_not_authorized"
        return None


class SendRateLimiter(Protocol):
    def reserve(
        self,
        job_id: UUID,
        message: NormalizedMessage,
        *,
        hourly_limit: int,
        daily_limit: int,
    ) -> str | None: ...


class PostgresSendRateLimiter:
    """Durably reserve bounded send capacity before provider submission.

    Reservations are intentionally not refunded automatically after provider errors.
    Consuming quota on an uncertain outcome is fail-closed and prevents a retry storm.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def reserve(
        self,
        job_id: UUID,
        message: NormalizedMessage,
        *,
        hourly_limit: int,
        daily_limit: int,
    ) -> str | None:
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                    (message.provider, message.sender),
                )
                existing = connection.execute(
                    """
                    SELECT 1
                    FROM messaging_outbound_send_reservations
                    WHERE job_id = %s
                    """,
                    (job_id,),
                ).fetchone()
                if existing is not None:
                    return None

                hourly_count, daily_count = connection.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE reserved_at >= now() - interval '1 hour'),
                        count(*) FILTER (WHERE reserved_at >= now() - interval '1 day')
                    FROM messaging_outbound_send_reservations
                    WHERE provider = %s AND sender = %s
                    """,
                    (message.provider, message.sender),
                ).fetchone()
                if int(hourly_count) >= hourly_limit:
                    return "hourly_message_limit_exceeded"
                if int(daily_count) >= daily_limit:
                    return "daily_message_limit_exceeded"

                connection.execute(
                    """
                    INSERT INTO messaging_outbound_send_reservations
                        (job_id, message_id, provider, sender, recipient_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        job_id,
                        message.event_id,
                        message.provider,
                        message.sender,
                        len(message.recipients),
                    ),
                )
        return None
