#!/usr/bin/env python3
"""Reconcile provider-side mail objects against the canonical WW.CX routes.

The tool is offline and read-only. It accepts one or more normalized provider
object inventories, compares them with the inbound hub and identity registry,
and writes a report. It never connects to a provider or changes mail service.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

CONTRACT = "wwcx.provider-mail-objects.v1"
REPORT_CONTRACT = "wwcx.provider-mail-reconciliation.v1"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
OBJECT_TYPES = {
    "mailbox",
    "alias",
    "forwarder",
    "distribution_list",
    "system_account",
    "unknown",
}
ACCESS_CLASSES = {
    "private_john",
    "shared_role",
    "provider_admin",
    "system",
    "unknown",
}
DEFAULT_BEHAVIORS = {"reject", "forward", "blackhole", "pipe", "unknown"}
ROUTING_MODES = {"local", "remote", "automatic", "unknown"}


class InventoryError(RuntimeError):
    """Raised when a provider object inventory is malformed."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"unable to read JSON inventory {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"inventory {path} must contain a JSON object")
    return value


def normalize_domain(value: Any, label: str) -> str:
    domain = str(value).strip().casefold().rstrip(".")
    if not DOMAIN_PATTERN.fullmatch(domain):
        raise InventoryError(f"{label} is not a normalized domain")
    return domain


def normalize_address(value: Any, label: str) -> str:
    address = str(value).strip().casefold()
    if "\r" in address or "\n" in address or not EMAIL_PATTERN.fullmatch(address):
        raise InventoryError(f"{label} is not a valid email address")
    local, domain = address.rsplit("@", 1)
    if not local:
        raise InventoryError(f"{label} has an empty local part")
    normalize_domain(domain, f"{label} domain")
    return address


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise InventoryError(f"{label} must be boolean")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InventoryError(f"{label} must be non-empty text")
    return value.strip()


def validate_inventory(inventory: dict[str, Any], label: str = "inventory") -> dict[str, Any]:
    expected_top = {
        "contract",
        "provider_id",
        "provider_family",
        "captured_at",
        "source",
        "objects",
        "default_addresses",
        "domain_routing",
    }
    if set(inventory) != expected_top:
        raise InventoryError(
            f"{label} keys invalid; missing={sorted(expected_top - set(inventory))}, "
            f"unexpected={sorted(set(inventory) - expected_top)}"
        )
    if inventory["contract"] != CONTRACT:
        raise InventoryError(f"{label} uses an unsupported contract")
    provider_id = _require_text(inventory["provider_id"], f"{label}.provider_id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", provider_id):
        raise InventoryError(f"{label}.provider_id is invalid")
    _require_text(inventory["provider_family"], f"{label}.provider_family")
    _require_text(inventory["captured_at"], f"{label}.captured_at")

    source = inventory["source"]
    if not isinstance(source, dict):
        raise InventoryError(f"{label}.source must be an object")
    required_source = {"method", "read_only", "evidence_files"}
    allowed_source = required_source | {"account_reference"}
    if not required_source.issubset(source) or not set(source).issubset(allowed_source):
        raise InventoryError(f"{label}.source keys are invalid")
    _require_text(source["method"], f"{label}.source.method")
    if _require_bool(source["read_only"], f"{label}.source.read_only") is not True:
        raise InventoryError(f"{label}.source must be read-only")
    if not isinstance(source["evidence_files"], list) or not all(
        isinstance(item, str) and item.strip() for item in source["evidence_files"]
    ):
        raise InventoryError(f"{label}.source.evidence_files must be a text list")

    objects = inventory["objects"]
    if not isinstance(objects, list):
        raise InventoryError(f"{label}.objects must be a list")
    normalized_objects: list[dict[str, Any]] = []
    for index, item in enumerate(objects):
        item_label = f"{label}.objects[{index}]"
        if not isinstance(item, dict):
            raise InventoryError(f"{item_label} must be an object")
        required = {
            "address",
            "domain",
            "object_type",
            "destinations",
            "receives_mail",
            "can_send",
            "active",
            "access_class",
            "notes",
        }
        allowed = required | {"quota_bytes"}
        if not required.issubset(item) or not set(item).issubset(allowed):
            raise InventoryError(f"{item_label} keys are invalid")
        address = normalize_address(item["address"], f"{item_label}.address")
        domain = normalize_domain(item["domain"], f"{item_label}.domain")
        if address.rsplit("@", 1)[1] != domain:
            raise InventoryError(f"{item_label} address and domain disagree")
        object_type = _require_text(item["object_type"], f"{item_label}.object_type")
        if object_type not in OBJECT_TYPES:
            raise InventoryError(f"{item_label}.object_type is unsupported")
        if not isinstance(item["destinations"], list):
            raise InventoryError(f"{item_label}.destinations must be a list")
        destinations = [
            normalize_address(value, f"{item_label}.destinations")
            for value in item["destinations"]
        ]
        if len(destinations) != len(set(destinations)):
            raise InventoryError(f"{item_label}.destinations contains duplicates")
        access_class = _require_text(item["access_class"], f"{item_label}.access_class")
        if access_class not in ACCESS_CLASSES:
            raise InventoryError(f"{item_label}.access_class is unsupported")
        notes = item["notes"]
        if not isinstance(notes, str):
            raise InventoryError(f"{item_label}.notes must be text")
        quota = item.get("quota_bytes")
        if quota is not None and (not isinstance(quota, int) or quota < 0):
            raise InventoryError(f"{item_label}.quota_bytes must be null or a non-negative integer")
        normalized_objects.append(
            {
                "provider_id": provider_id,
                "address": address,
                "domain": domain,
                "object_type": object_type,
                "destinations": destinations,
                "receives_mail": _require_bool(item["receives_mail"], f"{item_label}.receives_mail"),
                "can_send": _require_bool(item["can_send"], f"{item_label}.can_send"),
                "active": _require_bool(item["active"], f"{item_label}.active"),
                "access_class": access_class,
                "quota_bytes": quota,
                "notes": notes,
            }
        )

    defaults = inventory["default_addresses"]
    if not isinstance(defaults, list):
        raise InventoryError(f"{label}.default_addresses must be a list")
    normalized_defaults: list[dict[str, Any]] = []
    for index, item in enumerate(defaults):
        item_label = f"{label}.default_addresses[{index}]"
        if not isinstance(item, dict) or set(item) != {"domain", "behavior", "destination"}:
            raise InventoryError(f"{item_label} keys are invalid")
        behavior = _require_text(item["behavior"], f"{item_label}.behavior")
        if behavior not in DEFAULT_BEHAVIORS:
            raise InventoryError(f"{item_label}.behavior is unsupported")
        destination = item["destination"]
        if destination is not None:
            destination = normalize_address(destination, f"{item_label}.destination")
        if behavior == "forward" and destination is None:
            raise InventoryError(f"{item_label} forward behavior requires a destination")
        normalized_defaults.append(
            {
                "provider_id": provider_id,
                "domain": normalize_domain(item["domain"], f"{item_label}.domain"),
                "behavior": behavior,
                "destination": destination,
            }
        )

    routing = inventory["domain_routing"]
    if not isinstance(routing, list):
        raise InventoryError(f"{label}.domain_routing must be a list")
    normalized_routing: list[dict[str, str]] = []
    for index, item in enumerate(routing):
        item_label = f"{label}.domain_routing[{index}]"
        if not isinstance(item, dict) or set(item) != {"domain", "mode"}:
            raise InventoryError(f"{item_label} keys are invalid")
        mode = _require_text(item["mode"], f"{item_label}.mode")
        if mode not in ROUTING_MODES:
            raise InventoryError(f"{item_label}.mode is unsupported")
        normalized_routing.append(
            {
                "provider_id": provider_id,
                "domain": normalize_domain(item["domain"], f"{item_label}.domain"),
                "mode": mode,
            }
        )

    normalized = dict(inventory)
    normalized["provider_id"] = provider_id
    normalized["objects"] = normalized_objects
    normalized["default_addresses"] = normalized_defaults
    normalized["domain_routing"] = normalized_routing
    return normalized


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    active: set[str] = set()
    complete: set[str] = set()

    def canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
        body = nodes[:-1]
        rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
        best = min(rotations)
        return best + (best[0],)

    def visit(node: str) -> None:
        if node in complete:
            return
        if node in active:
            start = visiting.index(node)
            cycles.add(canonical_cycle(visiting[start:] + [node]))
            return
        active.add(node)
        visiting.append(node)
        for target in sorted(graph.get(node, set())):
            visit(target)
        visiting.pop()
        active.remove(node)
        complete.add(node)

    for node in sorted(graph):
        visit(node)
    return [list(item) for item in sorted(cycles)]


def reconcile(
    inbound: dict[str, Any],
    identities: dict[str, Any],
    inventories: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    routes = inbound.get("routing", {}).get("routes", {})
    if not isinstance(routes, dict) or not routes:
        raise InventoryError("inbound configuration does not contain routes")
    expected_routes = {
        normalize_address(address, "route address"): normalize_address(
            definition.get("destination"), f"route destination for {address}"
        )
        for address, definition in routes.items()
        if isinstance(definition, dict) and definition.get("enabled") is True
    }
    managed_domains = {normalize_domain(item, "managed domain") for item in inbound.get("domains", [])}
    if not managed_domains:
        raise InventoryError("inbound configuration has no managed domains")

    mailboxes = identities.get("mailboxes", {})
    private_mailbox = normalize_address(
        mailboxes.get("private_john", {}).get("address"), "private delivery mailbox"
    )
    shared_mailbox = normalize_address(
        mailboxes.get("shared_role", {}).get("address"), "shared delivery mailbox"
    )
    system_sender = normalize_address(
        identities.get("system_senders", {}).get("noreply", {}).get("address"),
        "system sender",
    )
    internal_addresses = {private_mailbox, shared_mailbox}
    sender_addresses = {
        normalize_address(value, "registered sender")
        for value in identities.get("sender_selection", {}).get("recipient_to_sender", {}).values()
    }
    sender_addresses.add(system_sender)

    normalized_inventories = [
        validate_inventory(value, f"inventory[{index}]")
        for index, value in enumerate(inventories)
    ]
    objects_by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    defaults: list[dict[str, Any]] = []
    domain_routing: list[dict[str, str]] = []
    for inventory in normalized_inventories:
        for item in inventory["objects"]:
            objects_by_address[item["address"]].append(item)
        defaults.extend(inventory["default_addresses"])
        domain_routing.extend(inventory["domain_routing"])

    route_results: list[dict[str, Any]] = []
    missing_expected: list[str] = []
    inactive_expected: list[str] = []
    forwarder_mismatches: list[dict[str, Any]] = []
    for address, expected_destination in sorted(expected_routes.items()):
        observed = objects_by_address.get(address, [])
        active_receivers = [item for item in observed if item["active"] and item["receives_mail"]]
        status = "missing"
        if not observed:
            missing_expected.append(address)
        elif not active_receivers:
            status = "inactive_or_not_receiving"
            inactive_expected.append(address)
        else:
            exact = [
                item
                for item in active_receivers
                if item["object_type"] in {"alias", "forwarder"}
                and expected_destination in item["destinations"]
            ]
            forwarding = [
                item
                for item in active_receivers
                if item["object_type"] in {"alias", "forwarder"}
            ]
            local = [
                item
                for item in active_receivers
                if item["object_type"] in {"mailbox", "distribution_list", "system_account"}
            ]
            if exact:
                status = "exact_forwarder"
            elif forwarding:
                status = "forwarder_destination_mismatch"
                forwarder_mismatches.append(
                    {
                        "address": address,
                        "expected_destination": expected_destination,
                        "observed_destinations": sorted(
                            {destination for item in forwarding for destination in item["destinations"]}
                        ),
                    }
                )
            elif local:
                status = "local_object_present"
            else:
                status = "object_present_unknown_type"
        route_results.append(
            {
                "address": address,
                "expected_destination": expected_destination,
                "status": status,
                "observed_objects": observed,
            }
        )

    unexpected_managed = sorted(
        address
        for address, observed in objects_by_address.items()
        if address.rsplit("@", 1)[1] in managed_domains
        and address not in expected_routes
        and address not in internal_addresses
        and address != system_sender
        and any(item["active"] and item["receives_mail"] for item in observed)
    )

    duplicate_provider_objects = [
        {
            "address": address,
            "providers": sorted({item["provider_id"] for item in observed}),
            "object_count": len(observed),
        }
        for address, observed in sorted(objects_by_address.items())
        if len({item["provider_id"] for item in observed}) > 1
    ]

    access_mismatches: list[dict[str, str]] = []
    internal_status: list[dict[str, Any]] = []
    for address, expected_access in (
        (private_mailbox, "private_john"),
        (shared_mailbox, "shared_role"),
    ):
        observed = objects_by_address.get(address, [])
        active = [item for item in observed if item["active"] and item["receives_mail"]]
        if active and not any(item["access_class"] == expected_access for item in active):
            access_mismatches.append(
                {
                    "address": address,
                    "expected_access_class": expected_access,
                    "observed_access_classes": ",".join(
                        sorted({item["access_class"] for item in active})
                    ),
                }
            )
        internal_status.append(
            {
                "address": address,
                "expected_access_class": expected_access,
                "status": "present" if active else "not_observed",
                "observed_objects": observed,
            }
        )

    sender_status = []
    for address in sorted(sender_addresses):
        observed = objects_by_address.get(address, [])
        senders = [item for item in observed if item["active"] and item["can_send"]]
        sender_status.append(
            {
                "address": address,
                "status": "sender_capable" if senders else "not_sender_capable_or_not_observed",
                "observed_objects": observed,
            }
        )

    catch_all_hazards = [
        item
        for item in defaults
        if item["domain"] in managed_domains and item["behavior"] != "reject"
    ]
    routing_unknown_or_automatic = [
        item
        for item in domain_routing
        if item["domain"] in managed_domains and item["mode"] in {"automatic", "unknown"}
    ]

    graph: dict[str, set[str]] = defaultdict(set)
    known_addresses = set(objects_by_address)
    for address, observed in objects_by_address.items():
        for item in observed:
            if item["active"] and item["object_type"] in {"alias", "forwarder"}:
                graph[address].update(
                    destination for destination in item["destinations"] if destination in known_addresses
                )
    forwarder_cycles = _find_cycles(graph)

    critical_gaps: list[dict[str, Any]] = []
    if missing_expected:
        critical_gaps.append({"type": "missing_expected_addresses", "items": missing_expected})
    if inactive_expected:
        critical_gaps.append({"type": "inactive_expected_addresses", "items": inactive_expected})
    if forwarder_mismatches:
        critical_gaps.append({"type": "forwarder_destination_mismatches", "items": forwarder_mismatches})
    if access_mismatches:
        critical_gaps.append({"type": "internal_access_class_mismatches", "items": access_mismatches})
    if forwarder_cycles:
        critical_gaps.append({"type": "forwarder_cycles", "items": forwarder_cycles})

    warnings: list[dict[str, Any]] = []
    if unexpected_managed:
        warnings.append({"type": "unexpected_managed_addresses", "items": unexpected_managed})
    if duplicate_provider_objects:
        warnings.append({"type": "addresses_observed_at_multiple_providers", "items": duplicate_provider_objects})
    if catch_all_hazards:
        warnings.append({"type": "non_reject_default_addresses", "items": catch_all_hazards})
    if routing_unknown_or_automatic:
        warnings.append({"type": "unresolved_domain_routing_modes", "items": routing_unknown_or_automatic})

    return {
        "contract": REPORT_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "read_only": True,
        "provider_ids": sorted(item["provider_id"] for item in normalized_inventories),
        "managed_domains": sorted(managed_domains),
        "summary": {
            "expected_route_count": len(expected_routes),
            "observed_address_count": len(objects_by_address),
            "missing_expected_count": len(missing_expected),
            "inactive_expected_count": len(inactive_expected),
            "forwarder_mismatch_count": len(forwarder_mismatches),
            "unexpected_managed_count": len(unexpected_managed),
            "forwarder_cycle_count": len(forwarder_cycles),
            "critical_gap_count": len(critical_gaps),
            "warning_count": len(warnings),
            "ready_for_pilot": not critical_gaps,
        },
        "route_results": route_results,
        "internal_mailboxes": internal_status,
        "sender_status": sender_status,
        "default_addresses": defaults,
        "domain_routing": domain_routing,
        "critical_gaps": critical_gaps,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    root = pathlib.Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inbound-config",
        type=pathlib.Path,
        default=root / "config" / "messaging" / "inbound-mail-hub.json",
    )
    parser.add_argument(
        "--identity-registry",
        type=pathlib.Path,
        default=root / "config" / "messaging" / "mail-identities.json",
    )
    parser.add_argument(
        "--inventory",
        type=pathlib.Path,
        action="append",
        required=True,
        help="Normalized provider inventory; may be supplied more than once.",
    )
    parser.add_argument("--output", type=pathlib.Path, default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 when critical reconciliation gaps remain.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inbound = load_json(args.inbound_config)
        identities = load_json(args.identity_registry)
        inventories = [load_json(path) for path in args.inventory]
        report = reconcile(inbound, identities, inventories)
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    if args.strict and report["critical_gaps"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
