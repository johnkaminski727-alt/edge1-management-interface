#!/usr/bin/env python3
"""Versioned capability evaluation for the public Edge1 Operator surface."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "config" / "edge1-operator-capabilities.json"
DEFAULT_READ_SCOPES = frozenset({
    "edge1.status.read",
    "edge1.telephony.read",
    "edge1.messaging.read",
})


class CapabilityConfigurationError(RuntimeError):
    pass


def configured_scopes() -> frozenset[str]:
    raw = os.environ.get("EDGE1_OPERATOR_SCOPES")
    if raw is None:
        return DEFAULT_READ_SCOPES
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _validate_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise CapabilityConfigurationError("unsupported capability manifest version")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise CapabilityConfigurationError("capability manifest must define capabilities")
    seen_tools: set[str] = set()
    for name, item in capabilities.items():
        if not isinstance(name, str) or not name.startswith("edge1."):
            raise CapabilityConfigurationError("invalid capability name")
        if not isinstance(item, dict):
            raise CapabilityConfigurationError(f"capability {name} must be an object")
        if set(item) != {"enabled", "access", "required_scope", "tools"}:
            raise CapabilityConfigurationError(f"capability {name} has unexpected fields")
        if not isinstance(item["enabled"], bool) or item["access"] not in {"read", "write"}:
            raise CapabilityConfigurationError(f"capability {name} has invalid policy")
        if not isinstance(item["required_scope"], str) or not item["required_scope"].startswith("edge1."):
            raise CapabilityConfigurationError(f"capability {name} has invalid scope")
        tools = item["tools"]
        if not isinstance(tools, list) or not tools or any(not isinstance(tool, str) for tool in tools):
            raise CapabilityConfigurationError(f"capability {name} has invalid tools")
        for tool in tools:
            if tool in seen_tools:
                raise CapabilityConfigurationError(f"tool {tool} is assigned more than once")
            seen_tools.add(tool)
    return data


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = Path(os.environ.get("EDGE1_OPERATOR_CAPABILITIES", str(path or DEFAULT_MANIFEST)))
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityConfigurationError("capability manifest is unavailable") from exc
    return _validate_manifest(data)


class CapabilityEvaluator:
    def __init__(self, manifest: dict[str, Any] | None = None, scopes: frozenset[str] | None = None) -> None:
        self.manifest = _validate_manifest(manifest) if manifest is not None else load_manifest()
        self.scopes = configured_scopes() if scopes is None else frozenset(scopes)
        self._tool_index: dict[str, tuple[str, dict[str, Any]]] = {}
        for capability, policy in self.manifest["capabilities"].items():
            for tool in policy["tools"]:
                self._tool_index[tool] = (capability, policy)

    def decision(self, tool: str) -> dict[str, Any]:
        mapped = self._tool_index.get(tool)
        if mapped is None:
            return {"allowed": False, "reason": "tool_not_in_capability_manifest", "tool": tool}
        capability, policy = mapped
        required_scope = policy["required_scope"]
        if not policy["enabled"]:
            allowed, reason = False, "capability_disabled"
        elif required_scope not in self.scopes:
            allowed, reason = False, "required_scope_missing"
        else:
            allowed, reason = True, "allowed"
        return {
            "allowed": allowed,
            "reason": reason,
            "tool": tool,
            "capability": capability,
            "access": policy["access"],
            "enabled": policy["enabled"],
            "required_scope": required_scope,
        }

    def summary(self) -> dict[str, Any]:
        items = []
        for capability, policy in sorted(self.manifest["capabilities"].items()):
            items.append({
                "capability": capability,
                "access": policy["access"],
                "enabled": policy["enabled"],
                "required_scope": policy["required_scope"],
                "scope_present": policy["required_scope"] in self.scopes,
                "tools": sorted(policy["tools"]),
            })
        return {"version": self.manifest["version"], "capabilities": items}
