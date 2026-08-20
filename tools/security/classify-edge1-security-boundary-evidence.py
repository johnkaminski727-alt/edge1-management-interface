#!/usr/bin/env python3
"""Classify the accepted Edge1 security-boundary inventory residuals read-only.

The tool opens only the already-collected protected inventory JSON plus the five
live filesystem objects needed to prove metadata/hash/path relationships. It
never writes files, changes permissions, invokes services, or follows arbitrary
symlinks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

DEFAULT_REPO_ROOT = Path("/opt/edge1-management-interface")
DEFAULT_STATUS_ROOT = Path("/var/www/edge1-status")
DEFAULT_EVIDENCE_ROOT = Path(
    "/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory"
)

REVIEWED_UNKNOWN_NAMES = {
    "bitcoin-mining-history.json",
    "mining-operations.json",
    "operations-changes.json",
    "operations-trends.json",
}
COMPATIBILITY_LINK_RELATIVE = "security-correlation.json"
COMPATIBILITY_TARGET_RELATIVE = "security/correlation/data/security-correlation.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(info: os.stat_result) -> str:
    return f"{stat.S_IMODE(info.st_mode):04o}"


def accepted_result(value: Any) -> bool:
    return isinstance(value, dict) and all(
        (
            value.get("contract")
            == "wwcx.edge1-security-boundary-live-inventory-result.v1",
            value.get("read_only_host_inventory") is True,
            value.get("live_configuration_changed") is False,
            value.get("source_tree_mutated") is False,
            value.get("credentials_collected") is False,
            value.get("cookie_values_recorded") is False,
            value.get("traffic_controls_changed") is False,
            value.get("inventory_records") == 164,
            value.get("mapped_records") == 160,
            value.get("unknown_preserved") == 4,
            value.get("missing_known") == 0,
            value.get("filesystem_anomalies") == 1,
            value.get("apache_config_test_passed") is True,
            value.get("staging_ready") is False,
            value.get("cutover_ready") is False,
        )
    )


def candidate_evidence_dirs(evidence_root: Path) -> list[Path]:
    matches: list[Path] = []
    for result_path in sorted(evidence_root.glob("*/result.json")):
        try:
            value = load_json(result_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if accepted_result(value):
            matches.append(result_path.parent)
    return matches


def exact_manifest_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    manifest = load_json(
        repo_root / "config/security/edge1-restricted-artifact-migration-manifest.json"
    )
    return {
        item["source_relative"]: item
        for item in manifest.get("known_exact_artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("source_relative"), str)
    }


def classify(
    *,
    repo_root: Path,
    status_root: Path,
    evidence_root: Path,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    if evidence_dir is None:
        candidates = candidate_evidence_dirs(evidence_root)
        if not candidates:
            raise ValueError("no protected evidence directory matches the accepted aggregate")
        selected = candidates[-1]
    else:
        selected = evidence_dir
        result = load_json(selected / "result.json")
        if not accepted_result(result):
            raise ValueError("explicit evidence directory does not match the accepted aggregate")
        candidates = candidate_evidence_dirs(evidence_root)

    required = (
        "result.json",
        "reconciliation.json",
        "public-filesystem-inventory.json",
        "public-filesystem-anomalies.json",
    )
    for name in required:
        if not (selected / name).is_file():
            raise ValueError(f"selected evidence is missing {name}")

    reconciliation = load_json(selected / "reconciliation.json")
    inventory = load_json(selected / "public-filesystem-inventory.json")
    anomalies = load_json(selected / "public-filesystem-anomalies.json")

    unknowns = reconciliation.get("unknown_preserved")
    if not isinstance(unknowns, list) or len(unknowns) != 4:
        raise ValueError("expected exactly four preserved unknown records")
    if not isinstance(anomalies, list) or len(anomalies) != 1:
        raise ValueError("expected exactly one filesystem anomaly")
    if not isinstance(inventory, list):
        raise ValueError("public filesystem inventory is not a list")

    unknown_map = {
        item.get("source_relative"): item
        for item in unknowns
        if isinstance(item, dict) and isinstance(item.get("source_relative"), str)
    }
    if set(unknown_map) != REVIEWED_UNKNOWN_NAMES:
        raise ValueError(
            "preserved unknown set does not match the reviewed four-artifact set"
        )

    manifest = exact_manifest_map(repo_root)
    classified_unknowns: list[dict[str, Any]] = []

    for name in sorted(REVIEWED_UNKNOWN_NAMES):
        record = unknown_map[name]
        if record.get("action") != "preserve_review":
            raise ValueError(f"{name}: unexpected historical evidence action")
        if record.get("reason") != "not_in_repository_declared_manifest":
            raise ValueError(f"{name}: unexpected historical evidence reason")

        live_path = status_root / name
        info = live_path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{name}: live object is not a regular file")

        live_mode = file_mode(info)
        live_hash = sha256(live_path)
        if live_mode != record.get("mode"):
            raise ValueError(f"{name}: live mode drift")
        if info.st_size != record.get("bytes"):
            raise ValueError(f"{name}: live byte-count drift")
        if live_hash != record.get("sha256"):
            raise ValueError(f"{name}: live SHA-256 drift")

        definition = manifest.get(name)
        if not isinstance(definition, dict):
            raise ValueError(f"{name}: current manifest lacks an exact classification")
        repository_source = definition.get("repository_source")
        if not isinstance(repository_source, str) or not repository_source:
            raise ValueError(f"{name}: current manifest lacks repository provenance")
        if not (repo_root / repository_source).is_file():
            raise ValueError(f"{name}: repository provenance source is missing")

        classified_unknowns.append(
            {
                "source_relative": name,
                "classification": definition.get("classification"),
                "target_relative": definition.get("target_relative"),
                "repository_source": repository_source,
                "mode": live_mode,
                "bytes": info.st_size,
                "sha256": live_hash,
                "live_matches_protected_inventory": True,
                "historical_action": "preserve_review",
                "current_manifest_mapping": "known_exact_artifact",
            }
        )

    anomaly = anomalies[0]
    if not isinstance(anomaly, dict):
        raise ValueError("filesystem anomaly record is not an object")

    expected_link = status_root / COMPATIBILITY_LINK_RELATIVE
    if anomaly.get("path") != str(expected_link):
        raise ValueError("filesystem anomaly path is not the reviewed compatibility link")
    if anomaly.get("type") != "symlink":
        raise ValueError("filesystem anomaly is not the reviewed symlink type")

    link_info = expected_link.lstat()
    if not stat.S_ISLNK(link_info.st_mode):
        raise ValueError("compatibility path is no longer a symlink")

    raw_target = os.readlink(expected_link)
    if raw_target != COMPATIBILITY_TARGET_RELATIVE:
        raise ValueError("compatibility symlink target drift")

    resolved = (expected_link.parent / raw_target).resolve(strict=True)
    root_resolved = status_root.resolve(strict=True)
    try:
        contained = os.path.commonpath([str(root_resolved), str(resolved)]) == str(
            root_resolved
        )
    except ValueError:
        contained = False
    if not contained:
        raise ValueError("compatibility symlink resolves outside the status root")

    target_info = resolved.lstat()
    if not stat.S_ISREG(target_info.st_mode):
        raise ValueError("compatibility symlink target is not a regular file")

    target_record = next(
        (
            item
            for item in inventory
            if isinstance(item, dict) and item.get("path") == str(resolved)
        ),
        None,
    )
    if target_record is None:
        raise ValueError("compatibility target lacks a protected inventory record")

    target_mode = file_mode(target_info)
    target_hash = sha256(resolved)
    if target_record.get("mode") != target_mode:
        raise ValueError("compatibility target mode differs from protected inventory")
    if target_record.get("bytes") != target_info.st_size:
        raise ValueError("compatibility target size differs from protected inventory")
    if target_record.get("sha256") != target_hash:
        raise ValueError("compatibility target SHA-256 differs from protected inventory")

    return {
        "contract": "wwcx.edge1-security-boundary-residual-classification.v1",
        "selected_evidence_dir": str(selected),
        "accepted_inventory_candidate_count": len(candidates),
        "classified_unknown_records": classified_unknowns,
        "classified_filesystem_anomaly": {
            "path": str(expected_link),
            "classification": "reviewed_compatibility_symlink",
            "raw_target": raw_target,
            "resolved_target": str(resolved),
            "contained_within_status_root": True,
            "target_mode": target_mode,
            "target_bytes": target_info.st_size,
            "target_sha256": target_hash,
            "target_matches_protected_inventory": True,
        },
        "classified_unknown_count": len(classified_unknowns),
        "classified_filesystem_anomaly_count": 1,
        "file_contents_printed": False,
        "live_files_mutated": False,
        "service_state_changed": False,
        "traffic_controls_changed": False,
        "staging_authorized": False,
        "cutover_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--status-root", type=Path, default=DEFAULT_STATUS_ROOT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    try:
        result = classify(
            repo_root=args.repo_root,
            status_root=args.status_root,
            evidence_root=args.evidence_root,
            evidence_dir=args.evidence_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("EDGE1_SECURITY_FIVE_RECORDS=FAIL", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"selected_evidence_dir={result['selected_evidence_dir']}")
    print(f"classified_unknown_records={result['classified_unknown_count']}")
    print(
        "classified_filesystem_anomalies="
        f"{result['classified_filesystem_anomaly_count']}"
    )
    print("file_contents_printed=false")
    print("live_files_mutated=false")
    print("EDGE1_SECURITY_FIVE_RECORDS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
