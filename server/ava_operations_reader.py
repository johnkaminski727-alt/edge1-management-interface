#!/usr/bin/env python3
"""Fail-closed read-only Edge1 capability adapter for Ava.

The adapter reuses the authenticated loopback BigBird/Edge1 control-plane
broker. It has no shell, filesystem, deployment, service-control, URL, or
arbitrary action input and refuses every non-read capability.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import bigbird_edge1_control_plane as control_plane

ROOT = Path(os.environ.get("BIGBIRD_CONTROL_PLANE_ROOT", "/opt/edge1-management-interface"))
PROFILE_PATH = Path(
    os.environ.get(
        "AVA_OPERATIONS_READER_PROFILE",
        str(ROOT / "integrations/ava-operations-reader/profile-v1.json"),
    )
)
TOOL_MANIFEST_PATH = Path(
    os.environ.get(
        "AVA_OPERATIONS_READER_TOOL_MANIFEST",
        str(ROOT / "integrations/ava-operations-reader/tool-manifest-v1.json"),
    )
)
ALLOWED_PROFILE_FIELDS = {
    "version", "profile", "mode", "max_age_seconds", "capabilities", "forbidden_classes"
}


class AvaOperationsReaderError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_profile(path: Path = PROFILE_PATH) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != ALLOWED_PROFILE_FIELDS:
        raise AvaOperationsReaderError("unexpected profile fields")
    if value.get("version") != 1 or value.get("profile") != "ava-operations-reader":
        raise AvaOperationsReaderError("unsupported Ava Operations Reader profile")
    if value.get("mode") != "read_only":
        raise AvaOperationsReaderError("Ava Operations Reader must remain read-only")
    maximum_age = value.get("max_age_seconds")
    if not isinstance(maximum_age, int) or not 1 <= maximum_age <= 300:
        raise AvaOperationsReaderError("invalid freshness limit")
    names = value.get("capabilities")
    if not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names):
        raise AvaOperationsReaderError("invalid capability selection")
    if len(names) != len(set(names)):
        raise AvaOperationsReaderError("duplicate capability selection")
    forbidden = value.get("forbidden_classes")
    if set(forbidden or ()) != {"staged_write", "staged_write_apply", "privileged_action"}:
        raise AvaOperationsReaderError("forbidden capability classes are incomplete")
    return value


def load_tool_manifest(path: Path = TOOL_MANIFEST_PATH) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or value.get("integration") != "ava-operations-reader":
        raise AvaOperationsReaderError("unsupported Ava tool manifest")
    if value.get("mode") != "read_only" or value.get("dispatcher") != "run":
        raise AvaOperationsReaderError("unsafe Ava tool manifest mode")
    tools = value.get("tools")
    if not isinstance(tools, list) or not tools:
        raise AvaOperationsReaderError("Ava tool manifest is empty")
    return value


def validate_contract(profile: dict, manifest: dict, tool_manifest: dict) -> dict[str, dict]:
    capabilities = control_plane.capability_map(manifest)
    selected: dict[str, dict] = {}
    for name in profile["capabilities"]:
        capability = capabilities.get(name)
        if capability is None:
            raise AvaOperationsReaderError("profile capability missing from control plane: " + name)
        if capability.get("class") != "read" or not capability.get("enabled"):
            raise AvaOperationsReaderError("profile capability is not enabled read-only: " + name)
        if capability.get("backend") != "operations_api" or not capability.get("action"):
            raise AvaOperationsReaderError("profile capability has an unsupported broker: " + name)
        selected[name] = capability

    tools = tool_manifest["tools"]
    tool_names = [item.get("name") for item in tools]
    if tool_names != profile["capabilities"]:
        raise AvaOperationsReaderError("Ava tool/profile contract drift")
    for tool in tools:
        name = tool["name"]
        if tool.get("read_only") is not True:
            raise AvaOperationsReaderError("Ava tool is not read-only: " + name)
        if tool.get("scope") != selected[name].get("scope"):
            raise AvaOperationsReaderError("Ava tool scope drift: " + name)
        schema = tool.get("input_schema")
        if schema != {"type": "object", "properties": {}, "additionalProperties": False}:
            raise AvaOperationsReaderError("Ava tool accepts unexpected input: " + name)
    return selected


def contracts() -> tuple[dict, dict, dict, dict[str, dict]]:
    profile = load_profile()
    manifest = control_plane.load_manifest()
    tool_manifest = load_tool_manifest()
    selected = validate_contract(profile, manifest, tool_manifest)
    return profile, manifest, tool_manifest, selected


def validate_live_capability(discovery: dict, name: str) -> dict:
    health = discovery.get("health") or {}
    if health.get("mutations_enabled") is not False:
        raise AvaOperationsReaderError("Operations API mutations must remain disabled")
    discovered = {item.get("name"): item for item in discovery.get("capabilities", [])}
    item = discovered.get(name)
    if item is None or not item.get("available"):
        raise AvaOperationsReaderError("selected capability is unavailable: " + name)
    if item.get("broker_mutating") is not False:
        raise AvaOperationsReaderError("broker no longer classifies capability as read-only: " + name)
    return item


def capabilities() -> dict:
    profile, manifest, _tools, selected = contracts()
    discovery = control_plane.discover(manifest)
    rows = []
    for name in profile["capabilities"]:
        item = validate_live_capability(discovery, name)
        rows.append({
            "name": name,
            "scope": selected[name]["scope"],
            "read_only": True,
            "available": bool(item.get("available")),
        })
    observed = utc_now()
    return {
        "schema_version": 1,
        "profile": profile["profile"],
        "mode": profile["mode"],
        "observed_at_utc": observed,
        "freshness": {"observed_at_utc": observed, "max_age_seconds": profile["max_age_seconds"]},
        "broker_health": discovery["health"],
        "capabilities": rows,
    }


def _structured_stdout(stdout: object) -> dict:
    if not isinstance(stdout, str):
        return {"format": "none", "value": None}
    text = stdout.strip()
    if not text:
        return {"format": "empty", "value": None}
    try:
        return {"format": "json", "value": json.loads(text)}
    except json.JSONDecodeError:
        return {"format": "text", "value": text}


def run(name: str) -> dict:
    profile, manifest, _tools, selected = contracts()
    capability = selected.get(name)
    if capability is None:
        raise AvaOperationsReaderError("capability is not in Ava Operations Reader profile")
    validate_live_capability(control_plane.discover(manifest), name)
    payload = control_plane.run_capability(manifest, name)
    if not isinstance(payload, dict):
        raise AvaOperationsReaderError("broker returned an invalid result")
    observed = utc_now()
    return {
        "schema_version": 1,
        "profile": profile["profile"],
        "capability": name,
        "scope": capability["scope"],
        "read_only": True,
        "observed_at_utc": observed,
        "freshness": {"observed_at_utc": observed, "max_age_seconds": profile["max_age_seconds"]},
        "audit": {
            "event_id": payload.get("event_id"),
            "status": payload.get("status"),
            "duration_ms": payload.get("duration_ms"),
            "exit_code": payload.get("exit_code"),
        },
        "data": _structured_stdout(payload.get("stdout")),
        "diagnostics": {
            "stderr_present": bool(payload.get("stderr")),
            "output_truncated": bool(payload.get("output_truncated", False)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capabilities")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("capability")
    args = parser.parse_args()
    result = capabilities() if args.command == "capabilities" else run(args.capability)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
