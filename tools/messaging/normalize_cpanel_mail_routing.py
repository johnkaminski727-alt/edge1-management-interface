#!/usr/bin/env python3
"""Normalize restricted cPanel API 2 getmxcheck evidence.

The tool is offline and read-only. It verifies SHA-256 evidence before parsing,
refuses Git working-tree evidence and output paths, and emits a routing-only
``wwcx.provider-mail-objects.v1`` inventory for combined reconciliation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime
from typing import Any

OUTPUT_CONTRACT = "wwcx.provider-mail-objects.v1"
EVIDENCE_CONTRACT = "wwcx.cpanel-mail-routing-evidence.v1"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
DOMAIN_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
MODE_MAP = {
    "auto": "automatic",
    "local": "local",
    "remote": "remote",
    "secondary": "unknown",
}


class RoutingEvidenceError(RuntimeError):
    """Raised when routing evidence cannot be normalized safely."""


def _git_root(path: pathlib.Path) -> pathlib.Path | None:
    current = path.resolve()
    if not current.exists():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutingEvidenceError(f"unable to read JSON evidence {path.name}: {exc}") from exc


def _normalize_domain(value: Any, label: str) -> str:
    domain = str(value or "").strip().casefold().rstrip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise RoutingEvidenceError(f"{label} is not a normalized domain")
    return domain


def _manifest_entries(path: pathlib.Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise RoutingEvidenceError(f"unable to read SHA256SUMS: {exc}") from exc

    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) != 2 or not HEX64_RE.fullmatch(parts[0]):
            raise RoutingEvidenceError(f"invalid SHA256SUMS line {line_number}")
        filename = parts[1]
        if pathlib.PurePath(filename).name != filename or filename in entries:
            raise RoutingEvidenceError(f"unsafe or duplicate manifest filename: {filename}")
        entries[filename] = parts[0]

    if "metadata.json" not in entries:
        raise RoutingEvidenceError("SHA256SUMS does not include metadata.json")
    return entries


def _verify_manifest(evidence_dir: pathlib.Path) -> list[str]:
    entries = _manifest_entries(evidence_dir / "SHA256SUMS")
    for filename, expected in entries.items():
        path = evidence_dir / filename
        if not path.is_file():
            raise RoutingEvidenceError(f"manifest file is missing: {filename}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RoutingEvidenceError(f"SHA-256 mismatch: {filename}")

    json_names = sorted(path.name for path in evidence_dir.glob("*.json"))
    unmanifested = sorted(set(json_names) - set(entries))
    if unmanifested:
        raise RoutingEvidenceError(
            f"unmanifested JSON evidence: {', '.join(unmanifested)}"
        )
    return sorted(entries)


def _api2_row(path: pathlib.Path, expected_domain: str) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise RoutingEvidenceError(f"{path.name} must contain a JSON object")

    result = payload.get("cpanelresult")
    if not isinstance(result, dict):
        raise RoutingEvidenceError(f"{path.name} has no cpanelresult object")

    event = result.get("event")
    if not isinstance(event, dict):
        raise RoutingEvidenceError(f"{path.name} has no API event object")

    try:
        success = int(event.get("result", 0))
    except (TypeError, ValueError) as exc:
        raise RoutingEvidenceError(f"{path.name} has an invalid event result") from exc
    if success != 1:
        raise RoutingEvidenceError(f"{path.name} does not report API success")

    rows = result.get("data")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RoutingEvidenceError(f"{path.name} must contain exactly one data row")

    row = rows[0]
    domain = _normalize_domain(row.get("domain"), f"{path.name} domain")
    if domain != expected_domain:
        raise RoutingEvidenceError(
            f"{path.name} returned {domain} while {expected_domain} was expected"
        )

    raw_mode = str(row.get("mxcheck", "")).strip().casefold()
    if raw_mode not in MODE_MAP:
        raise RoutingEvidenceError(f"{path.name} returned unsupported mode {raw_mode!r}")

    return {
        "domain": domain,
        "mode": MODE_MAP[raw_mode],
        "raw_mode": raw_mode,
    }


def normalize_routing_capture(
    evidence_dir: pathlib.Path,
    provider_id: str = "namecheap-business159-routing",
) -> dict[str, Any]:
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir():
        raise RoutingEvidenceError(f"evidence directory not found: {evidence_dir}")
    if _git_root(evidence_dir):
        raise RoutingEvidenceError(
            "refusing to normalize provider routing evidence inside a Git working tree"
        )

    evidence_files = _verify_manifest(evidence_dir)
    metadata = _load_json(evidence_dir / "metadata.json")
    if not isinstance(metadata, dict):
        raise RoutingEvidenceError("metadata.json must contain a JSON object")
    if metadata.get("contract") != EVIDENCE_CONTRACT:
        raise RoutingEvidenceError("metadata.json uses an unsupported evidence contract")
    if metadata.get("read_only") is not True:
        raise RoutingEvidenceError("metadata.json does not assert read_only=true")
    if metadata.get("function") != "Email::getmxcheck":
        raise RoutingEvidenceError("metadata.json does not identify Email::getmxcheck")

    domains = [
        _normalize_domain(value, "metadata domain")
        for value in metadata.get("domains", [])
    ]
    if not domains or len(domains) != len(set(domains)):
        raise RoutingEvidenceError("metadata.json must contain unique captured domains")

    captured_at = str(metadata.get("captured_at", "")).strip()
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RoutingEvidenceError("metadata.json captured_at is invalid") from exc

    required = {"metadata.json"}
    for domain in domains:
        required.add(f"getmxcheck-{domain.replace('.', '_')}.json")
    missing = sorted(required - set(evidence_files))
    if missing:
        raise RoutingEvidenceError(
            f"routing capture is incomplete; missing: {', '.join(missing)}"
        )

    domain_routing: list[dict[str, str]] = []
    for domain in sorted(domains):
        filename = f"getmxcheck-{domain.replace('.', '_')}.json"
        row = _api2_row(evidence_dir / filename, domain)
        domain_routing.append({"domain": domain, "mode": row["mode"]})

    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", provider_id):
        raise RoutingEvidenceError("provider_id is invalid")

    return {
        "contract": OUTPUT_CONTRACT,
        "provider_id": provider_id,
        "provider_family": "namecheap_shared_hosting",
        "captured_at": captured_at,
        "source": {
            "method": "provider_api",
            "read_only": True,
            "evidence_files": evidence_files + ["SHA256SUMS"],
            "account_reference": None,
        },
        "objects": [],
        "default_addresses": [],
        "domain_routing": domain_routing,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--provider-id", default="namecheap-business159-routing")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output = args.output.resolve()
        if _git_root(output):
            raise RoutingEvidenceError(
                "refusing to write normalized routing evidence into a Git working tree"
            )
        inventory = normalize_routing_capture(args.evidence_dir, args.provider_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    except RoutingEvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
