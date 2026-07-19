from threading import Lock

from .models import NormalizedMessage


class InMemoryEventStore:
    """Development-only idempotency store; replace with PostgreSQL before production."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[tuple[str, str], NormalizedMessage] = {}

    def put_if_absent(self, message: NormalizedMessage) -> bool:
        key = (message.provider, message.provider_event_id)
        with self._lock:
            if key in self._events:
                return False
            self._events[key] = message
            return True

    def count(self) -> int:
        with self._lock:
            return len(self._events)
