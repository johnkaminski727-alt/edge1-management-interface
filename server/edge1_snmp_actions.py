#!/usr/bin/env python3
"""Deterministic executor for approved Edge1 SNMP remediation proposals.

Only fixed, allowlisted application actions are implemented here. The executor
never accepts arbitrary commands, executable paths, SQL, or shell fragments from
AI output or API callers.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any, Callable

from edge1_snmp_platform import AUTO_ALLOWED, audit, get_device, poll_device, utcnow
from edge1_snmp_services import discover_interfaces, sync_interfaces

_ALLOWED_SERVICE_TARGET = "edge1-snmp-api.service"


def _proposal(conn, proposal_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM action_proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
    if not row:
        raise KeyError(proposal_id)
    proposal = dict(row)
    proposal["validation"] = json.loads(proposal.pop("validation_json") or "{}")
    proposal["rollback"] = json.loads(proposal.pop("rollback_json") or "{}")
    proposal["result"] = json.loads(proposal.pop("result_json") or "{}")
    return proposal


def _record_result(conn, proposal: dict[str, Any], *, state: str, result: dict[str, Any], before: Any, after: Any) -> dict[str, Any]:
    conn.execute(
        "UPDATE action_proposals SET state=?,result_json=? WHERE proposal_id=?",
        (state, json.dumps(result, sort_keys=True), proposal["proposal_id"]),
    )
    conn.commit()
    audit(
        conn,
        actor=proposal["actor"],
        source="policy-engine",
        action=f"action.execute.{proposal['action']}",
        target=proposal.get("target"),
        reason=proposal["reason"],
        result=state,
        before=before,
        after=after,
        ai_involvement="execution" if proposal["actor"].lower().startswith("ai") else "none",
        rollback=proposal["rollback"],
    )
    return {"proposal_id": proposal["proposal_id"], "state": state, "result": result}


def execute_proposal(
    conn,
    proposal_id: str,
    *,
    net=None,
    service_runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    proposal = _proposal(conn, proposal_id)
    if proposal["state"] != "approved":
        raise PermissionError("proposal is not approved for execution")
    if proposal["action_class"] not in AUTO_ALLOWED:
        raise PermissionError("proposal action class is not automatically executable")
    if not proposal["validation"] or not proposal["rollback"]:
        raise PermissionError("proposal lacks required validation or rollback metadata")

    action = proposal["action"]
    target = proposal.get("target")
    before: Any = {}
    after: Any = {}
    result: dict[str, Any]

    try:
        if action == "repoll_device":
            if not target:
                raise ValueError("repoll_device requires a device target")
            before = get_device(conn, target)
            result = asyncio.run(poll_device(conn, before, net=net))
            after = get_device(conn, target)

        elif action == "refresh_inventory":
            if not target:
                raise ValueError("refresh_inventory requires a device target")
            device = get_device(conn, target)
            before = {"device_id": target, "interface_count": conn.execute(
                "SELECT count(*) FROM interfaces WHERE device_id=?", (target,)
            ).fetchone()[0]}
            if net is None:
                from edge1_snmp_platform import NetSNMP
                net = NetSNMP()
            rows = discover_interfaces(net, device)
            count = sync_interfaces(conn, target, rows)
            after = {"device_id": target, "interface_count": count}
            result = {"refreshed_interfaces": count}

        elif action == "disable_broken_polling":
            if not target:
                raise ValueError("disable_broken_polling requires a device target")
            device = get_device(conn, target)
            before = {"polling_enabled": bool(device["polling_enabled"])}
            conn.execute("UPDATE devices SET polling_enabled=0,updated_at=? WHERE device_id=?", (utcnow(), target))
            conn.commit()
            after = {"polling_enabled": False}
            result = {"disabled": True}

        elif action == "temporarily_adjust_polling":
            if not target:
                raise ValueError("temporarily_adjust_polling requires a device target")
            new_interval = int(proposal["validation"].get("new_interval_seconds", 0))
            if new_interval < 10 or new_interval > 86400:
                raise ValueError("new_interval_seconds must be 10..86400")
            device = get_device(conn, target)
            before = {"polling_interval": int(device["polling_interval"])}
            conn.execute("UPDATE devices SET polling_interval=?,updated_at=? WHERE device_id=?", (new_interval, utcnow(), target))
            conn.commit()
            after = {"polling_interval": new_interval}
            result = {"polling_interval": new_interval}

        elif action == "restart_snmp_service":
            if target not in {None, _ALLOWED_SERVICE_TARGET}:
                raise PermissionError("service target is not allowlisted")
            before = {"service": _ALLOWED_SERVICE_TARGET}
            completed = service_runner(
                ["/usr/bin/systemctl", "restart", _ALLOWED_SERVICE_TARGET],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            )
            if completed.returncode != 0:
                raise RuntimeError((completed.stderr or completed.stdout or "service restart failed")[-2000:])
            after = {"service": _ALLOWED_SERVICE_TARGET, "restart_requested": True}
            result = {"restarted": _ALLOWED_SERVICE_TARGET}

        else:
            raise PermissionError("approved action has no deterministic executor")

    except Exception as exc:
        failure = {"error_type": type(exc).__name__, "detail": str(exc)[:1000]}
        _record_result(conn, proposal, state="failed", result=failure, before=before, after=after)
        raise

    return _record_result(conn, proposal, state="executed", result=result, before=before, after=after)
