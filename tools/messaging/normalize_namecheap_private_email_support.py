#!/usr/bin/env python3
"""Normalize a restricted Namecheap Private Email support evidence bundle.

The tool is offline and read-only. It verifies SHA-256 evidence before parsing,
rejects secret-bearing fields, derives access classes from canonical repository
configuration, and emits a conservative provider-object inventory plus a
restricted completeness summary. It never contacts Namecheap or changes mail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import date, datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_HUB = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
DEFAULT_IDENTITIES = ROOT / "config" / "messaging" / "mail-identities.json"

EVIDENCE_CONTRACT = "wwcx.namecheap-private-email-support-evidence.v1"
OUTPUT_CONTRACT = "wwcx.provider-mail-objects.v1"
SUMMARY_CONTRACT = "wwcx.namecheap-private-email-support-summary.v1"
PROVIDER_FAMILY = "namecheap_private_email"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TICKET_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,63}$")
OBJECT_TYPES = {
    "mailbox",
    "alias",
    "forwarder",
    "distribution_list",
    "system_account",
    "unknown",
}
CATCH_ALL_BEHAVIORS = {"reject", "forward", "blackhole", "unknown"}
SUBSCRIPTION_STATUSES = {"active", "inactive", "suspended", "expired", "unknown"}
DKIM_STATUSES = {"enabled", "disabled", "unverified", "unknown"}
COMPLETENESS_FIELDS = {
    "subscription",
    "mailboxes",
    "aliases_and_groups",
    "catch_all",
    "quotas",
    "forwarding",
    "dkim",
    "sender_capability",
    "filters_and_rules",
}
FORBIDDEN_KEY_FRAGMENTS = {
    "password",
    "passwd",
    "passphrase",
    "support_pin",
    "supportpin",
    "api_token",
    "apitoken",
    "access_token",
    "refresh_token",
    "bearer",
    "authorization",
    "cookie",
    "session_id",
    "sessionid",
    "cpsess",
    "reset_link",
    "reset_url",
    "private_key",
    "secret",
}


class SupportEvidenceError(RuntimeError):
    """Raised when support evidence cannot be normalized safely."""


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
        raise SupportEvidenceError(f"unable to read JSON evidence {path.name}: {exc}") from exc


def _normalize_domain(value: Any, label: str) -> str:
    domain = str(value or "").strip().casefold().rstrip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise SupportEvidenceError(f"{label} is not a normalized domain")
    return domain


def _normalize_address(value: Any, label: str) -> str:
    address = str(value or "").strip().casefold()
    if not EMAIL_RE.fullmatch(address):
        raise SupportEvidenceError(f"{label} is not a valid email address")
    return address


def _optional_text(value: Any, label: str, max_length: int = 1000) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SupportEvidenceError(f"{label} must be text or null")
    text = value.strip()
    if not text:
        return None
    if len(text) > max_length:
        raise SupportEvidenceError(f"{label} is too long")
    return text


def _nullable_bool(value: Any, label: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise SupportEvidenceError(f"{label} must be boolean or null")


def _reject_secret_keys(value: Any, path: str = "evidence") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            if any(fragment in normalized for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise SupportEvidenceError(
                    f"secret-bearing field is prohibited at {path}.{key}"
                )
            _reject_secret_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_keys(nested, f"{path}[{index}]")


def _manifest_entries(path: pathlib.Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise SupportEvidenceError(f"unable to read SHA256SUMS: {exc}") from exc

    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) != 2 or not HEX64_RE.fullmatch(parts[0]):
            raise SupportEvidenceError(f"invalid SHA256SUMS line {line_number}")
        filename = parts[1]
        if pathlib.PurePath(filename).name != filename or filename in entries:
            raise SupportEvidenceError(f"unsafe or duplicate manifest filename: {filename}")
        entries[filename] = parts[0]

    if "support-evidence.json" not in entries:
        raise SupportEvidenceError("SHA256SUMS does not include support-evidence.json")
    return entries


def _verify_manifest(evidence_dir: pathlib.Path) -> list[str]:
    entries = _manifest_entries(evidence_dir / "SHA256SUMS")
    for filename, expected in entries.items():
        path = evidence_dir / filename
        if not path.is_file():
            raise SupportEvidenceError(f"manifest file is missing: {filename}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SupportEvidenceError(f"SHA-256 mismatch: {filename}")

    unmanifested = sorted(
        path.name
        for path in evidence_dir.iterdir()
        if path.is_file() and path.name != "SHA256SUMS" and path.name not in entries
    )
    if unmanifested:
        raise SupportEvidenceError(
            f"unmanifested support evidence: {', '.join(unmanifested)}"
        )
    return sorted(entries)


def _canonical_access_map(
    hub_path: pathlib.Path,
    identities_path: pathlib.Path,
) -> dict[str, str]:
    hub = _load_json(hub_path)
    identities = _load_json(identities_path)

    try:
        routes = hub["routing"]["routes"]
        private_address = identities["mailboxes"]["private_john"]["address"]
        shared_address = identities["mailboxes"]["shared_role"]["address"]
        system_address = identities["system_senders"]["noreply"]["address"]
    except (KeyError, TypeError) as exc:
        raise SupportEvidenceError("canonical mail configuration is incomplete") from exc

    private_address = _normalize_address(private_address, "private mailbox")
    shared_address = _normalize_address(shared_address, "shared mailbox")
    system_address = _normalize_address(system_address, "system sender")

    access = {
        private_address: "private_john",
        shared_address: "shared_role",
        system_address: "system",
    }
    for address, route in routes.items():
        normalized = _normalize_address(address, "route address")
        destination = _normalize_address(route.get("destination"), f"destination for {address}")
        if destination == private_address:
            access[normalized] = "private_john"
        elif destination == shared_address:
            access[normalized] = "shared_role"
        else:
            access[normalized] = "unknown"
    return access


def _validate_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        missing = sorted(expected - set(value)) if isinstance(value, dict) else sorted(expected)
        unexpected = sorted(set(value) - expected) if isinstance(value, dict) else []
        raise SupportEvidenceError(
            f"{label} keys invalid; missing={missing}, unexpected={unexpected}"
        )
    return value


def normalize_support_capture(
    evidence_dir: pathlib.Path,
    hub_path: pathlib.Path = DEFAULT_HUB,
    identities_path: pathlib.Path = DEFAULT_IDENTITIES,
    provider_id: str = "namecheap-private-email-ww-cx",
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir():
        raise SupportEvidenceError(f"evidence directory not found: {evidence_dir}")
    if _git_root(evidence_dir):
        raise SupportEvidenceError(
            "refusing to normalize Private Email support evidence inside a Git working tree"
        )
    if not PROVIDER_ID_RE.fullmatch(provider_id):
        raise SupportEvidenceError("provider_id is invalid")

    evidence_files = _verify_manifest(evidence_dir)
    evidence = _load_json(evidence_dir / "support-evidence.json")
    if not isinstance(evidence, dict):
        raise SupportEvidenceError("support-evidence.json must contain a JSON object")
    _reject_secret_keys(evidence)

    expected_top = {
        "contract",
        "captured_at",
        "read_only",
        "provider_family",
        "domain",
        "ticket_reference",
        "subscription",
        "objects",
        "catch_all",
        "dkim",
        "provider_rules",
        "completeness",
    }
    _validate_exact_keys(evidence, expected_top, "support evidence")

    if evidence["contract"] != EVIDENCE_CONTRACT:
        raise SupportEvidenceError("support evidence uses an unsupported contract")
    if evidence["read_only"] is not True:
        raise SupportEvidenceError("support evidence does not assert read_only=true")
    if evidence["provider_family"] != PROVIDER_FAMILY:
        raise SupportEvidenceError("support evidence provider_family is unsupported")

    captured_at = str(evidence["captured_at"]).strip()
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SupportEvidenceError("captured_at is invalid") from exc

    domain = _normalize_domain(evidence["domain"], "support evidence domain")
    ticket_reference = str(evidence["ticket_reference"]).strip().upper()
    if not TICKET_RE.fullmatch(ticket_reference):
        raise SupportEvidenceError("ticket_reference is invalid")

    subscription = _validate_exact_keys(
        evidence["subscription"],
        {"status", "plan", "expiry_date", "mailbox_slots"},
        "subscription",
    )
    status = str(subscription["status"]).strip().casefold()
    if status not in SUBSCRIPTION_STATUSES:
        raise SupportEvidenceError("subscription.status is unsupported")
    plan = _optional_text(subscription["plan"], "subscription.plan", 256)
    expiry_date = _optional_text(
        subscription["expiry_date"], "subscription.expiry_date", 32
    )
    if expiry_date is not None:
        try:
            date.fromisoformat(expiry_date)
        except ValueError as exc:
            raise SupportEvidenceError(
                "subscription.expiry_date must use YYYY-MM-DD"
            ) from exc
    mailbox_slots = subscription["mailbox_slots"]
    if mailbox_slots is not None and (
        not isinstance(mailbox_slots, int) or isinstance(mailbox_slots, bool) or mailbox_slots < 0
    ):
        raise SupportEvidenceError(
            "subscription.mailbox_slots must be null or a non-negative integer"
        )

    access_map = _canonical_access_map(hub_path, identities_path)
    warnings: list[str] = []
    normalized_objects: list[dict[str, Any]] = []
    seen_object_keys: set[tuple[str, str, tuple[str, ...]]] = set()

    if not isinstance(evidence["objects"], list):
        raise SupportEvidenceError("objects must be a list")
    for index, raw in enumerate(evidence["objects"]):
        label = f"objects[{index}]"
        item = _validate_exact_keys(
            raw,
            {
                "address",
                "object_type",
                "destinations",
                "active",
                "receives_mail",
                "can_send",
                "quota_bytes",
                "notes",
            },
            label,
        )
        address = _normalize_address(item["address"], f"{label}.address")
        if address.rsplit("@", 1)[1] != domain:
            raise SupportEvidenceError(f"{label}.address is outside {domain}")
        object_type = str(item["object_type"]).strip().casefold()
        if object_type not in OBJECT_TYPES:
            raise SupportEvidenceError(f"{label}.object_type is unsupported")
        if not isinstance(item["destinations"], list):
            raise SupportEvidenceError(f"{label}.destinations must be a list")
        destinations = sorted(
            {
                _normalize_address(value, f"{label}.destinations")
                for value in item["destinations"]
            }
        )
        if object_type in {"alias", "forwarder"} and not destinations:
            warnings.append(f"{address}: forwarding object has no proven destination")
        if object_type not in {"alias", "forwarder"} and destinations:
            warnings.append(f"{address}: non-forwarding object has provider destinations")

        active_raw = _nullable_bool(item["active"], f"{label}.active")
        receives_raw = _nullable_bool(
            item["receives_mail"], f"{label}.receives_mail"
        )
        can_send_raw = _nullable_bool(item["can_send"], f"{label}.can_send")
        active = active_raw is True
        receives_mail = receives_raw is True
        can_send = can_send_raw is True
        if active_raw is None:
            warnings.append(f"{address}: active state was not proven")
        if receives_raw is None:
            warnings.append(f"{address}: receive capability was not proven")
        if can_send_raw is None:
            warnings.append(f"{address}: sender capability was not proven")

        quota_bytes = item["quota_bytes"]
        if quota_bytes is not None and (
            not isinstance(quota_bytes, int)
            or isinstance(quota_bytes, bool)
            or quota_bytes < 0
        ):
            raise SupportEvidenceError(
                f"{label}.quota_bytes must be null or a non-negative integer"
            )
        notes = _optional_text(item["notes"], f"{label}.notes") or ""
        if any(value is None for value in (active_raw, receives_raw, can_send_raw)):
            conservative_note = (
                "Unproven boolean capabilities were normalized to false and remain "
                "blocked pending explicit provider evidence."
            )
            notes = f"{notes} {conservative_note}".strip()

        object_key = (address, object_type, tuple(destinations))
        if object_key in seen_object_keys:
            raise SupportEvidenceError(f"duplicate provider object: {address}")
        seen_object_keys.add(object_key)
        normalized_objects.append(
            {
                "address": address,
                "domain": domain,
                "object_type": object_type,
                "destinations": destinations,
                "receives_mail": receives_mail,
                "can_send": can_send,
                "active": active,
                "access_class": access_map.get(address, "unknown"),
                "quota_bytes": quota_bytes,
                "notes": notes,
            }
        )

    catch_all = _validate_exact_keys(
        evidence["catch_all"],
        {"behavior", "destination"},
        "catch_all",
    )
    behavior = str(catch_all["behavior"]).strip().casefold()
    if behavior not in CATCH_ALL_BEHAVIORS:
        raise SupportEvidenceError("catch_all.behavior is unsupported")
    destination = catch_all["destination"]
    if destination is not None:
        destination = _normalize_address(destination, "catch_all.destination")
    if behavior == "forward" and destination is None:
        raise SupportEvidenceError("catch_all forward behavior requires a destination")
    if behavior != "forward" and destination is not None:
        raise SupportEvidenceError(
            "catch_all destination is permitted only for forward behavior"
        )

    dkim = _validate_exact_keys(
        evidence["dkim"],
        {"status", "selector"},
        "dkim",
    )
    dkim_status = str(dkim["status"]).strip().casefold()
    if dkim_status not in DKIM_STATUSES:
        raise SupportEvidenceError("dkim.status is unsupported")
    dkim_selector = _optional_text(dkim["selector"], "dkim.selector", 128)
    if dkim_selector is not None and not re.fullmatch(r"[A-Za-z0-9._-]+", dkim_selector):
        raise SupportEvidenceError("dkim.selector is invalid")

    provider_rules = _validate_exact_keys(
        evidence["provider_rules"],
        {"forwarding_reviewed", "filters_reviewed", "rules_present", "notes"},
        "provider_rules",
    )
    forwarding_reviewed = _nullable_bool(
        provider_rules["forwarding_reviewed"],
        "provider_rules.forwarding_reviewed",
    )
    filters_reviewed = _nullable_bool(
        provider_rules["filters_reviewed"],
        "provider_rules.filters_reviewed",
    )
    rules_present = _nullable_bool(
        provider_rules["rules_present"],
        "provider_rules.rules_present",
    )
    rules_notes = _optional_text(provider_rules["notes"], "provider_rules.notes")
    if rules_present is True:
        warnings.append("provider-side rules are present and require restricted review")
    if forwarding_reviewed is not True:
        warnings.append("provider forwarding was not completely reviewed")
    if filters_reviewed is not True:
        warnings.append("provider filters and rules were not completely reviewed")

    completeness = _validate_exact_keys(
        evidence["completeness"],
        COMPLETENESS_FIELDS,
        "completeness",
    )
    normalized_completeness: dict[str, bool] = {}
    for field in sorted(COMPLETENESS_FIELDS):
        value = completeness[field]
        if not isinstance(value, bool):
            raise SupportEvidenceError(f"completeness.{field} must be boolean")
        normalized_completeness[field] = value
        if not value:
            warnings.append(f"provider response is incomplete for {field}")

    if status != "active":
        warnings.append(f"subscription status is {status}")
    if dkim_status != "enabled":
        warnings.append(f"DKIM status is {dkim_status}")
    if behavior != "reject":
        warnings.append(f"catch-all behavior is {behavior}")

    inventory = {
        "contract": OUTPUT_CONTRACT,
        "provider_id": provider_id,
        "provider_family": PROVIDER_FAMILY,
        "captured_at": captured_at,
        "source": {
            "method": "private_email_admin",
            "read_only": True,
            "evidence_files": evidence_files + ["SHA256SUMS"],
            "account_reference": ticket_reference,
        },
        "objects": sorted(
            normalized_objects,
            key=lambda item: (item["address"], item["object_type"], item["destinations"]),
        ),
        "default_addresses": [
            {
                "domain": domain,
                "behavior": behavior,
                "destination": destination,
            }
        ],
        "domain_routing": [],
    }

    summary = {
        "contract": SUMMARY_CONTRACT,
        "captured_at": captured_at,
        "read_only": True,
        "provider_id": provider_id,
        "provider_family": PROVIDER_FAMILY,
        "domain": domain,
        "ticket_reference": ticket_reference,
        "subscription": {
            "status": status,
            "plan": plan,
            "expiry_date": expiry_date,
            "mailbox_slots": mailbox_slots,
        },
        "object_count": len(normalized_objects),
        "object_type_counts": {
            object_type: sum(
                1 for item in normalized_objects if item["object_type"] == object_type
            )
            for object_type in sorted(OBJECT_TYPES)
        },
        "catch_all": {
            "behavior": behavior,
            "destination": destination,
        },
        "dkim": {
            "status": dkim_status,
            "selector": dkim_selector,
        },
        "provider_rules": {
            "forwarding_reviewed": forwarding_reviewed,
            "filters_reviewed": filters_reviewed,
            "rules_present": rules_present,
            "notes": rules_notes,
        },
        "completeness": normalized_completeness,
        "complete": all(normalized_completeness.values()) and not warnings,
        "warnings": sorted(set(warnings)),
    }
    return inventory, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=pathlib.Path)
    parser.add_argument("--inventory-output", required=True, type=pathlib.Path)
    parser.add_argument("--summary-output", required=True, type=pathlib.Path)
    parser.add_argument("--hub", type=pathlib.Path, default=DEFAULT_HUB)
    parser.add_argument("--identities", type=pathlib.Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--provider-id", default="namecheap-private-email-ww-cx")
    parser.add_argument(
        "--strict-completeness",
        action="store_true",
        help="return status 2 after writing outputs when provider evidence is incomplete",
    )
    return parser


def _write_json_outside_git(path: pathlib.Path, payload: dict[str, Any]) -> None:
    output = path.resolve()
    if _git_root(output):
        raise SupportEvidenceError(
            "refusing to write normalized Private Email evidence into a Git working tree"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def main() -> int:
    args = build_parser().parse_args()
    try:
        inventory, summary = normalize_support_capture(
            args.evidence_dir,
            args.hub,
            args.identities,
            args.provider_id,
        )
        _write_json_outside_git(args.inventory_output, inventory)
        _write_json_outside_git(args.summary_output, summary)
    except SupportEvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(args.inventory_output.resolve())
    print(args.summary_output.resolve())
    if args.strict_completeness and not summary["complete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
