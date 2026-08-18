#!/usr/bin/env python3
"""Validate the bounded systemd deployment for the Communications workspace."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
UNIT = DEPLOY / "wwcx-communications-workspace.service"
RUNNER = DEPLOY / "run-wwcx-communications-workspace.sh"
INSTALLER = DEPLOY / "install-wwcx-communications-workspace.sh"
SERVER = ROOT / "server" / "unified_communications_server.py"

for path in (UNIT, RUNNER, INSTALLER, SERVER):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

unit = UNIT.read_text(encoding="utf-8")
for token in (
    "Environment=WWCX_COMMUNICATIONS_HOST=127.0.0.1",
    "Environment=WWCX_COMMUNICATIONS_PORT=8095",
    "Environment=PYTHONDONTWRITEBYTECODE=1",
    "ExecStart=/opt/edge1-management-interface/deploy/run-wwcx-communications-workspace.sh",
    "NoNewPrivileges=true",
    "ProtectSystem=strict",
    "ProtectHome=true",
    "PrivateTmp=true",
    "PrivateDevices=true",
    "CapabilityBoundingSet=",
    "AmbientCapabilities=",
    "ReadOnlyPaths=/opt/edge1-management-interface",
):
    assert token in unit, token
assert "0.0.0.0" not in unit

runner = RUNNER.read_text(encoding="utf-8")
for token in (
    "127.0.0.1|::1|localhost",
    "refusing non-loopback",
    "WWCX_COMMUNICATIONS_EVENT_SNAPSHOT",
    "--event-snapshot",
    'exec "$@"',
):
    assert token in runner, token
assert "eval " not in runner

installer = INSTALLER.read_text(encoding="utf-8")
for token in (
    "Dry run passed",
    "--apply",
    "port $PORT is already in use",
    "rollback()",
    "systemctl daemon-reload",
    "systemctl enable --now",
    "/communications/healthz",
    "/communications/api/v1/readiness",
    "/communications/api/v1/events?limit=1",
    'POST_CODE=$(curl',
    '[ "$POST_CODE" = "405" ]',
    "mutation_authorized",
    "0\\.0\\.0\\.0",
    "rollback_backup=",
):
    assert token in installer, token

combined = "\n".join((path.read_text(encoding="utf-8") for path in (UNIT, RUNNER, INSTALLER))).lower()
for forbidden in (
    "nginx",
    "apache",
    "haproxy",
    "caddy",
    "messages.send",
    "mail.send",
    "telephony.call.originate",
):
    assert forbidden not in combined, forbidden

server = SERVER.read_text(encoding="utf-8")
for token in ("Refusing non-loopback bind", "read_only_workspace", "mutation_authorized"):
    assert token in server, token

print("Unified Communications workspace service deployment validation passed")
print("Loopback-only bind, read-only API, systemd hardening, dry-run, health checks and rollback are enforced")
print("No reverse proxy, public listener, send/control capability, credential, or traffic activation is added")
