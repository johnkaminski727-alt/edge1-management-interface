#!/usr/bin/env python3
"""Validate the expiring one-message activation and rollback bundle builder."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/build_outbound_mail_controlled_activation_bundle.py"
SCHEMA = ROOT / "schemas/messaging/outbound-mail-controlled-activation.schema.json"
DOC = ROOT / "docs/messaging-operations/outbound-mail-controlled-activation-bundle-20260804.md"
SPEC = importlib.util.spec_from_file_location("activation_bundle", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load activation bundle builder")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def authorization(config: dict, policy: dict, identities: dict, key: str, address: str, now: datetime) -> dict:
    return {
        "contract": MODULE.AUTH_CONTRACT,
        "provider_profile": "smtp_submission",
        "sender_identity_key": key,
        "sender_address": address,
        "runtime_config_sha256": MODULE.sha256_document(config),
        "runtime_policy_sha256": MODULE.sha256_document(policy),
        "runtime_identities_sha256": MODULE.sha256_document(identities),
        "smtp_auth_canary_sha256": "a" * 64,
        "pilot_recipient_sha256": "b" * 64,
        "pilot_payload_sha256": "c" * 64,
        "expires_at": (now + timedelta(minutes=30)).isoformat(timespec="seconds"),
        "smtp_authentication_verified": True,
        "sender_provider_capability_verified": True,
        "dkim_dns_verified": True,
        "dmarc_monitoring_published": True,
        "aggregate_report_mailbox_ready": True,
        "bounce_ingestion_ready": True,
        "complaint_ingestion_ready": True,
        "suppression_gate_ready": True,
        "owned_recipient_verified": True,
        "activation_authorized": True,
        "one_message_authorized": True,
        "max_recipient_count": 1,
        "rollback_required": True,
        "bulk_authorized": False,
        "commercial_authorized": False,
        "regulatory_authorized": False,
        "emergency_authorized": False,
    }


def rejects(function, label: str) -> None:
    try:
        function()
    except MODULE.ActivationBundleError:
        return
    raise RuntimeError(f"unsafe activation state did not fail closed: {label}")


for path in (TOOL, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["properties"]["contract"]["const"] == MODULE.AUTH_CONTRACT, "schema contract mismatch")
check(schema["additionalProperties"] is False, "schema permits extra fields")
check(schema["properties"]["max_recipient_count"]["const"] == 1, "schema permits multiple recipients")
check(schema["properties"]["rollback_required"]["const"] is True, "schema permits no rollback")
for key in ("bulk_authorized", "commercial_authorized", "regulatory_authorized", "emergency_authorized"):
    check(schema["properties"][key]["const"] is False, f"schema permits {key}")

config = load("config/messaging/outbound-mail-gateway.json")
policy = load("config/messaging/outbound-mail-policy.json")
identities = load("config/messaging/mail-identities.json")
runtime_config = copy.deepcopy(config)
runtime_config["preparation_api"]["enabled"] = True
now = datetime(2026, 8, 4, 6, 0, 0, tzinfo=timezone.utc)

selected = None
errors: list[str] = []
for key, identity in identities["identities"].items():
    address = str(identity.get("address", "")).casefold()
    if not address or identity.get("live_enabled") is not False:
        continue
    candidate = authorization(runtime_config, policy, identities, key, address, now)
    try:
        bundle = MODULE.build_bundle(runtime_config, policy, identities, candidate, now=now)
    except MODULE.ActivationBundleError as exc:
        errors.append(f"{key}: {exc}")
        continue
    selected = (key, address, candidate, bundle)
    break
check(selected is not None, "no disabled identity produced a validator-clean activation bundle: " + " | ".join(errors[:5]))
identity_key, sender_address, auth, bundle = selected

check(bundle["contract"] == MODULE.BUNDLE_CONTRACT, "bundle contract mismatch")
check(bundle["provider_profile"] == "smtp_submission", "provider profile mismatch")
check(bundle["sender_identity_key"] == identity_key, "sender key mismatch")
check(bundle["sender_address_sha256"] == hashlib.sha256(sender_address.encode()).hexdigest(), "sender hash mismatch")
check(bundle["max_recipient_count"] == 1, "bundle permits multiple recipients")
check(bundle["rollback_required"] is True, "bundle does not require rollback")
check(bundle["changes"]["gateway"] == sorted([
    "admin.send_endpoint_enabled",
    "deployment_authorized",
    "enabled",
    "external_delivery_authorized",
    "provider.profiles.smtp_submission.enabled",
    "provider.selected",
]), "gateway change whitelist mismatch")
check(bundle["changes"]["policy"] == ["delivery.smtp_cutover_authorized", "enabled"], "policy change whitelist mismatch")
check(bundle["changes"]["identities"] == sorted([
    f"identities.{identity_key}.live_enabled",
    "outbound_activation_authorized",
    "sender_selection.live_sender_allowlist",
]), "identity change whitelist mismatch")

active_config = bundle["activated"]["outbound-mail-gateway-runtime.json"]
active_policy = bundle["activated"]["outbound-mail-policy-runtime.json"]
active_identities = bundle["activated"]["mail-identities-runtime.json"]
check(active_config["enabled"] is True, "activated gateway remains disabled")
check(active_config["deployment_authorized"] is True, "activated deployment remains unauthorized")
check(active_config["external_delivery_authorized"] is True, "activated delivery remains unauthorized")
check(active_config["admin"]["send_endpoint_enabled"] is True, "activated send endpoint remains disabled")
check(active_config["provider"]["selected"] == "smtp_submission", "SMTP provider was not selected")
check(active_config["provider"]["profiles"]["smtp_submission"]["enabled"] is True, "SMTP profile was not enabled")
check(active_config["preparation_api"]["enabled"] is True, "preparation API was disabled")
check(active_policy["enabled"] is True and active_policy["delivery"]["smtp_cutover_authorized"] is True, "policy activation mismatch")
check(active_identities["outbound_activation_authorized"] is True, "identity activation mismatch")
check(active_identities["identities"][identity_key]["live_enabled"] is True, "selected identity not enabled")
check(active_identities["sender_selection"]["live_sender_allowlist"] == [sender_address], "sender allowlist mismatch")
check(bundle["rollback"]["outbound-mail-gateway-runtime.json"] == runtime_config, "gateway rollback copy changed")
check(bundle["rollback"]["outbound-mail-policy-runtime.json"] == policy, "policy rollback copy changed")
check(bundle["rollback"]["mail-identities-runtime.json"] == identities, "identity rollback copy changed")
for key in ("credentials_read", "runtime_files_modified", "provider_contacted", "message_prepared", "message_sent"):
    check(bundle[key] is False, f"bundle safety marker changed: {key}")

hash_mismatch = copy.deepcopy(auth)
hash_mismatch["runtime_config_sha256"] = "f" * 64
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, hash_mismatch, now=now), "runtime hash mismatch")
expired = copy.deepcopy(auth)
expired["expires_at"] = (now - timedelta(seconds=1)).isoformat()
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, expired, now=now), "expired authorization")
long_lived = copy.deepcopy(auth)
long_lived["expires_at"] = (now + timedelta(hours=3)).isoformat()
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, long_lived, now=now), "authorization over two hours")
wrong_address = copy.deepcopy(auth)
wrong_address["sender_address"] = "wrong@example.com"
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, wrong_address, now=now), "sender address mismatch")
missing_readiness = copy.deepcopy(auth)
missing_readiness["bounce_ingestion_ready"] = False
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, missing_readiness, now=now), "missing bounce readiness")
bulk = copy.deepcopy(auth)
bulk["bulk_authorized"] = True
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, bulk, now=now), "bulk authorization")
multi = copy.deepcopy(auth)
multi["max_recipient_count"] = 2
rejects(lambda: MODULE.build_bundle(runtime_config, policy, identities, multi, now=now), "multiple recipients")
active_source = copy.deepcopy(runtime_config)
active_source["enabled"] = True
rejects(lambda: MODULE.build_bundle(active_source, policy, identities, auth, now=now), "already active gateway")

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    output = folder / "bundle"
    written = MODULE.write_bundle(bundle, output)
    check("manifest.json" in written, "activation bundle manifest missing")
    check(len(written) == 7, "activation bundle file count mismatch")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    check("activated" not in manifest and "rollback" not in manifest, "manifest retained inline documents")
    check(len(manifest["file_sha256"]) == 6, "manifest hash inventory mismatch")
    for relative, digest in manifest["file_sha256"].items():
        path = output / relative
        check(path.is_file(), f"bundle file missing: {relative}")
        check((path.stat().st_mode & 0o777) == 0o600, f"bundle file mode too broad: {relative}")
        check(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"bundle file hash mismatch: {relative}")
    rejects(lambda: MODULE.write_bundle(bundle, output), "non-empty output directory")

    config_path = folder / "config.json"
    policy_path = folder / "policy.json"
    identities_path = folder / "identities.json"
    auth_path = folder / "authorization.json"
    config_path.write_text(json.dumps(runtime_config), encoding="utf-8")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    identities_path.write_text(json.dumps(identities), encoding="utf-8")
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    cli_output = folder / "cli-bundle"
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--config", str(config_path),
            "--policy", str(policy_path),
            "--identities", str(identities_path),
            "--authorization", str(auth_path),
            "--output-dir", str(cli_output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(process.returncode == 2, "CLI unexpectedly accepted expired-by-current-time synthetic authorization")

    forbidden = ROOT / "var" / "forbidden-activation-bundle"
    refused = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--config", str(config_path),
            "--policy", str(policy_path),
            "--identities", str(identities_path),
            "--authorization", str(auth_path),
            "--output-dir", str(forbidden),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(refused.returncode == 2, "CLI accepted output inside Git tree")
    check("refusing activation authorization or output" in refused.stderr, "worktree refusal reason changed")
    check(not forbidden.exists(), "CLI wrote forbidden activation output")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "changes only the exact SMTP provider",
    "authorization window exceeds two hours",
    "required preparation-only safe state",
    "activation gateway changes are unauthorized",
    "activation policy changes are unauthorized",
    "activation identity changes are unauthorized",
    "rollback_required",
    "credentials_read",
    "runtime_files_modified",
    "provider_contacted",
    "message_sent",
    "refusing activation authorization or output inside the Git working tree",
):
    check(required in source, f"activation builder missing safety marker: {required}")
for prohibited in (
    "smtplib",
    "requests.",
    "urllib.request",
    "subprocess.",
    "os.replace(",
    "shutil.copy",
    "systemctl",
    "WWCX_MAIL_SMTP_PASSWORD",
    "getenv(",
):
    check(prohibited not in source, f"activation builder contains prohibited operation: {prohibited}")

print("Controlled outbound-mail activation bundle validation passed")
print("Exact runtime hashes, two-hour authorization, readiness gates, one sender/recipient/payload, and rollback verified")
print("Only six gateway, two policy, and three identity paths change")
print("Activated and rollback files are private, hashed, and never installed by the builder")
print("No credential, provider contact, runtime mutation, message preparation, or message traffic occurs")
