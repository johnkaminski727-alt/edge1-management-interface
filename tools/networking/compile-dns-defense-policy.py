#!/usr/bin/env python3
"""Compile a repository-managed DNS defense policy into staged Unbound RPZ assets."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SUPPORTED_ACTIONS = {
    "nxdomain": ".",
    "nodata": "*.",
    "passthru": "rpz-passthru.",
}
POLICY_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


class PolicyError(ValueError):
    """Raised when a policy cannot be compiled safely."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"policy file is unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyError("policy root must be a JSON object")
    return value


def normalize_domain(value: Any) -> str:
    text = str(value or "").strip().rstrip(".").lower()
    if not text:
        raise PolicyError("domain must not be empty")
    if text.startswith("*."):
        raise PolicyError("domain must not include a wildcard; use include_subdomains")
    if any(char.isspace() or ord(char) < 33 or ord(char) == 127 for char in text):
        raise PolicyError(f"domain contains whitespace or control characters: {text!r}")
    try:
        ascii_name = text.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PolicyError(f"domain is not valid IDNA: {text!r}") from exc
    labels = ascii_name.split(".")
    if len(labels) < 2:
        raise PolicyError(f"domain must contain at least two labels: {ascii_name!r}")
    if len(ascii_name) > 253:
        raise PolicyError(f"domain is too long: {ascii_name!r}")
    for label in labels:
        if not label or len(label) > 63:
            raise PolicyError(f"domain label is invalid: {ascii_name!r}")
        if label.startswith("-") or label.endswith("-"):
            raise PolicyError(f"domain label cannot start or end with '-': {ascii_name!r}")
        if not re.fullmatch(r"[a-z0-9-]+", label):
            raise PolicyError(f"domain label contains unsupported characters: {ascii_name!r}")
    return ascii_name


def normalize_policy_name(value: Any) -> str:
    name = normalize_domain(value)
    if not POLICY_NAME_RE.fullmatch(name):
        raise PolicyError(f"policy_name is invalid: {name!r}")
    return name


def validate_policy(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError(f"schema_version must be {SCHEMA_VERSION!r}")

    policy_name = normalize_policy_name(document.get("policy_name"))
    serial = document.get("serial")
    if not isinstance(serial, int) or isinstance(serial, bool) or not (1 <= serial <= 4294967295):
        raise PolicyError("serial must be an integer between 1 and 4294967295")

    entries = document.get("entries")
    if not isinstance(entries, list):
        raise PolicyError("entries must be a JSON array")
    if len(entries) > 100000:
        raise PolicyError("entries exceeds the 100000 record safety limit")

    normalized_entries: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise PolicyError(f"entries[{index}] must be an object")
        domain = normalize_domain(item.get("domain"))
        action = str(item.get("action") or "").strip().lower()
        if action not in SUPPORTED_ACTIONS:
            raise PolicyError(
                f"entries[{index}].action must be one of: {', '.join(sorted(SUPPORTED_ACTIONS))}"
            )
        include_subdomains = item.get("include_subdomains", False)
        if not isinstance(include_subdomains, bool):
            raise PolicyError(f"entries[{index}].include_subdomains must be boolean")
        reason = str(item.get("reason") or "").strip()
        if len(reason) > 500:
            raise PolicyError(f"entries[{index}].reason exceeds 500 characters")

        previous = seen.get(domain)
        if previous is not None:
            raise PolicyError(
                f"duplicate or conflicting policy entry for {domain!r}: {previous!r} and {action!r}"
            )
        seen[domain] = action
        normalized_entries.append(
            {
                "domain": domain,
                "action": action,
                "include_subdomains": include_subdomains,
                "reason": reason,
            }
        )

    ttl = document.get("ttl", 60)
    if not isinstance(ttl, int) or isinstance(ttl, bool) or not (30 <= ttl <= 86400):
        raise PolicyError("ttl must be an integer between 30 and 86400 seconds")

    normalized_entries.sort(key=lambda item: (item["domain"], item["action"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_name": policy_name,
        "serial": serial,
        "ttl": ttl,
        "entries": normalized_entries,
    }


def compile_zone(policy: dict[str, Any]) -> str:
    ttl = policy["ttl"]
    if not 30 <= ttl <= 86400:
        raise PolicyError("ttl must be between 30 and 86400 seconds")

    lines = [
        f"$ORIGIN {policy['policy_name']}.",
        f"$TTL {ttl}",
        "@ IN SOA localhost. hostmaster.localhost. (",
        f"    {policy['serial']} 3600 600 86400 {ttl}",
        ")",
        "@ IN NS localhost.",
        "",
    ]
    for item in policy["entries"]:
        target = SUPPORTED_ACTIONS[item["action"]]
        lines.append(f"{item['domain']}. CNAME {target}")
        if item["include_subdomains"]:
            lines.append(f"*.{item['domain']}. CNAME {target}")
    return "\n".join(lines).rstrip() + "\n"


def compile_staged_include(policy: dict[str, Any], zonefile: Path) -> str:
    return "\n".join(
        [
            "# Generated WW.CX DNS Defense staging include.",
            "# Observation only: policy actions are disabled and may be logged after explicit installation.",
            "# Prerequisite: the active server module-config must include respip before this include is used.",
            "rpz:",
            f'    name: "{policy["policy_name"]}"',
            f'    zonefile: "{zonefile}"',
            "    rpz-action-override: disabled",
            "    rpz-log: yes",
            '    rpz-log-name: "wwcx-dns-defense-staged"',
            "",
        ]
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_status(policy: dict[str, Any], zone: str, include: str, policy_path: Path) -> dict[str, Any]:
    action_counts = {action: 0 for action in sorted(SUPPORTED_ACTIONS)}
    expanded_records = 0
    for item in policy["entries"]:
        action_counts[item["action"]] += 1
        expanded_records += 2 if item["include_subdomains"] else 1
    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "read_only": True,
        "traffic_controls_changed": False,
        "activation_mode": "staged_disabled",
        "enforcement_enabled": False,
        "rpz_action_override": "disabled",
        "requires_explicit_activation": True,
        "requires_respip_module": True,
        "policy": {
            "name": policy["policy_name"],
            "serial": policy["serial"],
            "source_file": policy_path.name,
            "entry_count": len(policy["entries"]),
            "expanded_record_count": expanded_records,
            "action_counts": action_counts,
        },
        "artifacts": {
            "zone_sha256": sha256_text(zone),
            "include_sha256": sha256_text(include),
        },
        "limitations": [
            "The generated include is not installed or loaded automatically.",
            "The staged RPZ action override is disabled, so policy matches do not alter DNS answers.",
            "Live resolver module configuration, syntax, logging, and statistics require separate authenticated verification.",
        ],
    }


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(path)


def write_outputs(policy_path: Path, output_dir: Path) -> dict[str, Path]:
    policy = validate_policy(load_policy(policy_path))
    zone_path = output_dir / f"{policy['policy_name']}.zone"
    include_path = output_dir / "wwcx-dns-defense-staged.conf"
    status_path = output_dir / "dns-defense-policy-status.json"
    zone = compile_zone(policy)
    include = compile_staged_include(policy, zone_path)
    status = build_status(policy, zone, include, policy_path)
    atomic_write(zone_path, zone)
    atomic_write(include_path, include)
    atomic_write(status_path, json.dumps(status, indent=2, sort_keys=True) + "\n")
    return {"zone": zone_path, "include": include_path, "status": status_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        outputs = write_outputs(args.policy, args.output_dir)
    except PolicyError as exc:
        raise SystemExit(f"DNS defense policy rejected: {exc}") from exc
    print(json.dumps({"ok": True, **{name: str(path) for name, path in outputs.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
