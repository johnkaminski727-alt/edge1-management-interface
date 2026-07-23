#!/usr/bin/env python3
"""WW.CX Messaging Operations health models.

Read-only observation models only. No production messaging actions are
implemented by this module.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict


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


def health_snapshot(
    *,
    service_active: bool,
    listener_reachable: bool,
) -> MessagingHealthSnapshot:
    state = "healthy" if service_active and listener_reachable else "degraded"
    return MessagingHealthSnapshot(
        gateway="wwcx-messaging-gateway",
        service_active=service_active,
        listener_reachable=listener_reachable,
        state=state,
        production_actions_enabled=False,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def degraded_snapshot() -> MessagingHealthSnapshot:
    """Compatibility helper for an explicitly degraded observation."""
    return health_snapshot(service_active=True, listener_reachable=False)
