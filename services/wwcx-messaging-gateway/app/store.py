from threading import Lock

from .models import NormalizedMessage


class InMemoryEventStore:
    """Development-only idempotency, ledger, and control store."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[tuple[str, str], NormalizedMessage] = {}
        self._paused = False
        self._last_control: dict[str, str] | None = None

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

    def list_recent(self, limit: int = 50) -> list[NormalizedMessage]:
        with self._lock:
            events = list(self._events.values())
        events.sort(key=lambda item: item.occurred_at, reverse=True)
        return events[:limit]

    def get_event(self, event_id: str) -> NormalizedMessage | None:
        with self._lock:
            for message in self._events.values():
                if str(message.event_id) == event_id:
                    return message
        return None

    def get_control_state(self) -> dict[str, object]:
        with self._lock:
            return {
                "paused": self._paused,
                "last_control": self._last_control,
            }

    def set_paused(self, paused: bool, actor: str, reason: str) -> dict[str, object]:
        with self._lock:
            self._paused = paused
            self._last_control = {
                "action": "pause" if paused else "resume",
                "actor": actor,
                "reason": reason,
            }
            return {
                "paused": self._paused,
                "last_control": self._last_control,
            }
