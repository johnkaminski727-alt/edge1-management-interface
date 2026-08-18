from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_WORDS = {"START", "UNSTOP", "YES"}
HELP_WORDS = {"HELP", "INFO"}


def normalize_compliance_keyword(text: str) -> str:
    return text.strip().upper()


def classify_compliance_keyword(text: str) -> str | None:
    keyword = normalize_compliance_keyword(text)
    if keyword in STOP_WORDS:
        return "stop"
    if keyword in START_WORDS:
        return "start"
    if keyword in HELP_WORDS:
        return "help"
    return None


@dataclass
class SuppressionRegistry:
    """Development-only keyword registry; durable production state belongs in PostgreSQL."""

    suppressed: dict[str, datetime] = field(default_factory=dict)
    effective: dict[str, tuple[datetime, str]] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)

    def classify(self, text: str) -> str | None:
        return classify_compliance_keyword(text)

    def apply(
        self,
        address: str,
        text: str,
        *,
        occurred_at: datetime | None = None,
        message_id: str = "",
    ) -> str | None:
        action = self.classify(text)
        if action is None:
            return None

        event_time = occurred_at or datetime.now(timezone.utc)
        event_key = (event_time, message_id)
        current_key = self.effective.get(address)
        applied = current_key is None or event_key > current_key

        if applied:
            self.effective[address] = event_key
            if action == "stop":
                self.suppressed[address] = event_time
            elif action == "start":
                self.suppressed.pop(address, None)

        self.events.append(
            {
                "address": address,
                "action": action,
                "keyword": normalize_compliance_keyword(text),
                "occurred_at": event_time.isoformat(),
                "message_id": message_id,
                "applied": applied,
            }
        )
        return action

    def may_send(self, address: str) -> bool:
        return address not in self.suppressed

    def status(self, limit: int = 25) -> dict[str, object]:
        bounded_limit = min(max(int(limit), 1), 100)
        action_counts = {"stop": 0, "start": 0, "help": 0}
        stale_count = 0
        for event in self.events:
            action_counts[str(event["action"])] += 1
            if not event["applied"]:
                stale_count += 1
        return {
            "durable": False,
            "suppression_count": len(self.suppressed),
            "keyword_suppression_count": len(self.suppressed),
            "consent_state_counts": {
                "suppressed": len(self.suppressed),
                "active": max(0, len(self.effective) - len(self.suppressed)),
            },
            "action_counts": action_counts,
            "stale_event_count": stale_count,
            "recent_events": list(reversed(self.events[-bounded_limit:])),
        }
