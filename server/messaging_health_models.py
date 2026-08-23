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
    storage_backend: str
    mms_security_ready: bool
    mms_quarantine_root_present: bool
    mms_quarantine_root_secure: bool
    trusted_scanner_available: bool
    trusted_scanner_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def health_snapshot(
    *,
    service_active: bool,
    listener_reachable: bool,
    storage_backend: str = "unknown",
    mms_quarantine_root_present: bool = False,
    mms_quarantine_root_secure: bool = False,
    trusted_scanner_available: bool = False,
    trusted_scanner_version: str = "unknown",
) -> MessagingHealthSnapshot:
    mms_security_ready = (
        mms_quarantine_root_present
        and mms_quarantine_root_secure
        and trusted_scanner_available
    )
    state = "healthy" if service_active and listener_reachable else "degraded"
    return MessagingHealthSnapshot(
        gateway="wwcx-messaging-gateway",
        service_active=service_active,
        listener_reachable=listener_reachable,
        state=state,
        production_actions_enabled=False,
        checked_at=datetime.now(timezone.utc).isoformat(),
        storage_backend=storage_backend,
        mms_security_ready=mms_security_ready,
        mms_quarantine_root_present=mms_quarantine_root_present,
        mms_quarantine_root_secure=mms_quarantine_root_secure,
        trusted_scanner_available=trusted_scanner_available,
        trusted_scanner_version=trusted_scanner_version,
    )


def degraded_snapshot() -> MessagingHealthSnapshot:
    """Compatibility helper for an explicitly degraded observation."""
    return health_snapshot(service_active=True, listener_reachable=False)
