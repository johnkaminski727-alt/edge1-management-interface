#!/usr/bin/env python3
"""Build an expiring one-message outbound-mail activation and rollback bundle.

The builder accepts safe-disabled runtime gateway, policy, and identity documents
plus a closed authorization record. It changes only the exact SMTP provider,
send, policy, and one-sender gates required for a controlled pilot, validates
the resulting documents, and emits both activated and rollback copies. It does
not read credentials, install files, contact a provider, prepare a message, or
send mail.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import re
import stat
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

AUTH_CONTRACT = "wwcx.outbound-mail-controlled-activation.v1"
BUNDLE_CONTRACT = "wwcx.outbound-mail-controlled-activation-bundle.v1"
MAX_AUTHORIZATION_SECONDS = 2 * 60 * 60
HEX64 = set("0123456789abcdef")
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{2,159}$")


class ActivationBundleError(RuntimeError):
    """Raised when activation evidence or source state is unsafe."""


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_document(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivationBundleError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise ActivationBundleError(f"{label} must be a JSON object")
    return value


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def _token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN_RE.fullmatch(value) is not None


def _changed_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if type(before) is not type(after):
        return [prefix or "$"]
    if isinstance(before, dict):
        result: list[str] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(_changed_paths(before[key], after[key], child))
        return result
    if isinstance(before, list):
        return [] if before == after else [prefix or "$"]
    return [] if before == after else [prefix or "$"]


def _parse_timestamp(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ActivationBundleError(f"controlled activation {label} is invalid") from exc
    if parsed.tzinfo is None:
        raise ActivationBundleError(f"controlled activation {label} lacks a timezone")
    return parsed.astimezone(timezone.utc)


def validate_authorization(
    authorization: dict[str, Any],
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    expected = {
        "contract",
        "authorization_id",
        "authorized_by",
        "authorization_reference",
        "issued_at",
        "expires_at",
        "provider_profile",
        "sender_identity_key",
        "sender_address",
        "runtime_config_sha256",
        "runtime_policy_sha256",
        "runtime_identities_sha256",
        "smtp_auth_canary_sha256",
        "pilot_recipient_sha256",
        "pilot_payload_sha256",
        "smtp_authentication_verified",
        "sender_provider_capability_verified",
        "dkim_dns_verified",
        "dmarc_monitoring_published",
        "aggregate_report_mailbox_ready",
        "bounce_ingestion_ready",
        "complaint_ingestion_ready",
        "suppression_gate_ready",
        "owned_recipient_verified",
        "activation_authorized",
        "one_message_authorized",
        "max_recipient_count",
        "rollback_required",
        "bulk_authorized",
        "commercial_authorized",
        "regulatory_authorized",
        "emergency_authorized",
    }
    if set(authorization) != expected:
        raise ActivationBundleError("controlled activation authorization keys are invalid")
    if authorization["contract"] != AUTH_CONTRACT:
        raise ActivationBundleError("controlled activation authorization contract is unsupported")
    for key in ("authorization_id", "authorized_by", "authorization_reference"):
        if not _token(authorization[key]):
            raise ActivationBundleError(f"controlled activation {key} is invalid")
    if authorization["provider_profile"] != "smtp_submission":
        raise ActivationBundleError("controlled activation provider profile is invalid")
    required_true = (
        "smtp_authentication_verified",
        "sender_provider_capability_verified",
        "dkim_dns_verified",
        "dmarc_monitoring_published",
        "aggregate_report_mailbox_ready",
        "bounce_ingestion_ready",
        "complaint_ingestion_ready",
        "suppression_gate_ready",
        "owned_recipient_verified",
        "activation_authorized",
        "one_message_authorized",
        "rollback_required",
    )
    if any(authorization[key] is not True for key in required_true):
        raise ActivationBundleError("controlled activation readiness or authorization is incomplete")
    prohibited = ("bulk_authorized", "commercial_authorized", "regulatory_authorized", "emergency_authorized")
    if any(authorization[key] is not False for key in prohibited):
        raise ActivationBundleError("controlled activation authorizes a prohibited traffic class")
    if authorization["max_recipient_count"] != 1:
        raise ActivationBundleError("controlled activation must permit exactly one recipient")
    for key in (
        "runtime_config_sha256",
        "runtime_policy_sha256",
        "runtime_identities_sha256",
        "smtp_auth_canary_sha256",
        "pilot_recipient_sha256",
        "pilot_payload_sha256",
    ):
        if not _sha256(authorization[key]):
            raise ActivationBundleError(f"controlled activation {key} is invalid")
    if authorization["runtime_config_sha256"] != sha256_document(config):
        raise ActivationBundleError("runtime gateway config hash does not match authorization")
    if authorization["runtime_policy_sha256"] != sha256_document(policy):
        raise ActivationBundleError("runtime policy hash does not match authorization")
    if authorization["runtime_identities_sha256"] != sha256_document(identities):
        raise ActivationBundleError("runtime identities hash does not match authorization")

    issued = _parse_timestamp(authorization["issued_at"], "issued_at")
    expires = _parse_timestamp(authorization["expires_at"], "expires_at")
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    lifetime = (expires - issued).total_seconds()
    if lifetime <= 0:
        raise ActivationBundleError("controlled activation authorization lifetime is invalid")
    if lifetime > MAX_AUTHORIZATION_SECONDS:
        raise ActivationBundleError("controlled activation authorization lifetime exceeds two hours")
    if issued > current:
        raise ActivationBundleError("controlled activation authorization is not yet valid")
    if expires <= current:
        raise ActivationBundleError("controlled activation authorization has expired")
    return {
        "authorization_id": authorization["authorization_id"],
        "authorized_by": authorization["authorized_by"],
        "authorization_reference": authorization["authorization_reference"],
        "authorization_sha256": sha256_document(authorization),
        "issued_at": issued.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "remaining_seconds": int((expires - current).total_seconds()),
    }


def validate_safe_sources(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
) -> None:
    try:
        gateway.validate_gateway_config(config)
        outbound_mail_policy.validate_policy(policy)
        mail_identity_registry.validate_registry(identities)
    except Exception as exc:
        raise ActivationBundleError(f"runtime source document validation failed: {exc}") from exc
    profiles = config["provider"]["profiles"]
    sender_profiles = identities["sender_profiles"]
    unsafe = any(
        [
            not config["preparation_api"]["enabled"],
            config["enabled"],
            config["deployment_authorized"],
            config["external_delivery_authorized"],
            config["admin"]["send_endpoint_enabled"],
            config["provider"]["selected"] != "none",
            any(profile.get("enabled") is not False for profile in profiles.values()),
            policy["enabled"],
            policy["delivery"]["smtp_cutover_authorized"],
            identities["outbound_activation_authorized"],
            bool(identities["sender_selection"]["live_sender_allowlist"]),
            any(profile.get("outbound_enabled") is not False for profile in sender_profiles.values()),
            identities["system_senders"]["noreply"].get("outbound_enabled") is not False,
        ]
    )
    if unsafe:
        raise ActivationBundleError("runtime sources are not in the required preparation-only safe state")


def build_bundle(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    authorization: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_safe_sources(config, policy, identities)
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    auth_status = validate_authorization(authorization, config, policy, identities, now=current)
    identity_key = authorization["sender_identity_key"]
    sender_address = str(authorization["sender_address"]).casefold()
    identity = identities["sender_profiles"].get(identity_key)
    if not isinstance(identity, dict):
        raise ActivationBundleError("authorized sender profile key does not exist")
    if str(identity.get("address", "")).casefold() != sender_address:
        raise ActivationBundleError("authorized sender address does not match the identity registry")
    if identity.get("outbound_enabled") is not False:
        raise ActivationBundleError("authorized sender is not currently disabled")

    active_config = copy.deepcopy(config)
    active_config["enabled"] = True
    active_config["deployment_authorized"] = True
    active_config["external_delivery_authorized"] = True
    active_config["admin"]["send_endpoint_enabled"] = True
    active_config["provider"]["selected"] = "smtp_submission"
    active_config["provider"]["profiles"]["smtp_submission"]["enabled"] = True

    active_policy = copy.deepcopy(policy)
    active_policy["enabled"] = True
    active_policy["delivery"]["smtp_cutover_authorized"] = True

    active_identities = copy.deepcopy(identities)
    active_identities["outbound_activation_authorized"] = True
    active_identities["sender_profiles"][identity_key]["outbound_enabled"] = True
    active_identities["sender_selection"]["live_sender_allowlist"] = [sender_address]

    try:
        gateway.validate_gateway_config(active_config)
        outbound_mail_policy.validate_policy(active_policy)
        mail_identity_registry.validate_registry(active_identities)
    except Exception as exc:
        raise ActivationBundleError(f"generated activation documents are invalid: {exc}") from exc

    config_changes = sorted(_changed_paths(config, active_config))
    policy_changes = sorted(_changed_paths(policy, active_policy))
    identity_changes = sorted(_changed_paths(identities, active_identities))
    expected_config = sorted(
        [
            "admin.send_endpoint_enabled",
            "deployment_authorized",
            "enabled",
            "external_delivery_authorized",
            "provider.profiles.smtp_submission.enabled",
            "provider.selected",
        ]
    )
    expected_policy = ["delivery.smtp_cutover_authorized", "enabled"]
    expected_identities = sorted(
        [
            f"sender_profiles.{identity_key}.outbound_enabled",
            "outbound_activation_authorized",
            "sender_selection.live_sender_allowlist",
        ]
    )
    if config_changes != expected_config:
        raise ActivationBundleError(f"activation gateway changes are unauthorized: {config_changes}")
    if policy_changes != expected_policy:
        raise ActivationBundleError(f"activation policy changes are unauthorized: {policy_changes}")
    if identity_changes != expected_identities:
        raise ActivationBundleError(f"activation identity changes are unauthorized: {identity_changes}")

    return {
        "contract": BUNDLE_CONTRACT,
        "generated_at": current.isoformat(timespec="seconds"),
        "authorization_id": auth_status["authorization_id"],
        "authorized_by": auth_status["authorized_by"],
        "authorization_reference": auth_status["authorization_reference"],
        "authorization_sha256": auth_status["authorization_sha256"],
        "authorization_issued_at": auth_status["issued_at"],
        "authorization_expires_at": auth_status["expires_at"],
        "source_runtime_sha256": {
            "outbound-mail-gateway-runtime.json": authorization["runtime_config_sha256"],
            "outbound-mail-policy-runtime.json": authorization["runtime_policy_sha256"],
            "mail-identities-runtime.json": authorization["runtime_identities_sha256"],
        },
        "provider_profile": "smtp_submission",
        "sender_identity_key": identity_key,
        "sender_address_sha256": hashlib.sha256(sender_address.encode("utf-8")).hexdigest(),
        "pilot_recipient_sha256": authorization["pilot_recipient_sha256"],
        "pilot_payload_sha256": authorization["pilot_payload_sha256"],
        "smtp_auth_canary_sha256": authorization["smtp_auth_canary_sha256"],
        "max_recipient_count": 1,
        "rollback_required": True,
        "changes": {
            "gateway": expected_config,
            "policy": expected_policy,
            "identities": expected_identities,
        },
        "activated": {
            "outbound-mail-gateway-runtime.json": active_config,
            "outbound-mail-policy-runtime.json": active_policy,
            "mail-identities-runtime.json": active_identities,
        },
        "rollback": {
            "outbound-mail-gateway-runtime.json": copy.deepcopy(config),
            "outbound-mail-policy-runtime.json": copy.deepcopy(policy),
            "mail-identities-runtime.json": copy.deepcopy(identities),
        },
        "credentials_read": False,
        "runtime_files_modified": False,
        "provider_contacted": False,
        "message_prepared": False,
        "message_sent": False,
    }


def _absolute_without_resolving(path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(os.fspath(path)))


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    repo = ROOT.resolve()
    return resolved == repo or repo in resolved.parents


def _reject_symlink_components(path: pathlib.Path, label: str) -> pathlib.Path:
    absolute = _absolute_without_resolving(path)
    current = pathlib.Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ActivationBundleError(f"{label} contains a symlink component")
    return absolute


def _validate_input_file(path: pathlib.Path, label: str, *, private: bool) -> pathlib.Path:
    absolute = _reject_symlink_components(path, label)
    try:
        details = absolute.lstat()
    except OSError as exc:
        raise ActivationBundleError(f"unable to inspect {label}") from exc
    if not stat.S_ISREG(details.st_mode):
        raise ActivationBundleError(f"{label} must be a regular file")
    mode = stat.S_IMODE(details.st_mode)
    if mode & 0o022:
        raise ActivationBundleError(f"{label} is group/world writable")
    if private and mode & 0o077:
        raise ActivationBundleError(f"{label} must be private mode 0600 or stricter")
    if details.st_uid != os.geteuid():
        raise ActivationBundleError(f"{label} is not owned by the current operator")
    return absolute


def _secure_write(path: pathlib.Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def write_bundle(bundle: dict[str, Any], output_dir: pathlib.Path) -> dict[str, str]:
    output = _absolute_without_resolving(output_dir)
    _reject_symlink_components(output.parent, "activation bundle output parent")
    if output.exists() or output.is_symlink():
        raise ActivationBundleError("activation bundle output directory must not already exist")
    try:
        parent_details = output.parent.lstat()
    except OSError as exc:
        raise ActivationBundleError("activation bundle output parent is unavailable") from exc
    if not stat.S_ISDIR(parent_details.st_mode):
        raise ActivationBundleError("activation bundle output parent is not a directory")
    if stat.S_IMODE(parent_details.st_mode) & 0o022:
        raise ActivationBundleError("activation bundle output parent is group/world writable")
    if parent_details.st_uid != os.geteuid():
        raise ActivationBundleError("activation bundle output parent is not owned by the current operator")
    output.mkdir(mode=0o700)
    written: dict[str, str] = {}
    for section in ("activated", "rollback"):
        section_dir = output / section
        section_dir.mkdir(mode=0o700)
        for filename, document in bundle[section].items():
            path = section_dir / filename
            _secure_write(path, canonical_bytes(document))
            written[f"{section}/{filename}"] = str(path)
    manifest = copy.deepcopy(bundle)
    manifest.pop("activated")
    manifest.pop("rollback")
    manifest["file_sha256"] = {
        key: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        for key, path in sorted(written.items())
    }
    manifest_path = output / "manifest.json"
    _secure_write(manifest_path, canonical_bytes(manifest))
    written["manifest.json"] = str(manifest_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, required=True)
    parser.add_argument("--policy", type=pathlib.Path, required=True)
    parser.add_argument("--identities", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    return parser.parse_args()


def main() -> int:
    os.umask(0o077)
    args = parse_args()
    all_paths = {
        "runtime gateway config": args.config,
        "runtime policy": args.policy,
        "runtime identities": args.identities,
        "controlled activation authorization": args.authorization,
        "activation bundle output": args.output_dir,
    }
    if any(_inside_repo(path) for path in all_paths.values()):
        print("refusing runtime input, activation authorization, or output inside the Git working tree", file=sys.stderr)
        return 2
    try:
        config_path = _validate_input_file(args.config, "runtime gateway config", private=False)
        policy_path = _validate_input_file(args.policy, "runtime policy", private=False)
        identities_path = _validate_input_file(args.identities, "runtime identities", private=False)
        authorization_path = _validate_input_file(
            args.authorization,
            "controlled activation authorization",
            private=True,
        )
        bundle = build_bundle(
            load_json(config_path, "runtime gateway config"),
            load_json(policy_path, "runtime policy"),
            load_json(identities_path, "runtime identities"),
            load_json(authorization_path, "controlled activation authorization"),
        )
        written = write_bundle(bundle, args.output_dir)
    except ActivationBundleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"contract": BUNDLE_CONTRACT, "written": written}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
