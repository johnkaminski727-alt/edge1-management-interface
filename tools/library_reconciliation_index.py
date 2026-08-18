#!/usr/bin/env python3
"""Build a non-destructive reconciliation index for loose project artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_HINTS = (("bigbird", "Project Big Bird"), ("edge1", "Edge1"), ("ww.cx", "WW.CX"), ("wwcx", "WW.CX"))
EVIDENCE_HINTS = (
    (("screenshot", ".png", ".jpg", ".jpeg", ".webp"), "screenshot/image"),
    (("deploy", "install", "provision"), "deployment-helper"),
    (("handoff", "continuation"), "handoff"),
    (("log", "evidence", "validation"), "operational-evidence"),
    (("archive", ".zip", ".tar", ".tgz"), "archive/bundle"),
    (("script", ".sh", ".ps1", ".py"), "script/helper"),
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_project(path: Path) -> str:
    lowered = str(path).lower()
    for hint, project in PROJECT_HINTS:
        if hint in lowered:
            return project
    return "unclassified"


def classify_evidence(path: Path) -> str:
    lowered = path.name.lower()
    suffix = path.suffix.lower()
    for hints, label in EVIDENCE_HINTS:
        if any(hint in lowered or hint == suffix for hint in hints):
            return label
    return mimetypes.guess_type(path.name)[0] or "unknown"


def load_mapping(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mapping must be a JSON object keyed by SHA-256")
    return data


def record(path: Path, root: Path, mapping: dict[str, dict[str, Any]]) -> dict[str, Any]:
    digest = sha256(path)
    override = mapping.get(digest, {})
    stat = path.stat()
    canonical = override.get("canonical_retained_record")
    repository_representation = override.get("repository_representation")
    duplicate_of = override.get("duplicate_of")
    unique_value_reconciled = bool(override.get("unique_value_reconciled", False))
    deletion_eligibility = "review-required"
    unresolved_status = "unresolved"
    if duplicate_of and canonical and unique_value_reconciled:
        deletion_eligibility = "eligible-after-independent-verification"
        unresolved_status = "resolved-pending-disposition"
    return {
        "sha256": digest,
        "filename": path.name,
        "relative_path": str(path.relative_to(root)),
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "project": override.get("project", classify_project(path)),
        "evidence_type": override.get("evidence_type", classify_evidence(path)),
        "repository_representation": repository_representation,
        "canonical_retained_record": canonical,
        "duplicate_of": duplicate_of,
        "unique_value_reconciled": unique_value_reconciled,
        "deletion_eligibility": deletion_eligibility,
        "unresolved_status": unresolved_status,
    }


def scan(root: Path, mapping: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise ValueError("input root must be a directory")
    return [record(path, root, mapping) for path in sorted(root.rglob("*")) if path.is_file()]


def write_outputs(records: list[dict[str, Any]], output_json: Path, output_csv: Path | None) -> None:
    payload = {"schema": "wwcx-library-reconciliation-index-v1", "generated_utc": utcnow(), "destructive_actions_performed": False, "records": records}
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_csv:
        fields = list(records[0].keys()) if records else ["sha256", "filename", "relative_path", "size_bytes", "modified_utc", "project", "evidence_type", "repository_representation", "canonical_retained_record", "duplicate_of", "unique_value_reconciled", "deletion_eligibility", "unresolved_status"]
        with output_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash and classify loose project artifacts without deleting anything")
    parser.add_argument("root", type=Path)
    parser.add_argument("--mapping", type=Path, help="optional reviewed SHA-256 classification mapping")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    records = scan(args.root.resolve(), load_mapping(args.mapping))
    write_outputs(records, args.json, args.csv)
    print(json.dumps({"records": len(records), "json": str(args.json), "csv": str(args.csv) if args.csv else None, "deleted": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
