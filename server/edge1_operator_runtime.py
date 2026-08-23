#!/usr/bin/env python3
"""Bounded Edge1 Operator runtime backed by the hardened Operations API."""
from __future__ import annotations

import os
import socket
import uuid

from .edge1_operator_capabilities import CapabilityEvaluator
from .edge1_operator_operations_client import Edge1OperationsClient


READ_ONLY_ACTIONS = {
    "snapshot": ("edge1.snapshot",),
    "inventory": (
        "control_surfaces.summary",
        "system.services",
        "network.addresses",
        "network.routes",
        "disk.state",
        "repository.status",
        "repository.head",
        "bigbird.health",
    ),
    "services": ("system.services",),
    "network_state": ("network.addresses", "network.routes", "control_surfaces.listeners"),
    "disk_state": ("disk.state",),
    "bigbird_status": ("bigbird.health", "bigbird.tools"),
    "apache_status": ("apache.status",),
    "asterisk_status": ("asterisk.diagnostics",),
    "telephony_status": ("telephony.health",),
    "telephony_console_control_status": ("telephony.console.control_status",),
    "messaging_status": ("messaging.health",),
    "time_authority_status": ("time_authority.summary",),
    "git_state": ("repository.status", "repository.head"),
    "config_digest": ("config.digest",),
}
CONTROL_ACTIONS = {"telephony_console_reload": "telephony.console.reload_safe"}


def execution_id() -> str:
    return uuid.uuid4().hex[:16]


class Edge1OperatorRuntime:
    """Typed runtime interface; no arbitrary action name reaches the MCP caller."""

    def __init__(
        self,
        client: Edge1OperationsClient | None = None,
        capabilities: CapabilityEvaluator | None = None,
    ) -> None:
        allowed = {action for actions in READ_ONLY_ACTIONS.values() for action in actions}
        allowed.update(CONTROL_ACTIONS.values())
        self.client = client or Edge1OperationsClient(allowed_actions=allowed)
        self.capabilities_policy = capabilities or CapabilityEvaluator()

    def _require(self, tool: str) -> None:
        decision = self.capabilities_policy.decision(tool)
        if not decision.get("allowed"):
            raise PermissionError(str(decision.get("reason", "capability_denied")))

    def identity(self) -> dict:
        self._require("edge1.identity")
        return {
            "service": "edge1-operator-mcp",
            "status": "ready",
            "hostname": socket.gethostname(),
            "principal": os.environ.get("USER", "edge1-operator"),
            "read_only_tools": sorted(READ_ONLY_ACTIONS),
            "capability_manifest_version": self.capabilities_policy.manifest["version"],
        }

    def capabilities(self) -> dict:
        self._require("edge1.capabilities")
        return self.capabilities_policy.summary()

    def operations_status(self) -> dict:
        self._require("edge1.operations_status")
        return {
            "service": "edge1-operations-api",
            "loopback": True,
            "health": self.client.health(),
        }

    def health(self) -> dict:
        self._require("edge1.health")
        health = self.client.health()
        return {
            "status": "ok" if health.get("status") == "ok" else "degraded",
            "service": "edge1-operator-mcp",
            "operations_api": {
                "service": "edge1-operations-api",
                "loopback": True,
                "health": health,
            },
        }

    def _run_group(self, tool: str, group: str) -> dict:
        self._require(tool)
        actions = READ_ONLY_ACTIONS[group]
        return {
            "group": group,
            "read_only": True,
            "results": [self.client.run_action(action) for action in actions],
        }

    def snapshot(self) -> dict:
        return self._run_group("edge1.snapshot", "snapshot")

    def inventory(self) -> dict:
        return self._run_group("edge1.inventory", "inventory")

    def services(self) -> dict:
        return self._run_group("edge1.services", "services")

    def network_state(self) -> dict:
        return self._run_group("edge1.network_state", "network_state")

    def disk_state(self) -> dict:
        return self._run_group("edge1.disk_state", "disk_state")

    def bigbird_status(self) -> dict:
        return self._run_group("edge1.bigbird_status", "bigbird_status")

    def apache_status(self) -> dict:
        return self._run_group("edge1.apache_status", "apache_status")

    def asterisk_status(self) -> dict:
        return self._run_group("edge1.asterisk_status", "asterisk_status")

    def telephony_status(self) -> dict:
        return self._run_group("edge1.telephony_status", "telephony_status")

    def telephony_console_control_status(self) -> dict:
        return self._run_group(
            "edge1.telephony_console_control_status",
            "telephony_console_control_status",
        )

    def messaging_status(self) -> dict:
        return self._run_group("edge1.messaging_status", "messaging_status")

    def time_authority_status(self) -> dict:
        return self._run_group("edge1.time_authority_status", "time_authority_status")

    def git_state(self) -> dict:
        return self._run_group("edge1.git_state", "git_state")

    def config_digest(self) -> dict:
        return self._run_group("edge1.config_digest", "config_digest")

    def telephony_console_reload(
        self,
        *,
        expected_pid: int,
        expected_source_sha256: str,
        expected_repo_head: str,
        idempotency_key: str,
    ) -> dict:
        self._require("edge1.telephony_console_reload")
        return self.client.run_action(
            CONTROL_ACTIONS["telephony_console_reload"],
            {
                "expected_pid": expected_pid,
                "expected_source_sha256": expected_source_sha256,
                "expected_repo_head": expected_repo_head,
                "idempotency_key": idempotency_key,
            },
        )
