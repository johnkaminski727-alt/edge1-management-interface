#!/usr/bin/env python3
"""Normalize a restricted cPanel UAPI mail capture into provider-object JSON.

The tool is offline and read-only. It verifies the evidence manifest, refuses to
read from or write into a Git working tree, and writes the normalized inventory
next to other restricted evidence. It never contacts cPanel or changes mail.
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

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_HUB = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
EVIDENCE_CONTRACTS = {
    "wwcx.cpanel-http-mail-inventory-evidence.v1",
    "wwcx.cpanel-mail-inventory-evidence.v1",
}
OUTPUT_CONTRACT = "wwcx.provider-mail-objects.v1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class CaptureError(RuntimeError):
    """Raised when the capture cannot be normalized safely."""


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
        raise CaptureError(f"unable to read JSON evidence {path.name}: {exc}") from exc


def _uapi_data(path: pathlib.Path) -> Any:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise CaptureError(f"{path.name} must contain a JSON object")
    result = payload.get("result", payload)
    if not isinstance(result, dict):
        raise CaptureError(f"{path.name} has no UAPI result object")
    try:
        status = int(result.get("status", payload.get("status", 0)))
    except (TypeError, ValueError) as exc:
        raise CaptureError(f"{path.name} has an invalid UAPI status") from exc
    if status != 1:
        raise CaptureError(f"{path.name} does not report UAPI success")
    return result.get("data")


def _as_rows(data: Any, label: str) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise CaptureError(f"{label} data must be an object or list of objects")
    return data


def _normalize_domain(value: Any) -> str:
    domain = str(value or "").strip().casefold().rstrip(".")
    if not domain or "." not in domain or any(char.isspace() for char in domain):
        raise CaptureError(f"invalid domain in provider evidence: {value!r}")
    return domain


def _normalize_address(value: Any) -> str | None:
    address = str(value or "").strip().casefold()
    if EMAIL_RE.fullmatch(address):
        return address
    return None


def _field(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _flag(row: dict[str, Any], *names: str) -> bool:
    value = _field(row, *names)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "suspended"}


def _address_from_row(row: dict[str, Any]) -> str | None:
    for name in ("address", "email", "login"):
        address = _normalize_address(row.get(name))
        if address:
            return address
    local = str(_field(row, "user", "email", "login") or "").strip().casefold()
    domain_value = _field(row, "domain", "demain")
    if local and "@" not in local and domain_value:
        return _normalize_address(f"{local}@{_normalize_domain(domain_value)}")
    return None


def _split_destinations(value: Any) -> tuple[list[str], list[str]]:
    if value is None:
        return [], []
    values = value if isinstance(value, list) else re.split(r"\s*,\s*", str(value))
    addresses: list[str] = []
    unsupported: list[str] = []
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        address = _normalize_address(text)
        if address:
            addresses.append(address)
        else:
            unsupported.append(text)
    return sorted(set(addresses)), unsupported


def _manifest_entries(path: pathlib.Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise CaptureError(f"unable to read SHA256SUMS: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) != 2 or not HEX64_RE.fullmatch(parts[0]):
            raise CaptureError(f"invalid SHA256SUMS line {line_number}")
        filename = parts[1]
        if pathlib.PurePath(filename).name != filename or filename in entries:
            raise CaptureError(f"unsafe or duplicate manifest filename: {filename}")
        entries[filename] = parts[0]
    if "metadata.json" not in entries:
        raise CaptureError("SHA256SUMS does not include metadata.json")
    return entries


def _verify_manifest(evidence_dir: pathlib.Path) -> list[str]:
    entries = _manifest_entries(evidence_dir / "SHA256SUMS")
    for filename, expected in entries.items():
        path = evidence_dir / filename
        if not path.is_file():
            raise CaptureError(f"manifest file is missing: {filename}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise CaptureError(f"SHA-256 mismatch: {filename}")
    json_names = sorted(path.name for path in evidence_dir.glob("*.json"))
    unmanifested = sorted(set(json_names) - set(entries))
    if unmanifested:
        raise CaptureError(f"unmanifested JSON evidence: {', '.join(unmanifested)}")
    return sorted(entries)


def _access_map(hub_path: pathlib.Path) -> dict[str, str]:
    hub = _load_json(hub_path)
    try:
        routes = hub["routing"]["routes"]
    except (TypeError, KeyError) as exc:
        raise CaptureError("inbound hub does not contain routing.routes") from exc
    access: dict[str, str] = {}
    for address, route in routes.items():
        destination = str(route.get("destination", "")).casefold()
        if destination == "john-inbox@ww.cx":
            access[address.casefold()] = "private_john"
        elif destination == "maildesk@ww.cx":
            access[address.casefold()] = "shared_role"
        else:
            access[address.casefold()] = "unknown"
    return access


def _require_empty_behavior(evidence_dir: pathlib.Path, filename: str, label: str) -> None:
    rows = _as_rows(_uapi_data(evidence_dir / filename), filename)
    if rows:
        raise CaptureError(
            f"{label} are present in {filename}; manual restricted review is required"
        )


def _default_behavior(value: Any) -> tuple[str, str | None]:
    text = str(value or "").strip()
    folded = text.casefold()
    if folded.startswith(":fail:") or folded == "fail":
        return "reject", None
    if folded in {":blackhole:", "blackhole"}:
        return "blackhole", None
    address = _normalize_address(text)
    if address:
        return "forward", address
    if text.startswith("|") or text.startswith("/"):
        return "pipe", None
    return "unknown", None


def normalize_capture(
    evidence_dir: pathlib.Path,
    hub_path: pathlib.Path = DEFAULT_HUB,
    provider_id: str = "namecheap-business159",
) -> dict[str, Any]:
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir():
        raise CaptureError(f"evidence directory not found: {evidence_dir}")
    if _git_root(evidence_dir):
        raise CaptureError("refusing to normalize provider evidence inside a Git working tree")

    evidence_files = _verify_manifest(evidence_dir)
    metadata = _load_json(evidence_dir / "metadata.json")
    if not isinstance(metadata, dict):
        raise CaptureError("metadata.json must contain a JSON object")
    if metadata.get("contract") not in EVIDENCE_CONTRACTS:
        raise CaptureError("metadata.json uses an unsupported evidence contract")
    if metadata.get("read_only") is not True:
        raise CaptureError("metadata.json does not assert read_only=true")
    domains = [_normalize_domain(value) for value in metadata.get("domains", [])]
    if not domains or len(domains) != len(set(domains)):
        raise CaptureError("metadata.json must contain unique captured domains")
    captured_at = str(metadata.get("captured_at", "")).strip()
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureError("metadata.json captured_at is invalid") from exc

    safe_domains = {domain.replace(".", "_"): domain for domain in domains}
    required = {
        "list-mail-domains.json",
        "list-pops.json",
        "list-domain-forwarders.json",
        "list-filters.json",
        "metadata.json",
    }
    for safe in safe_domains:
        required.update(
            {
                f"list-forwarders-{safe}.json",
                f"list-default-address-{safe}.json",
                f"list-auto-responders-{safe}.json",
            }
        )
    missing = sorted(required - set(evidence_files))
    if missing:
        raise CaptureError(f"capture is incomplete; missing: {', '.join(missing)}")

    _require_empty_behavior(
        evidence_dir, "list-domain-forwarders.json", "domain-level forwarders"
    )
    _require_empty_behavior(evidence_dir, "list-filters.json", "account filters")
    for safe in safe_domains:
        _require_empty_behavior(
            evidence_dir,
            f"list-auto-responders-{safe}.json",
            f"autoresponders for {safe_domains[safe]}",
        )

    access = _access_map(hub_path)
    objects: list[dict[str, Any]] = []

    for row in _as_rows(_uapi_data(evidence_dir / "list-pops.json"), "list-pops.json"):
        address = _address_from_row(row)
        if not address or address.rsplit("@", 1)[1] not in domains:
            continue
        suspended_login = _flag(row, "suspended_login", "suspended")
        suspended_incoming = _flag(row, "suspended_incoming")
        objects.append(
            {
                "address": address,
                "domain": address.rsplit("@", 1)[1],
                "object_type": "mailbox",
                "destinations": [],
                "receives_mail": not suspended_incoming,
                "can_send": False,
                "active": not suspended_login,
                "access_class": access.get(address, "unknown"),
                "quota_bytes": None,
                "notes": (
                    "Mailbox observed through read-only cPanel UAPI. Outbound sender "
                    "authorization and quota units were not proven by this capture."
                ),
            }
        )

    for safe, domain in safe_domains.items():
        filename = f"list-forwarders-{safe}.json"
        for row in _as_rows(_uapi_data(evidence_dir / filename), filename):
            address = _address_from_row(row)
            if not address:
                local = str(_field(row, "email", "user") or "").strip().casefold()
                address = _normalize_address(f"{local}@{domain}") if local else None
            if not address or address.rsplit("@", 1)[1] != domain:
                raise CaptureError(f"unable to normalize a forwarder source in {filename}")
            destinations, unsupported = _split_destinations(
                _field(row, "dest", "forward", "destination", "forwarder")
            )
            note = "Forwarder observed through read-only cPanel UAPI."
            object_type = "forwarder"
            if unsupported:
                object_type = "unknown"
                note += " Non-email destination requires manual restricted review."
            objects.append(
                {
                    "address": address,
                    "domain": domain,
                    "object_type": object_type,
                    "destinations": destinations,
                    "receives_mail": True,
                    "can_send": False,
                    "active": True,
                    "access_class": access.get(address, "unknown"),
                    "quota_bytes": None,
                    "notes": note,
                }
            )

    default_addresses: list[dict[str, Any]] = []
    for safe, domain in safe_domains.items():
        filename = f"list-default-address-{safe}.json"
        rows = _as_rows(_uapi_data(evidence_dir / filename), filename)
        if not rows:
            raise CaptureError(f"{filename} returned no default-address record")
        if len(rows) != 1:
            raise CaptureError(f"{filename} returned multiple default-address records")
        row = rows[0]
        behavior, destination = _default_behavior(
            _field(row, "defaultaddress", "forward", "destination", "default_address")
        )
        default_addresses.append(
            {"domain": domain, "behavior": behavior, "destination": destination}
        )

    return {
        "contract": OUTPUT_CONTRACT,
        "provider_id": provider_id,
        "provider_family": "namecheap_shared_hosting",
        "captured_at": captured_at,
        "source": {
            "method": "cpanel_uapi",
            "read_only": True,
            "evidence_files": evidence_files + ["SHA256SUMS"],
            "account_reference": None,
        },
        "objects": sorted(
            objects, key=lambda item: (item["address"], item["object_type"], item["destinations"])
        ),
        "default_addresses": sorted(default_addresses, key=lambda item: item["domain"]),
        "domain_routing": [
            {"domain": domain, "mode": "unknown"} for domain in sorted(domains)
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--hub", type=pathlib.Path, default=DEFAULT_HUB)
    parser.add_argument("--provider-id", default="namecheap-business159")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        output = args.output.resolve()
        if _git_root(output):
            raise CaptureError("refusing to write normalized provider evidence into a Git working tree")
        inventory = normalize_capture(args.evidence_dir, args.hub, args.provider_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    except CaptureError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for item in inventory["objects"]:
        counts[item["object_type"]] = counts.get(item["object_type"], 0) + 1
    print("Normalized restricted cPanel inventory written successfully.")
    print(f"Captured domains: {len(inventory['domain_routing'])}")
    print(f"Mail objects: {len(inventory['objects'])}")
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    print(f"Default addresses: {len(inventory['default_addresses'])}")
    print("Domain routing remains unknown until separately verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
