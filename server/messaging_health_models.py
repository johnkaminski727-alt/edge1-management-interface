#!/usr/bin/env python3
"""
WW.CX Messaging Operations health models.

Read-only observation models only.
No production messaging actions are implemented.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any


@dataclass
class MessagingHealthSnapshot:
    gateway: str
    service_active: bool
    listener_reachable: bool
    state: str
    production_actions_enabled: bool
    checked_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def degraded_snapshot() -> MessagingHealthSnapshot:
    return MessagingHealthSnapshot(
        gateway="wwcx-messaging-gateway",
        service_active=True,
        listener_reachable=False,
        state="degraded",
        production_actions_enabled=False,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
