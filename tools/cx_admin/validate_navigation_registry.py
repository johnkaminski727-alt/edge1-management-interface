#!/usr/bin/env python3
"""Validate the evidence-backed CX Admin navigation registry."""

import argparse
import json
from pathlib import Path

FORBIDDEN_ROUTE_PARTS = (
    "/_private/",
    "/actions/",
    "/api/",
    "/callbacks/",
    "/include/",
    "/includes/",
    "/payload/",
    "/private/",
    "/src/",
    "/vendor/",
)
FORBIDDEN_FILENAMES = {
    "api.php",
    "autoload.php",
    "bootstrap.php",
    "callback.php",
    "config.php",
    "functions.php",
    "helpers.php",
    "login.php",
    "logout.php",
    "renderer.php",
    "renderers.php",
    "webhook.php",
}
REQUIRED_ROUTE = "/admin/bigbird-operations-console.php"
REQUIRED_MODULE_COUNT = 13


def fail(message):
    raise SystemExit("navigation registry validation failed: " + message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=Path("config/cx_admin/navigation_registry.json"),
    )
    parser.add_argument(
        "--require-menu-ready",
        action="store_true",
        help="fail unless every module has verified labels and authorization metadata",
    )
    args = parser.parse_args()

    data = json.loads(args.registry.read_text(encoding="utf-8"))
    modules = data.get("modules")
    if not isinstance(modules, list):
        fail("modules must be a list")
    if len(modules) != REQUIRED_MODULE_COUNT:
        fail("expected {} modules, found {}".format(REQUIRED_MODULE_COUNT, len(modules)))

    ids = set()
    routes = set()
    unresolved = []

    for module in modules:
        module_id = module.get("id")
        route = module.get("route")
        if not module_id or not route:
            fail("every module requires id and route")
        if module_id in ids:
            fail("duplicate module id: " + module_id)
        if route in routes:
            fail("duplicate route: " + route)
        ids.add(module_id)
        routes.add(route)

        if not route.startswith("/admin/") or not route.endswith(".php"):
            fail("invalid admin PHP route: " + route)
        lower_route = route.lower()
        if any(part in lower_route for part in FORBIDDEN_ROUTE_PARTS):
            fail("implementation route registered: " + route)
        if Path(lower_route).name in FORBIDDEN_FILENAMES:
            fail("implementation filename registered: " + route)
        if module.get("evidence_status") != "verified_route":
            fail("route lacks verified evidence status: " + route)
        if module.get("enabled") is not False:
            fail("discovery registry entries must remain disabled: " + route)

        missing = []
        if not module.get("label"):
            missing.append("label")
        if not module.get("required_role") and not module.get("required_permission"):
            missing.append("authorization")
        if not module.get("section"):
            missing.append("section")
        if not isinstance(module.get("sort_order"), int):
            missing.append("sort_order")
        if missing:
            unresolved.append("{}: {}".format(route, ", ".join(missing)))

    if REQUIRED_ROUTE not in routes:
        fail("required Operations Console route is absent")

    if data.get("deployment_status") != "discovery_only":
        fail("registry must remain discovery_only until source metadata is verified")

    if args.require_menu_ready and unresolved:
        fail("menu metadata unresolved:\n- " + "\n- ".join(unresolved))

    print("CX Admin navigation registry validation passed")
    print("verified routes:", len(routes))
    print("menu-ready routes:", len(routes) - len(unresolved))
    print("unresolved routes:", len(unresolved))
    if unresolved:
        print("deployment status: blocked pending source metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
