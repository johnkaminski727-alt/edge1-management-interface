#!/usr/bin/env python3
"""Validate and reconcile the repository-declared Edge1 restricted-artifact manifest.

This module is read-only. It does not copy, move, rename, publish, route, delete,
chmod, chown, reload, or mutate either the public or restricted tree.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from edge1_ops_access_policy import (
    GENERAL_SCOPE,
    load_policy as load_access_policy,
    match_route,
    validate_policy as validate_access_policy,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "security" / "edge1-restricted-artifact-migration-manifest.json"
DEFAULT_ACCESS_POLICY = ROOT / "config" / "security" / "edge1-authenticated-operations-policy.json"
CONTRACT = "wwcx.edge1-restricted-artifact-migration-manifest.v1"
SOURCE_ROOT = "/var/www/edge1-status"
SOURCE_ROUTE_ROOT = "/edge1-status/"
TARGET_RELEASE_ROOT = "/var/lib/wwcx-edge1-ops/releases"
TARGET_ROUTE_ROOT = "/edge1-ops/"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MODE_RE = re.compile(r"^0[0-7]{3}$")
CLASSIFICATIONS = {
    "restricted_operations_landing",
    "restricted_security_operations",
    "restricted_network_operations",
    "restricted_financial_operations",
    "restricted_evidence_and_reports",
    "restricted_operations_data",
}
TOP_LEVEL_FIELDS = {
    "contract", "status", "enabled", "staging_authorized",
    "cutover_authorized", "deletion_authorized", "source_public_root",
    "source_route_root", "target_release_root", "target_route_root",
    "hash_algorithm", "unknown_artifact_action", "duplicate_target_action",
    "missing_known_action", "source_mutation_allowed", "repository_evidence",
    "known_exact_artifacts", "known_prefix_groups", "acceptance",
}
EXACT_FIELDS = {
    "source_relative", "target_relative", "classification",
    "required_scopes", "repository_source",
}
PREFIX_FIELDS = {
    "source_prefix", "target_prefix", "classification",
    "required_scopes", "live_enumeration_required",
}
ACCEPTANCE_FIELDS = {
    "fresh_live_route_inventory_required",
    "fresh_live_filesystem_inventory_required",
    "sha256_inventory_required",
    "source_backup_required",
    "target_release_validation_required",
    "authorized_route_matrix_required",
    "unauthorized_route_matrix_required",
    "unknown_artifacts_preserved",
    "duplicate_targets_blocked",
    "source_tree_unchanged",
    "public_cutover_performed",
    "detailed_artifacts_removed",
    "traffic_controls_changed",
    "live_change_authorized",
}


def load_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def safe_relative(value: Any, *, directory: bool = False) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ValueError("artifact path must be a non-empty relative path")
    if any(token in value for token in ("\\", "?", "#", "%", "\x00")):
        raise ValueError("artifact path contains an ambiguous token")
    if "//" in value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("artifact path contains an unsafe segment")
    if directory and not value.endswith("/"):
        raise ValueError("prefix path must end with a slash")
    if not directory and value.endswith("/"):
        raise ValueError("exact artifact path must not end with a slash")
    return value


def target_route(target_relative: str) -> str:
    if target_relative == "index.html":
        return TARGET_ROUTE_ROOT
    return TARGET_ROUTE_ROOT + target_relative


def require_exact_fields(value: Any, fields: Iterable[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} fields do not match the contract")
    return value


def route_contract(
    access_policy: Dict[str, Any],
    target_relative: str,
    required_scopes: Sequence[str],
) -> Dict[str, Any]:
    route = match_route(access_policy, target_route(target_relative))
    if route is None:
        raise ValueError(f"target is not covered by the registered restricted routes: {target_relative}")
    if tuple(required_scopes) != tuple(route["required_scopes"]):
        raise ValueError(f"target scopes do not match the registered route: {target_relative}")
    return route


def validate_manifest(
    manifest: Dict[str, Any],
    access_policy: Dict[str, Any],
) -> Dict[str, Any]:
    validate_access_policy(access_policy)
    if not isinstance(manifest, dict) or set(manifest) != TOP_LEVEL_FIELDS:
        raise ValueError("migration manifest fields do not match the contract")
    fixed = {
        "contract": CONTRACT,
        "status": "design_only",
        "source_public_root": SOURCE_ROOT,
        "source_route_root": SOURCE_ROUTE_ROOT,
        "target_release_root": TARGET_RELEASE_ROOT,
        "target_route_root": TARGET_ROUTE_ROOT,
        "hash_algorithm": "sha256",
        "unknown_artifact_action": "preserve_review",
        "duplicate_target_action": "block",
        "missing_known_action": "report",
        "source_mutation_allowed": False,
    }
    for key, expected in fixed.items():
        if manifest.get(key) != expected:
            raise ValueError(f"{key} does not match the accepted migration boundary")
    activation_keys = ("enabled", "staging_authorized", "cutover_authorized", "deletion_authorized")
    if any(not isinstance(manifest.get(key), bool) for key in activation_keys):
        raise ValueError("migration activation flags must be boolean")

    evidence_expected = {
        "operations_center_source": "src/web/operations-center/index.html",
        "operations_center_publish_script": "deploy/operations-center/publish.sh",
        "operations_center_documentation": "docs/operations-center/README.md",
        "inventory_scope": "repository_declared_only",
        "fresh_live_inventory_required": True,
    }
    evidence = require_exact_fields(manifest["repository_evidence"], evidence_expected, "repository_evidence")
    if evidence != evidence_expected:
        raise ValueError("repository evidence contract does not match")

    exact = manifest["known_exact_artifacts"]
    prefixes = manifest["known_prefix_groups"]
    if not isinstance(exact, list) or not exact:
        raise ValueError("known exact artifact list is empty")
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError("known prefix group list is empty")

    source_seen: set[str] = set()
    target_seen: set[str] = set()
    for index, raw in enumerate(exact):
        item = require_exact_fields(raw, EXACT_FIELDS, f"known_exact_artifacts[{index}]")
        source = safe_relative(item["source_relative"])
        target = safe_relative(item["target_relative"])
        if source in source_seen:
            raise ValueError(f"duplicate exact source: {source}")
        if target in target_seen:
            raise ValueError(f"duplicate exact target: {target}")
        source_seen.add(source)
        target_seen.add(target)
        if item["classification"] not in CLASSIFICATIONS:
            raise ValueError(f"unsupported classification: {item['classification']}")
        scopes = item["required_scopes"]
        if scopes != [GENERAL_SCOPE]:
            raise ValueError("repository-declared detailed artifacts require the general detail scope")
        repository_source = item["repository_source"]
        if repository_source is not None:
            safe_relative(repository_source)
        route_contract(access_policy, target, scopes)

    prefix_seen: set[str] = set()
    target_prefix_seen: set[str] = set()
    for index, raw in enumerate(prefixes):
        item = require_exact_fields(raw, PREFIX_FIELDS, f"known_prefix_groups[{index}]")
        source = safe_relative(item["source_prefix"], directory=True)
        target = safe_relative(item["target_prefix"], directory=True)
        if source in prefix_seen or target in target_prefix_seen:
            raise ValueError("duplicate prefix group")
        prefix_seen.add(source)
        target_prefix_seen.add(target)
        if item["classification"] not in CLASSIFICATIONS:
            raise ValueError("unsupported prefix classification")
        if item["required_scopes"] != [GENERAL_SCOPE]:
            raise ValueError("prefix group requires unsupported scopes")
        if item["live_enumeration_required"] is not True:
            raise ValueError("prefix groups require fresh live enumeration")
        route_contract(access_policy, target + "inventory-probe", item["required_scopes"])

    acceptance = require_exact_fields(manifest["acceptance"], ACCEPTANCE_FIELDS, "acceptance")
    required_true = (
        "fresh_live_route_inventory_required",
        "fresh_live_filesystem_inventory_required",
        "sha256_inventory_required",
        "source_backup_required",
        "target_release_validation_required",
        "authorized_route_matrix_required",
        "unauthorized_route_matrix_required",
        "unknown_artifacts_preserved",
        "duplicate_targets_blocked",
        "source_tree_unchanged",
    )
    for key in required_true:
        if acceptance.get(key) is not True:
            raise ValueError(f"acceptance.{key} must be true")
    required_false = (
        "public_cutover_performed",
        "detailed_artifacts_removed",
        "traffic_controls_changed",
        "live_change_authorized",
    )
    for key in required_false:
        if not isinstance(acceptance.get(key), bool):
            raise ValueError(f"acceptance.{key} must be boolean")

    flags = tuple(manifest[key] for key in activation_keys)
    if any(flags):
        if not manifest["enabled"] or not manifest["staging_authorized"]:
            raise ValueError("staging cannot be partially activated")
        if manifest["cutover_authorized"] and acceptance["live_change_authorized"] is not True:
            raise ValueError("cutover requires explicit live-change acceptance")
        if manifest["deletion_authorized"] and (
            not manifest["cutover_authorized"]
            or acceptance["public_cutover_performed"] is not True
            or acceptance["authorized_route_matrix_required"] is not True
            or acceptance["unauthorized_route_matrix_required"] is not True
        ):
            raise ValueError("deletion requires accepted cutover and route matrices")
    return manifest


def exact_map(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {item["source_relative"]: item for item in manifest["known_exact_artifacts"]}


def prefix_match(manifest: Dict[str, Any], source_relative: str) -> Optional[Tuple[Dict[str, Any], str]]:
    candidates = sorted(manifest["known_prefix_groups"], key=lambda item: len(item["source_prefix"]), reverse=True)
    for group in candidates:
        if source_relative.startswith(group["source_prefix"]):
            suffix = source_relative[len(group["source_prefix"]):]
            if suffix:
                return group, suffix
    return None


def covers_relative(manifest: Dict[str, Any], source_relative: str) -> bool:
    if source_relative in exact_map(manifest):
        return True
    return prefix_match(manifest, source_relative) is not None


def normalize_inventory_item(item: Any) -> Dict[str, Any]:
    fields = {"path", "sha256", "mode", "bytes"}
    value = require_exact_fields(item, fields, "inventory item")
    path = value["path"]
    if not isinstance(path, str) or not path.startswith(SOURCE_ROOT + "/"):
        raise ValueError("inventory path is outside the source public root")
    relative = safe_relative(path[len(SOURCE_ROOT) + 1:])
    digest = value["sha256"]
    mode = value["mode"]
    size = value["bytes"]
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise ValueError("inventory SHA-256 is invalid")
    if not isinstance(mode, str) or MODE_RE.fullmatch(mode) is None:
        raise ValueError("inventory mode is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError("inventory byte count is invalid")
    return {"source_relative": relative, "sha256": digest, "mode": mode, "bytes": size}


def reconcile_inventory(
    manifest: Dict[str, Any],
    access_policy: Dict[str, Any],
    inventory: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    validate_manifest(manifest, access_policy)
    if not isinstance(inventory, (list, tuple)):
        raise ValueError("inventory must be a sequence")
    known = exact_map(manifest)
    source_seen: set[str] = set()
    target_seen: set[str] = set()
    mapped: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []

    for raw in inventory:
        item = normalize_inventory_item(raw)
        source = item["source_relative"]
        if source in source_seen:
            raise ValueError(f"duplicate source inventory record: {source}")
        source_seen.add(source)
        definition = known.get(source)
        if definition is not None:
            target = definition["target_relative"]
            classification = definition["classification"]
            scopes = definition["required_scopes"]
            provenance = "exact"
        else:
            matched = prefix_match(manifest, source)
            if matched is None:
                unknown.append({
                    **item,
                    "action": "preserve_review",
                    "reason": "not_in_repository_declared_manifest",
                })
                continue
            group, suffix = matched
            target = group["target_prefix"] + suffix
            safe_relative(target)
            classification = group["classification"]
            scopes = group["required_scopes"]
            provenance = "prefix_live_enumeration"
        if target in target_seen:
            raise ValueError(f"duplicate target mapping blocked: {target}")
        target_seen.add(target)
        route = route_contract(access_policy, target, scopes)
        mapped.append({
            **item,
            "target_relative": target,
            "target_route": target_route(target),
            "classification": classification,
            "registered_route_classification": route["classification"],
            "required_scopes": list(scopes),
            "provenance": provenance,
            "action": "stage_candidate",
        })

    missing = sorted(set(known) - source_seen)
    acceptance = manifest["acceptance"]
    staging_ready = bool(
        manifest["enabled"]
        and manifest["staging_authorized"]
        and not missing
        and not unknown
    )
    cutover_ready = bool(
        staging_ready
        and manifest["cutover_authorized"]
        and acceptance["live_change_authorized"]
        and acceptance["public_cutover_performed"]
    )
    return {
        "contract": "wwcx.edge1-restricted-artifact-reconciliation.v1",
        "inventory_scope": "provided_read_only_inventory",
        "mapped": mapped,
        "unknown_preserved": unknown,
        "missing_known": missing,
        "counts": {
            "inventory": len(inventory),
            "mapped": len(mapped),
            "unknown_preserved": len(unknown),
            "missing_known": len(missing),
        },
        "source_mutation_allowed": False,
        "deletion_authorized": manifest["deletion_authorized"],
        "staging_ready": staging_ready,
        "cutover_ready": cutover_ready,
        "traffic_controls_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--access-policy", type=Path, default=DEFAULT_ACCESS_POLICY)
    args = parser.parse_args()
    manifest = load_object(args.manifest)
    access_policy = load_access_policy(args.access_policy)
    validate_manifest(manifest, access_policy)
    print(json.dumps({
        "ok": True,
        "state": manifest["status"],
        "enabled": manifest["enabled"],
        "staging_authorized": manifest["staging_authorized"],
        "cutover_authorized": manifest["cutover_authorized"],
        "deletion_authorized": manifest["deletion_authorized"],
        "known_exact_artifacts": len(manifest["known_exact_artifacts"]),
        "known_prefix_groups": len(manifest["known_prefix_groups"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
