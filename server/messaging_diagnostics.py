#!/usr/bin/env python3
"""Read-only diagnostics for the WW.CX messaging gateway.

This module classifies sanitized observations. It cannot restart services,
change configuration, alter routing, or send messages.
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
        observations.append({"severity": "info", "code": "listener_reachable", "message": "Gateway listener is reachable."})
    else:
        observations.append({"severity": "warning", "code": "listener_unreachable", "message": "Gateway listener is not reachable."})

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
        "disabled_actions": ["send_sms", "send_mms", "restart_gateway", "modify_routing", "carrier_test"],
        "production_actions_enabled": False,
    }
