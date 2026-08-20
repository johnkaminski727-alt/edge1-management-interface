#!/usr/bin/env python3
"""Validate the canonical Edge1 Operator navigation registry without granting authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "config" / "edge1_operator" / "navigation_registry.json"
SECURITY_HTTP = ROOT / "config" / "security" / "edge1-security-auth-http.json"
UNIFIED_COMMS = ROOT / "config" / "communications" / "unified-communications.json"

FORBIDDEN_ROUTE_PARTS = ("/api/", "/actions/", "/callback", "/include", "/private/", "/src/")
ALLOWED_AVAILABILITY = {
    "accepted_live",
    "loopback_only",
    "runtime_only",
    "staged_disabled",
    "browser_acceptance_unverified",
}


def fail(message: str) -> None:
    raise SystemExit("edge1 operator navigation validation failed: " + message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    data = json.loads(args.registry.read_text(encoding="utf-8"))

    if data.get("contract") != "wwcx.edge1-operator-navigation.v1":
        fail("unexpected contract")
    safety = data.get("safety", {})
    required_false = (
        "navigation_grants_authorization",
        "generic_execution_authorized",
        "production_traffic_authorized",
        "mutations_enabled",
        "unknown_status_is_healthy",
    )
    for key in required_false:
        if safety.get(key) is not False:
            fail(f"safety.{key} must be false")

    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        fail("modules must be a non-empty list")

    ids: set[str] = set()
    browser_routes: set[str] = set()
    labels_by_section: set[tuple[str, str]] = set()
    for item in modules:
        module_id = item.get("id")
        label = item.get("label")
        section = item.get("section")
        route = item.get("browser_route")
        availability = item.get("availability")
        if not module_id or not label or not section:
            fail("every module requires id, label, and section")
        if module_id in ids:
            fail("duplicate module id: " + module_id)
        ids.add(module_id)
        key = (section, label)
        if key in labels_by_section:
            fail(f"duplicate label in section {section}: {label}")
        labels_by_section.add(key)
        if availability not in ALLOWED_AVAILABILITY:
            fail(f"unsupported availability for {module_id}: {availability}")
        if not item.get("authorization"):
            fail(f"authorization metadata missing for {module_id}")
        if not item.get("evidence_status"):
            fail(f"evidence_status missing for {module_id}")
        if not isinstance(item.get("sort_order"), int):
            fail(f"sort_order missing for {module_id}")
        if route is not None:
            if not isinstance(route, str) or not route.startswith("/") or route.startswith("//"):
                fail(f"invalid browser route for {module_id}")
            lower = route.lower()
            if any(part in lower for part in FORBIDDEN_ROUTE_PARTS):
                fail(f"implementation/API route cannot be navigable: {route}")
            if route in browser_routes:
                fail("duplicate browser route: " + route)
            browser_routes.add(route)
            if availability != "accepted_live":
                fail(f"non-live module exposed as browser navigation: {module_id}")
        if item.get("palette") and route is None:
            fail(f"palette module lacks accepted browser route: {module_id}")
        if item.get("palette") and availability != "accepted_live":
            fail(f"palette module is not accepted live: {module_id}")

    if "operations-center" not in ids or "/edge1-status/" not in browser_routes:
        fail("canonical Operations Center is missing")
    if "security-console" not in ids or "wwcx-ai" not in ids:
        fail("staged Security Console and WW.CX AI evidence entries are required")
    if any("store admin" in str(item.get("label", "")).lower() for item in modules):
        fail("Store Admin must remain a separate interface")

    security = json.loads(SECURITY_HTTP.read_text(encoding="utf-8"))
    security_item = next(item for item in modules if item["id"] == "security-console")
    if security.get("live_route_authorized") is not True and security_item.get("browser_route") is not None:
        fail("Security Console cannot be navigable while live_route_authorized is false")

    comms = json.loads(UNIFIED_COMMS.read_text(encoding="utf-8"))
    if comms.get("production_traffic_authorized") is not False:
        fail("communications production traffic authorization changed")
    if comms.get("generic_execution_authorized") is not False:
        fail("communications generic execution authorization changed")
    for channel in comms.get("channels", []):
        if channel.get("mutation_authorized") is not False:
            fail("communications mutation authorization changed")
        if channel.get("live_traffic_authorized") is not False:
            fail("communications live traffic authorization changed")

    print("Edge1 Operator navigation registry validation passed")
    print("modules:", len(modules))
    print("accepted browser routes:", len(browser_routes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
