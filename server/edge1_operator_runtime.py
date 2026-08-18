#!/usr/bin/env python3
"""Bounded Edge1 Operator runtime backed by the hardened Operations API."""
from __future__ import annotations

import os
import socket
import uuid

from .edge1_operator_operations_client import Edge1OperationsClient


READ_ONLY_ACTIONS = {
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
    "messaging_status": ("messaging.health",),
    "time_authority_status": ("time_authority.summary",),
    "git_state": ("repository.status", "repository.head"),
    "config_digest": ("config.digest",),
}


def execution_id() -> str:
    return uuid.uuid4().hex[:16]


class Edge1OperatorRuntime:
    """Typed runtime interface; no arbitrary action name reaches the MCP caller."""

    def __init__(self, client: Edge1OperationsClient | None = None) -> None:
        allowed = {action for actions in READ_ONLY_ACTIONS.values() for action in actions}
        self.client = client or Edge1OperationsClient(allowed_actions=allowed)

    def identity(self) -> dict:
        return {
            "service": "edge1-operator-mcp",
            "status": "ready",
            "hostname": socket.gethostname(),
            "principal": os.environ.get("USER", "edge1-operator"),
            "read_only_tools": sorted(READ_ONLY_ACTIONS),
        }

    def operations_status(self) -> dict:
        return {
            "service": "edge1-operations-api",
            "loopback": True,
            "health": self.client.health(),
        }

    def health(self) -> dict:
        operations = self.operations_status()
        health = operations["health"]
        return {
            "status": "ok" if health.get("status") == "ok" else "degraded",
            "service": "edge1-operator-mcp",
            "operations_api": operations,
        }

    def _run_group(self, group: str) -> dict:
        actions = READ_ONLY_ACTIONS[group]
        return {
            "group": group,
            "read_only": True,
            "results": [self.client.run_action(action) for action in actions],
        }

    def inventory(self) -> dict:
        return self._run_group("inventory")

    def services(self) -> dict:
        return self._run_group("services")

    def network_state(self) -> dict:
        return self._run_group("network_state")

    def disk_state(self) -> dict:
        return self._run_group("disk_state")

    def bigbird_status(self) -> dict:
        return self._run_group("bigbird_status")

    def apache_status(self) -> dict:
        return self._run_group("apache_status")

    def asterisk_status(self) -> dict:
        return self._run_group("asterisk_status")

    def telephony_status(self) -> dict:
        return self._run_group("telephony_status")

    def messaging_status(self) -> dict:
        return self._run_group("messaging_status")

    def time_authority_status(self) -> dict:
        return self._run_group("time_authority_status")

    def git_state(self) -> dict:
        return self._run_group("git_state")

    def config_digest(self) -> dict:
        return self._run_group("config_digest")
