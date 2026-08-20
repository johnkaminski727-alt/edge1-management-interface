#!/usr/bin/env python3
"""Classify accepted Edge1 security-boundary residuals read-only and fail-closed.

The historical protected inventory establishes which residual paths were preserved.
Classification then applies a path-specific current rule:

* repository_static: live content must exactly match the reviewed repository source;
* generated_json: live content must be a safe regular file containing valid JSON;
* preserved_unresolved: the exact reviewed path may remain preserved without invented
  repository provenance, but must remain a safe regular file;
* reviewed_compatibility_symlink: the exact link and contained target are validated.

Dynamic/generated artifacts are deliberately not compared with historical size/hash
snapshots. The tool never mutates files, invokes services, or executes commands.
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

REVIEWED_RESIDUAL_RULES = {
    "network-sensor/data/network-sensor.json": {"classification": "generated_json"},
    "network-sensor/index.html": {
        "classification": "repository_static",
        "repository_source": "src/web/network-sensor/index.html",
    },
    "operations-center/snmp.html": {"classification": "preserved_unresolved"},
    "snmp/operations-snmp.json": {"classification": "generated_json"},
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
            value.get("contract") == "wwcx.edge1-security-boundary-live-inventory-result.v1",
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


def _is_contained(root: Path, path: Path) -> bool:
    root_resolved = root.resolve(strict=True)
    path_resolved = path.resolve(strict=True)
    try:
        return os.path.commonpath([str(root_resolved), str(path_resolved)]) == str(root_resolved)
    except ValueError:
        return False


def _safe_regular(root: Path, path: Path, label: str) -> os.stat_result:
    if not _is_contained(root, path):
        raise ValueError(f"{label}: path escapes reviewed root")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label}: live object is not a regular file")
    if stat.S_IMODE(info.st_mode) & 0o002:
        raise ValueError(f"{label}: live object is world-writable")
    return info


def _historical_unknown_map(reconciliation: Any) -> dict[str, dict[str, Any]]:
    unknowns = reconciliation.get("unknown_preserved") if isinstance(reconciliation, dict) else None
    if not isinstance(unknowns, list) or len(unknowns) != 4:
        raise ValueError("expected exactly four preserved unknown records")
    unknown_map = {
        item.get("source_relative"): item
        for item in unknowns
        if isinstance(item, dict) and isinstance(item.get("source_relative"), str)
    }
    if set(unknown_map) != set(REVIEWED_RESIDUAL_RULES):
        raise ValueError("preserved unknown set does not match the reviewed four-artifact set")
    for name, record in unknown_map.items():
        if record.get("action") != "preserve_review":
            raise ValueError(f"{name}: unexpected historical evidence action")
        if record.get("reason") != "not_in_repository_declared_manifest":
            raise ValueError(f"{name}: unexpected historical evidence reason")
    return unknown_map


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
        if not _is_contained(evidence_root, selected):
            raise ValueError("explicit evidence directory escapes protected evidence root")
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
        path = selected / name
        if not path.is_file() or not _is_contained(selected, path):
            raise ValueError(f"selected evidence is missing or escapes root: {name}")

    reconciliation = load_json(selected / "reconciliation.json")
    inventory = load_json(selected / "public-filesystem-inventory.json")
    anomalies = load_json(selected / "public-filesystem-anomalies.json")
    _historical_unknown_map(reconciliation)
    if not isinstance(inventory, list):
        raise ValueError("public filesystem inventory is not a list")
    if not isinstance(anomalies, list) or len(anomalies) != 1:
        raise ValueError("expected exactly one filesystem anomaly")

    classified: list[dict[str, Any]] = []
    for relative, rule in REVIEWED_RESIDUAL_RULES.items():
        live_path = status_root / relative
        info = _safe_regular(status_root, live_path, relative)
        kind = rule["classification"]
        item: dict[str, Any] = {
            "source_relative": relative,
            "classification": kind,
            "mode": file_mode(info),
            "bytes": info.st_size,
            "sha256": sha256(live_path),
            "historical_action": "preserve_review",
        }

        if kind == "repository_static":
            repository_source = rule["repository_source"]
            source_path = repo_root / repository_source
            _safe_regular(repo_root, source_path, f"{relative} repository source")
            source_hash = sha256(source_path)
            if item["sha256"] != source_hash or info.st_size != source_path.stat().st_size:
                raise ValueError(f"{relative}: live content does not match repository source")
            item.update(
                {
                    "repository_source": repository_source,
                    "repository_source_sha256": source_hash,
                    "live_matches_repository_source": True,
                }
            )
        elif kind == "generated_json":
            value = load_json(live_path)
            if not isinstance(value, (dict, list)):
                raise ValueError(f"{relative}: generated JSON root is not an object or array")
            item.update({"json_valid": True, "historical_size_hash_enforced": False})
        elif kind == "preserved_unresolved":
            item.update(
                {
                    "repository_provenance": "unresolved_preserved",
                    "historical_size_hash_enforced": False,
                    "overwrite_authorized": False,
                }
            )
        else:
            raise ValueError(f"{relative}: unsupported classification rule")
        classified.append(item)

    anomaly = anomalies[0]
    if not isinstance(anomaly, dict):
        raise ValueError("filesystem anomaly record is not an object")
    expected_link = status_root / COMPATIBILITY_LINK_RELATIVE
    if anomaly.get("path") != str(expected_link) or anomaly.get("type") != "symlink":
        raise ValueError("filesystem anomaly is not the reviewed compatibility symlink")
    link_info = expected_link.lstat()
    if not stat.S_ISLNK(link_info.st_mode):
        raise ValueError("compatibility path is no longer a symlink")
    raw_target = os.readlink(expected_link)
    if raw_target != COMPATIBILITY_TARGET_RELATIVE:
        raise ValueError("compatibility symlink target drift")

    resolved = (expected_link.parent / raw_target).resolve(strict=True)
    if not _is_contained(status_root, resolved):
        raise ValueError("compatibility symlink resolves outside the status root")
    target_info = _safe_regular(status_root, resolved, "compatibility symlink target")
    target_json = load_json(resolved)
    if not isinstance(target_json, (dict, list)):
        raise ValueError("compatibility symlink target JSON root is not an object or array")

    return {
        "contract": "wwcx.edge1-security-boundary-residual-classification.v2",
        "selected_evidence_dir": str(selected),
        "accepted_inventory_candidate_count": len(candidates),
        "classified_unknown_records": classified,
        "classified_filesystem_anomaly": {
            "path": str(expected_link),
            "classification": "reviewed_compatibility_symlink",
            "raw_target": raw_target,
            "resolved_target": str(resolved),
            "contained_within_status_root": True,
            "target_mode": file_mode(target_info),
            "target_bytes": target_info.st_size,
            "target_sha256": sha256(resolved),
            "target_json_valid": True,
            "historical_size_hash_enforced": False,
        },
        "classified_unknown_count": len(classified),
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
    print(f"classified_filesystem_anomalies={result['classified_filesystem_anomaly_count']}")
    print("file_contents_printed=false")
    print("live_files_mutated=false")
    print("EDGE1_SECURITY_FIVE_RECORDS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
