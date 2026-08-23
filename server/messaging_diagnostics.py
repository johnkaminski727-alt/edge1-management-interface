#!/usr/bin/env python3
"""Read-only diagnostics for the WW.CX messaging gateway.

This module classifies sanitized observations. It cannot restart services,
change configuration, alter routing, release quarantine, or send messages.
"""

from __future__ import annotations

from typing import Any


def build_diagnostics(snapshot: dict[str, Any]) -> dict[str, Any]:
    observations: list[dict[str, str]] = []

    if snapshot.get("service_active"):
        observations.append({"severity": "info", "code": "service_active", "message": "Gateway service is active."})
    else:
        observations.append({"severity": "critical", "code": "service_inactive", "message": "Gateway service is not active."})

    if snapshot.get("listener_reachable"):
        observations.append({"severity": "info", "code": "listener_reachable", "message": "Gateway health and readiness endpoints are reachable."})
    else:
        observations.append({"severity": "warning", "code": "listener_unreachable", "message": "Gateway health/readiness endpoints are not both reachable."})

    storage = snapshot.get("storage_backend", "unknown")
    observations.append({
        "severity": "info" if storage != "unknown" else "warning",
        "code": "storage_backend",
        "message": f"Gateway readiness reports storage backend: {storage}.",
    })

    quarantine_present = bool(snapshot.get("mms_quarantine_root_present"))
    quarantine_secure = bool(snapshot.get("mms_quarantine_root_secure"))
    if quarantine_present and quarantine_secure:
        observations.append({"severity": "info", "code": "mms_quarantine_secure", "message": "Private MMS quarantine root is present with strict owner-only directory mode."})
    elif quarantine_present:
        observations.append({"severity": "critical", "code": "mms_quarantine_permissions", "message": "Private MMS quarantine root is present but its directory mode is not the required 0700."})
    else:
        observations.append({"severity": "warning", "code": "mms_quarantine_unverified", "message": "Private MMS quarantine root is absent or not observable from the current read-only operations identity."})

    if snapshot.get("trusted_scanner_available"):
        version = str(snapshot.get("trusted_scanner_version", "available"))[:128]
        observations.append({"severity": "info", "code": "mms_scanner_available", "message": f"Fixed local ClamAV scanner probe succeeded: {version}."})
    else:
        observations.append({"severity": "warning", "code": "mms_scanner_unavailable", "message": "The fixed local /usr/bin/clamscan runtime is unavailable to the current operations probe."})

    if snapshot.get("mms_security_ready"):
        observations.append({"severity": "info", "code": "mms_security_ready", "message": "MMS quarantine and scanner posture are both observable and security-ready."})
    else:
        observations.append({"severity": "warning", "code": "mms_security_unverified", "message": "MMS security readiness is not freshly proven by this read-only snapshot; carrier media must remain held/fail-closed."})

    queue_depth = snapshot.get("queue_depth")
    if queue_depth is None:
        observations.append({"severity": "info", "code": "queue_unknown", "message": "Queue depth is not available from the current read-only probe."})
    elif queue_depth > 0:
        observations.append({"severity": "warning", "code": "queue_pending", "message": f"Queue contains {queue_depth} pending item(s)."})
    else:
        observations.append({"severity": "info", "code": "queue_empty", "message": "Queue is empty."})

    return {
        "gateway": snapshot.get("gateway", "wwcx-messaging-gateway"),
        "state": snapshot.get("state", "unknown"),
        "checked_at": snapshot.get("checked_at", ""),
        "observations": observations,
        "allowed_actions": ["inspect", "record_evidence", "simulate_sandbox"],
        "disabled_actions": ["send_sms", "send_mms", "restart_gateway", "modify_routing", "carrier_test", "release_quarantine"],
        "production_actions_enabled": False,
    }
