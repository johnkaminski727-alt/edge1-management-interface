#!/usr/bin/env python3
"""Fail-closed authority evaluation for Ava operator parity.

This module is intentionally transport-neutral. It decides whether Ava may invoke an
already-authenticated Edge1 or Business159 operator capability. It never stores secrets,
opens a shell, or expands a requested capability into broader authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("AVA_OPERATOR_ROOT", str(Path(__file__).resolve().parents[1])))
POLICY_PATH = Path(os.environ.get("AVA_OPERATOR_POLICY", str(ROOT / "config/ava-operator-parity.json")))
VALID_CLASSES = {"observe", "routine", "conditional", "attended", "restricted"}

class AvaOperatorPolicyError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or value.get("profile") != "ava-operator-parity":
        raise AvaOperatorPolicyError("unsupported Ava operator policy")
    if value.get("execution_enabled") is not True:
        raise AvaOperatorPolicyError("Ava operator execution is disabled")
    classes = value.get("classes")
    if not isinstance(classes, dict) or set(classes) != VALID_CLASSES:
        raise AvaOperatorPolicyError("invalid authority classes")
    rules = value.get("capabilities")
    if not isinstance(rules, list) or not rules:
        raise AvaOperatorPolicyError("operator capability policy is empty")
    seen: set[str] = set()
    for rule in rules:
        prefix = rule.get("prefix") if isinstance(rule, dict) else None
        classification = rule.get("class") if isinstance(rule, dict) else None
        if not isinstance(prefix, str) or not prefix or prefix in seen or classification not in VALID_CLASSES:
            raise AvaOperatorPolicyError("invalid operator capability rule")
        seen.add(prefix)
    return value


def classify(capability: str, policy: dict[str, Any]) -> str:
    if not isinstance(capability, str) or not capability:
        raise AvaOperatorPolicyError("capability is missing")
    matches = [r for r in policy["capabilities"] if capability == r["prefix"] or capability.startswith(r["prefix"] + ".")]
    if not matches:
        return "restricted"
    matches.sort(key=lambda r: len(r["prefix"]), reverse=True)
    return str(matches[0]["class"])


def authorize(capability: str, *, confirmed: bool = False, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    active = policy or load_policy()
    classification = classify(capability, active)
    rule = active["classes"][classification]
    allowed = bool(rule.get("allowed")) and (not rule.get("requires_confirmation") or confirmed)
    return {
        "profile": active["profile"],
        "capability": capability,
        "classification": classification,
        "requires_confirmation": bool(rule.get("requires_confirmation")),
        "confirmed": bool(confirmed),
        "allowed": allowed,
        "reason": "authorized" if allowed else ("confirmation_required" if rule.get("allowed") else "restricted"),
    }
