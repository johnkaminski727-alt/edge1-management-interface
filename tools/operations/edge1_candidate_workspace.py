#!/usr/bin/env python3
"""Edge1 candidate configuration workspace G1: PURE, IN-MEMORY PROTOTYPE.

This model never executes commands, opens production files, contacts a service,
or persists state. No production networking/firewall/DNS setting is supported.
Integration requires separate API authorization and an approved apply runner.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
from typing import Any

MAX_ITEMS = 48
ALLOWED_SECTIONS = frozenset({"dashboard", "inventory", "alerts"})
DASHBOARD_PANELS = frozenset({"system", "services", "security", "network", "jobs"})
ALLOWED_KEYS = {
    "dashboard": frozenset({"refresh_seconds", "panels"}),
    "inventory": frozenset({"show_interfaces", "show_routes", "show_vpn_peers"}),
    "alerts": frozenset({"show_warnings", "max_items"}),
}


class CandidateError(ValueError):
    """Untrusted or conflicting candidate cannot be accepted."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def revision(config: dict) -> str:
    return hashlib.sha256(canonical(config).encode("ascii")).hexdigest()


def validate(config: Any) -> dict:
    """Require exact non-secret display-settings schema and strict data types."""
    if not isinstance(config, dict) or set(config) != ALLOWED_SECTIONS:
        raise CandidateError("Expected dashboard, inventory and alerts sections")
    for section, keys in ALLOWED_KEYS.items():
        if not isinstance(config[section], dict) or set(config[section]) != keys:
            raise CandidateError("Unexpected or missing settings in " + section)
    dashboard = config["dashboard"]
    if type(dashboard["refresh_seconds"]) is not int or not (10 <= dashboard["refresh_seconds"] <= 3600):
        raise CandidateError("refresh_seconds must be an integer from 10 to 3600")
    panels = dashboard["panels"]
    if not isinstance(panels, list) or not (1 <= len(panels) <= len(DASHBOARD_PANELS)):
        raise CandidateError("panels must be a nonempty list")
    if any(not isinstance(p, str) or p not in DASHBOARD_PANELS for p in panels):
        raise CandidateError("Unexpected panel")
    if len(set(panels)) != len(panels):
        raise CandidateError("Duplicate panel")
    for field, value in config["inventory"].items():
        if type(value) is not bool:
            raise CandidateError("inventory." + field + " must be boolean")
    if type(config["alerts"]["show_warnings"]) is not bool:
        raise CandidateError("alerts.show_warnings must be boolean")
    cap = config["alerts"]["max_items"]
    if type(cap) is not int or not 1 <= cap <= MAX_ITEMS:
        raise CandidateError("alerts.max_items out of range")
    output = copy.deepcopy(config)
    output["dashboard"]["panels"].sort()
    return output


def initial_settings() -> dict:
    return {
        "dashboard": {"refresh_seconds": 30, "panels": ["system", "services", "security", "network", "jobs"]},
        "inventory": {"show_interfaces": True, "show_routes": True, "show_vpn_peers": False},
        "alerts": {"show_warnings": True, "max_items": 20},
    }


class Workspace:
    """Candidate overlay and human-readable preview, no execution capability."""

    def __init__(self, running: dict):
        self._running = validate(running)
        self._candidate = copy.deepcopy(self._running)
        self._base_revision = revision(self._running)
        self._events: list[dict] = []

    @property
    def running(self) -> dict:
        return copy.deepcopy(self._running)

    @property
    def candidate(self) -> dict:
        return copy.deepcopy(self._candidate)

    @property
    def base_revision(self) -> str:
        return self._base_revision

    @property
    def pending(self) -> bool:
        return self._candidate != self._running

    @property
    def audit(self) -> list[dict]:
        return copy.deepcopy(self._events)

    def propose(self, section: str, field: str, value: Any, *, expected_revision: str) -> dict:
        if expected_revision != self._base_revision:
            raise CandidateError("Stale candidate base revision")
        if section not in ALLOWED_KEYS or field not in ALLOWED_KEYS[section]:
            raise CandidateError("Unknown configuration setting")
        next_config = copy.deepcopy(self._candidate)
        next_config[section][field] = copy.deepcopy(value)
        next_config = validate(next_config)
        was = revision(self._candidate)
        self._candidate = next_config
        self._events.append({
            "event": "candidate_proposed",
            "section": section,
            "field": field,
            "before_sha256": was,
            "after_sha256": revision(self._candidate),
            "execution": "none",
        })
        return self.preview()

    def discard(self, *, expected_revision: str) -> dict:
        if expected_revision != self._base_revision:
            raise CandidateError("Stale candidate base revision")
        self._candidate = copy.deepcopy(self._running)
        self._events.append({"event": "candidate_discarded", "execution": "none"})
        return self.preview()

    def preview(self) -> dict:
        old = canonical(self._running).splitlines(keepends=True)
        new = canonical(self._candidate).splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old, new, fromfile="running", tofile="candidate"))
        changes = []
        for section in sorted(ALLOWED_SECTIONS):
            for field in sorted(ALLOWED_KEYS[section]):
                before = self._running[section][field]
                after = self._candidate[section][field]
                if before != after:
                    changes.append({"path": section + "." + field, "running": copy.deepcopy(before), "candidate": copy.deepcopy(after)})
        return {
            "schema": "edge1-candidate-workspace-g1",
            "base_revision": self._base_revision,
            "candidate_revision": revision(self._candidate),
            "pending": self.pending,
            "validation": "passed",
            "execution_allowed": False,
            "diff": diff,
            "changes": changes,
        }

    def rebase_running(self, updated_running: dict) -> None:
        """Fail instead of silently overwriting pending edits on external drift."""
        updated = validate(updated_running)
        if self.pending and revision(updated) != self._base_revision:
            raise CandidateError("Running configuration changed; resolve drift before rebase")
        self._running = updated
        self._candidate = copy.deepcopy(updated)
        self._base_revision = revision(updated)
        self._events.append({"event": "running_snapshot_refreshed", "execution": "none"})
