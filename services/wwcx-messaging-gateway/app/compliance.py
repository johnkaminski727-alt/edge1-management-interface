from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_WORDS = {"START", "UNSTOP", "YES"}
HELP_WORDS = {"HELP", "INFO"}


@dataclass
class SuppressionRegistry:
    """Development registry; production storage belongs in PostgreSQL."""

    suppressed: dict[str, datetime] = field(default_factory=dict)

    def classify(self, text: str) -> str | None:
        keyword = text.strip().upper()
        if keyword in STOP_WORDS:
            return "stop"
        if keyword in START_WORDS:
            return "start"
        if keyword in HELP_WORDS:
            return "help"
        return None

    def apply(self, address: str, text: str) -> str | None:
        action = self.classify(text)
        if action == "stop":
            self.suppressed[address] = datetime.now(timezone.utc)
        elif action == "start":
            self.suppressed.pop(address, None)
        return action

    def may_send(self, address: str) -> bool:
        return address not in self.suppressed
