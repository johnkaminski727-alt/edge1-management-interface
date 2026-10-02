#!/usr/bin/env python3
"""Hardware-free broker policy for AVA physical presentation effects.

This module deliberately contains no hardware or command-execution
primitive. It validates a bounded broker request and applies deduplication
and rate limiting before any future hardware boundary.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
import time

try:
    from ava_physical_effects_state import (
        DurableReservationLedger,
        PhysicalEffectsStateError,
    )
except ImportError:
    from server.ava_physical_effects_state import (
        DurableReservationLedger,
        PhysicalEffectsStateError,
    )


ALLOWED_CATALOGUE_EFFECTS = frozenset({
    "blue_tit_chirp",
    "donkey_braying",
    "cat_meow",
    "moist_owlette_hoot",
})

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_MAX_EVENTS_PER_WINDOW = 4
DEFAULT_DEDUPE_SECONDS = 300.0


class BrokerPolicyError(ValueError):
    """Raised when an incoming broker request is malformed or unauthorized."""


@dataclass(frozen=True)
class BrokerDecision:
    request_id: str
    catalogue_effect: str
    disposition: str

    def public(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "catalogue_effect": self.catalogue_effect,
            "disposition": self.disposition,
        }


class BrokerPolicy:
    """In-memory fail-closed dedupe and rate-limit policy."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_events_per_window: int = DEFAULT_MAX_EVENTS_PER_WINDOW,
        dedupe_seconds: float = DEFAULT_DEDUPE_SECONDS,
        clock=time.monotonic,
        durable_ledger: DurableReservationLedger | None = None,
    ) -> None:
        if type(enabled) is not bool:
            raise BrokerPolicyError("enabled must be boolean")
        if window_seconds <= 0:
            raise BrokerPolicyError("window_seconds must be positive")
        if max_events_per_window <= 0:
            raise BrokerPolicyError("max_events_per_window must be positive")
        if dedupe_seconds <= 0:
            raise BrokerPolicyError("dedupe_seconds must be positive")

        self.enabled = enabled
        self.window_seconds = float(window_seconds)
        self.max_events_per_window = int(max_events_per_window)
        self.dedupe_seconds = float(dedupe_seconds)
        self._clock = clock
        self._durable_ledger = durable_ledger
        self._seen: dict[str, float] = {}
        self._events: deque[float] = deque()

    @staticmethod
    def validate_request(request_id: str, catalogue_effect: str) -> None:
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            raise BrokerPolicyError("invalid request_id")

        if (
            not isinstance(catalogue_effect, str)
            or catalogue_effect not in ALLOWED_CATALOGUE_EFFECTS
        ):
            raise BrokerPolicyError("catalogue effect is not approved")

    def _expire(self, now: float) -> None:
        dedupe_cutoff = now - self.dedupe_seconds
        stale = [
            request_id
            for request_id, timestamp in self._seen.items()
            if timestamp <= dedupe_cutoff
        ]
        for request_id in stale:
            del self._seen[request_id]

        rate_cutoff = now - self.window_seconds
        while self._events and self._events[0] <= rate_cutoff:
            self._events.popleft()

    def decide(
        self,
        request_id: str,
        catalogue_effect: str,
    ) -> BrokerDecision:
        self.validate_request(request_id, catalogue_effect)

        now = float(self._clock())
        self._expire(now)

        if request_id in self._seen:
            return BrokerDecision(
                request_id=request_id,
                catalogue_effect=catalogue_effect,
                disposition="duplicate",
            )

        if self.enabled is not True:
            return BrokerDecision(
                request_id=request_id,
                catalogue_effect=catalogue_effect,
                disposition="disabled",
            )

        if self._durable_ledger is not None:
            try:
                existing = self._durable_ledger.lookup(request_id)
            except PhysicalEffectsStateError as exc:
                raise BrokerPolicyError(
                    "durable reservation state unavailable"
                ) from exc

            if existing is not None:
                if existing["catalogue_effect"] != catalogue_effect:
                    raise BrokerPolicyError(
                        "request_id effect mismatch"
                    )

                return BrokerDecision(
                    request_id=request_id,
                    catalogue_effect=catalogue_effect,
                    disposition="duplicate",
                )

        if len(self._events) >= self.max_events_per_window:
            return BrokerDecision(
                request_id=request_id,
                catalogue_effect=catalogue_effect,
                disposition="rate_limited",
            )

        if self._durable_ledger is not None:
            try:
                reserved = self._durable_ledger.reserve(
                    request_id,
                    catalogue_effect,
                )
            except PhysicalEffectsStateError as exc:
                raise BrokerPolicyError(
                    "durable reservation failed"
                ) from exc

            if reserved is not True:
                existing = self._durable_ledger.lookup(request_id)

                if (
                    existing is not None
                    and existing["catalogue_effect"] != catalogue_effect
                ):
                    raise BrokerPolicyError(
                        "request_id effect mismatch"
                    )

                return BrokerDecision(
                    request_id=request_id,
                    catalogue_effect=catalogue_effect,
                    disposition="duplicate",
                )

        self._seen[request_id] = now
        self._events.append(now)

        return BrokerDecision(
            request_id=request_id,
            catalogue_effect=catalogue_effect,
            disposition="approved",
        )
