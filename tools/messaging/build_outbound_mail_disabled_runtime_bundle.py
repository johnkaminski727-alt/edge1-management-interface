#!/usr/bin/env python3
"""Build a disabled runtime-only outbound-mail configuration bundle.

The builder copies the accepted gateway, policy, and identity documents while
changing only the policy, audit, and nonce paths needed for strict `/etc/wwcx`
and `/var/lib/wwcx-outbound-mail` separation. It never reads credentials,
enables delivery, changes the source files, contacts a provider, or sends mail.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import mail_identity_registry
import outbound_mail_gateway as gateway
import outbound_mail_policy


CONTRACT = "wwcx.outbound-mail-disabled-runtime-bundle.v1"
CONFIG_FILENAME = "outbound-mail-gateway-runtime.json"
POLICY_FILENAME = "outbound-mail-policy-runtime.json"
IDENTITIES_FILENAME = "mail-identities-runtime.json"


class RuntimeBundleError(RuntimeError):
    """Raised when source state is unsafe or the bundle changes an unauthorized field."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError(f"unable to read source JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeBundleError(f"source JSON must be an object: {path}")
    return value


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _changed_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if type(before) is not type(after):
        return [prefix or "$"]
    if isinstance(before, dict):
        result: list[str] = []
        keys = sorted(set(before) | set(after))
        for key in keys:
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(_changed_paths(before[key], after[key], child))
        return result
    if isinstance(before, list):
        return [] if before == after else [prefix or "$"]
    return [] if before == after else [prefix or "$"]


def _all_provider_profiles_disabled(config: dict[str, Any]) -> bool:
    profiles = config.get("provider", {}).get("profiles", {})
    return isinstance(profiles, dict) and bool(profiles) and all(
        isinstance(profile, dict) and profile.get("enabled") is False
        for profile in profiles.values()
    )


def _all_identity_senders_disabled(identities: dict[str, Any]) -> bool:
    entries = identities.get("identities", {})
    return isinstance(entries, dict) and bool(entries) and all(
        isinstance(item, dict) and item.get("live_enabled") is False
        for item in entries.values()
    )


def validate_safe_disabled_sources(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    *,
    require_preparation_enabled: bool,
) -> None:
    try:
        gateway.validate_gateway_config(config)
        outbound_mail_policy.validate_policy(policy)
        mail_identity_registry.validate_registry(identities)
    except Exception as exc:
        raise RuntimeBundleError(f"source document validation failed: {exc}") from exc

    checks = {
        "gateway_enabled": config["enabled"],
        "deployment_authorized": config["deployment_authorized"],
        "external_delivery_authorized": config["external_delivery_authorized"],
        "send_endpoint_enabled": config["admin"]["send_endpoint_enabled"],
        "selected_provider": config["provider"]["selected"],
        "all_provider_profiles_disabled": _all_provider_profiles_disabled(config),
        "policy_enabled": policy["enabled"],
        "smtp_cutover_authorized": policy["delivery"]["smtp_cutover_authorized"],
        "identity_activation_authorized": identities["outbound_activation_authorized"],
        "live_sender_allowlist": identities["sender_selection"]["live_sender_allowlist"],
        "all_identity_senders_disabled": _all_identity_senders_disabled(identities),
        "preparation_api_enabled": config["preparation_api"]["enabled"],
    }
    unsafe = any(
        [
            checks["gateway_enabled"],
            checks["deployment_authorized"],
            checks["external_delivery_authorized"],
            checks["send_endpoint_enabled"],
            checks["selected_provider"] != "none",
            not checks["all_provider_profiles_disabled"],
            checks["policy_enabled"],
            checks["smtp_cutover_authorized"],
            checks["identity_activation_authorized"],
            bool(checks["live_sender_allowlist"]),
            not checks["all_identity_senders_disabled"],
        ]
    )
    if unsafe:
        raise RuntimeBundleError(
            "source configuration is not in the required safe-disabled state"
        )
    if require_preparation_enabled and not checks["preparation_api_enabled"]:
        raise RuntimeBundleError("existing runtime preparation API is not enabled")


def build_bundle(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    *,
    config_root: pathlib.Path,
    state_root: pathlib.Path,
    require_preparation_enabled: bool = True,
) -> dict[str, Any]:
    validate_safe_disabled_sources(
        config,
        policy,
        identities,
        require_preparation_enabled=require_preparation_enabled,
    )
    runtime_config = copy.deepcopy(config)
    runtime_config["paths"]["policy"] = str(config_root / POLICY_FILENAME)
    runtime_config["paths"]["audit_jsonl"] = str(state_root / "audit.jsonl")
    runtime_config["preparation_api"]["nonce_store"] = str(
        state_root / "preparation-nonces.sqlite3"
    )
    try:
        gateway.validate_gateway_config(runtime_config)
    except Exception as exc:
        raise RuntimeBundleError(f"generated runtime config is invalid: {exc}") from exc

    changed = _changed_paths(config, runtime_config)
    expected_changes = sorted(
        [
            "paths.audit_jsonl",
            "paths.policy",
            "preparation_api.nonce_store",
        ]
    )
    if sorted(changed) != expected_changes:
        raise RuntimeBundleError(
            f"runtime config changed unauthorized fields: {sorted(changed)}"
        )

    config_bytes = canonical_bytes(runtime_config)
    policy_bytes = canonical_bytes(policy)
    identities_bytes = canonical_bytes(identities)
    return {
        "contract": CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_root": str(config_root),
        "state_root": str(state_root),
        "files": {
            CONFIG_FILENAME: {
                "content": runtime_config,
                "sha256": sha256_bytes(config_bytes),
                "mode": "0640",
                "owner": "root",
            },
            POLICY_FILENAME: {
                "content": policy,
                "sha256": sha256_bytes(policy_bytes),
                "mode": "0640",
                "owner": "root",
            },
            IDENTITIES_FILENAME: {
                "content": identities,
                "sha256": sha256_bytes(identities_bytes),
                "mode": "0640",
                "owner": "root",
            },
        },
        "config_changed_paths": expected_changes,
        "source_state": {
            "preparation_api_enabled": config["preparation_api"]["enabled"],
            "gateway_enabled": False,
            "external_delivery_authorized": False,
            "send_endpoint_enabled": False,
            "selected_provider": "none",
            "policy_enabled": False,
            "smtp_cutover_authorized": False,
            "identity_activation_authorized": False,
            "live_sender_count": 0,
        },
        "runtime_state_paths": {
            "audit_jsonl": str(state_root / "audit.jsonl"),
            "nonce_store": str(state_root / "preparation-nonces.sqlite3"),
            "suppression_database": str(state_root / "delivery-state.sqlite3"),
        },
        "credentials_read": False,
        "source_files_modified": False,
        "provider_or_sender_enabled": False,
        "external_delivery_enabled": False,
        "message_prepared": False,
        "message_sent": False,
    }


def write_bundle(bundle: dict[str, Any], output_dir: pathlib.Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise RuntimeBundleError("runtime bundle output directory must be empty")
    written: dict[str, str] = {}
    for filename, metadata in bundle["files"].items():
        path = output_dir / filename
        content = canonical_bytes(metadata["content"])
        path.write_bytes(content)
        os.chmod(path, 0o600)
        if sha256_bytes(content) != metadata["sha256"]:
            raise RuntimeBundleError(f"written runtime file hash mismatch: {filename}")
        written[filename] = str(path)
    manifest = copy.deepcopy(bundle)
    for metadata in manifest["files"].values():
        metadata.pop("content", None)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    os.chmod(manifest_path, 0o600)
    written["manifest.json"] = str(manifest_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-config", type=pathlib.Path, required=True)
    parser.add_argument("--policy", type=pathlib.Path, required=True)
    parser.add_argument("--identities", type=pathlib.Path, required=True)
    parser.add_argument("--config-root", type=pathlib.Path, default=pathlib.Path("/etc/wwcx"))
    parser.add_argument(
        "--state-root",
        type=pathlib.Path,
        default=pathlib.Path("/var/lib/wwcx-outbound-mail"),
    )
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--allow-preparation-disabled-test-source",
        action="store_true",
        help="test-only: allow the committed preparation-disabled source",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        bundle = build_bundle(
            load_json(args.existing_config),
            load_json(args.policy),
            load_json(args.identities),
            config_root=args.config_root,
            state_root=args.state_root,
            require_preparation_enabled=not args.allow_preparation_disabled_test_source,
        )
        written = write_bundle(bundle, args.output_dir)
    except RuntimeBundleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"contract": CONTRACT, "written": written}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
