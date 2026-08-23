#!/usr/bin/env python3
"""Validate Operator Controls v1 live with all host-write gates still disabled."""
from __future__ import annotations

import json
import os
import stat
import urllib.request
from pathlib import Path

MCP_URL = "http://127.0.0.1:8102/mcp"
TOKEN_PATH = Path("/etc/edge1-operator/mcp-token")
BROKER_AUDIT = Path("/var/lib/edge1-operator-privileged/audit.jsonl")


def _token() -> str:
    st = TOKEN_PATH.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise RuntimeError("operator token permissions are unsafe")
    value = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if len(value) < 32 or any(ch.isspace() for ch in value):
        raise RuntimeError("operator token is invalid")
    return value


def _rpc(method: str, params: dict, request_id: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        MCP_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or "result" not in payload:
        raise RuntimeError(f"MCP {method} failed")
    return payload["result"]


def _tool(name: str, arguments: dict, request_id: int) -> dict:
    result = _rpc("tools/call", {"name": name, "arguments": arguments}, request_id)
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise RuntimeError(f"tool {name} returned no structuredContent")
    return structured


def _authorized_attempt_count() -> int:
    if not BROKER_AUDIT.exists():
        return 0
    count = 0
    with BROKER_AUDIT.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if value.get("status") == "authorized_attempt":
                count += 1
    return count


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("run as root so the protected local MCP token can be read")

    listed = _rpc("tools/list", {}, 1)
    tools = listed.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError("tools/list did not return tools")
    names = {item.get("name") for item in tools if isinstance(item, dict)}
    required = {
        "edge1.capabilities",
        "edge1.telephony_console_control_status",
        "edge1.telephony_console_reload",
    }
    if not required.issubset(names):
        raise RuntimeError(f"new Operator controls are missing: {sorted(required - names)}")
    if "agent.turn.handoff" in names or "agent.turn.status" in names or "edge1.exec" in names:
        raise RuntimeError("internal or generic execution tool leaked into public surface")

    capabilities = _tool("edge1.capabilities", {}, 2)
    if capabilities.get("status") != "ok":
        raise RuntimeError("edge1.capabilities failed")
    summary = capabilities.get("payload")
    if not isinstance(summary, dict):
        raise RuntimeError("capability summary is invalid")
    telephony_control = next(
        (item for item in summary.get("capabilities", []) if item.get("capability") == "edge1.telephony.control.safe"),
        None,
    )
    if not isinstance(telephony_control, dict):
        raise RuntimeError("telephony safe-control capability is absent")
    if telephony_control.get("scope_present") is not False:
        raise RuntimeError("telephony safe-control scope is unexpectedly active")

    status = _tool("edge1.telephony_console_control_status", {}, 3)
    if status.get("status") != "ok":
        raise RuntimeError("telephony control status failed")
    payload = status.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("telephony control status payload is invalid")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1:
        raise RuntimeError("telephony control status result count is invalid")
    action = results[0]
    if action.get("status") != "succeeded" or action.get("action") != "telephony.console.control_status":
        raise RuntimeError("telephony control status Operations API action failed")
    observed = json.loads(action.get("stdout", "{}"))
    if observed.get("active") is not True or observed.get("loopback_health") is not True:
        raise RuntimeError("telephony console is not healthy")
    if observed.get("source_matches_head") is not True or not isinstance(observed.get("pid"), int) or observed["pid"] <= 0:
        raise RuntimeError("telephony control preconditions are not trustworthy")

    before = _authorized_attempt_count()
    denied = _tool(
        "edge1.telephony_console_reload",
        {
            "expected_pid": observed["pid"],
            "expected_source_sha256": observed["source_sha256"],
            "expected_repo_head": observed["repo_head"],
            "idempotency_key": "disabled-commissioning-denial-0001",
        },
        4,
    )
    after = _authorized_attempt_count()
    if denied.get("status") != "error" or denied.get("payload") != {"message": "capability_denied"}:
        raise RuntimeError(f"write tool was not denied by Operator scope: {denied!r}")
    if after != before:
        raise RuntimeError("denied MCP write reached the privileged broker")

    print(json.dumps({
        "contract": "wwcx.edge1-operator-controls-disabled-acceptance.v1",
        "status": "accepted",
        "public_tools": len(names),
        "telephony_control_scope_present": False,
        "write_tool_denied": True,
        "privileged_broker_not_reached_by_denied_write": True,
        "telephony_console_healthy": True,
        "source_matches_head": True,
        "secrets_output": False,
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
