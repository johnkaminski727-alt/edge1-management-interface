#!/usr/bin/env python3
"""Validate the safe-disabled outbound-mail runtime bundle builder."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/build_outbound_mail_disabled_runtime_bundle.py"
SPEC = importlib.util.spec_from_file_location("runtime_bundle", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load runtime bundle builder")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CONFIG_PATH = ROOT / "config/messaging/outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config/messaging/outbound-mail-policy.json"
IDENTITIES_PATH = ROOT / "config/messaging/mail-identities.json"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rejects(function, label: str) -> None:
    try:
        function()
    except MODULE.RuntimeBundleError:
        return
    raise RuntimeError(f"unsafe bundle input did not fail closed: {label}")


config = load(CONFIG_PATH)
policy = load(POLICY_PATH)
identities = load(IDENTITIES_PATH)
source_snapshot = copy.deepcopy((config, policy, identities))

with tempfile.TemporaryDirectory() as temporary:
    root = pathlib.Path(temporary)
    config_root = root / "etc"
    state_root = root / "state"
    live_config = copy.deepcopy(config)
    live_config["preparation_api"]["enabled"] = True
    bundle = MODULE.build_bundle(
        live_config,
        policy,
        identities,
        config_root=config_root,
        state_root=state_root,
    )
    check(bundle["config_changed_paths"] == [
        "paths.audit_jsonl",
        "paths.policy",
        "preparation_api.nonce_store",
    ], "runtime change whitelist mismatch")
    runtime = bundle["files"][MODULE.CONFIG_FILENAME]["content"]
    check(runtime["preparation_api"]["enabled"] is True, "preparation state changed")
    check(runtime["enabled"] is False, "gateway became enabled")
    check(runtime["deployment_authorized"] is False, "deployment became authorized")
    check(runtime["external_delivery_authorized"] is False, "delivery became authorized")
    check(runtime["admin"]["send_endpoint_enabled"] is False, "send endpoint became enabled")
    check(runtime["provider"]["selected"] == "none", "provider became selected")
    check(runtime["paths"]["policy"] == str(config_root / MODULE.POLICY_FILENAME), "policy path mismatch")
    check(runtime["paths"]["audit_jsonl"] == str(state_root / "audit.jsonl"), "audit path mismatch")
    check(runtime["preparation_api"]["nonce_store"] == str(state_root / "preparation-nonces.sqlite3"), "nonce path mismatch")
    check(bundle["files"][MODULE.POLICY_FILENAME]["content"] == policy, "policy changed")
    check(bundle["files"][MODULE.IDENTITIES_FILENAME]["content"] == identities, "identities changed")
    for key in (
        "credentials_read",
        "source_files_modified",
        "provider_or_sender_enabled",
        "external_delivery_enabled",
        "message_prepared",
        "message_sent",
    ):
        check(bundle[key] is False, f"safety marker changed: {key}")

    output = root / "bundle"
    written = MODULE.write_bundle(bundle, output)
    check(set(written) == {
        MODULE.CONFIG_FILENAME,
        MODULE.POLICY_FILENAME,
        MODULE.IDENTITIES_FILENAME,
        "manifest.json",
    }, "bundle file set mismatch")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for filename in (MODULE.CONFIG_FILENAME, MODULE.POLICY_FILENAME, MODULE.IDENTITIES_FILENAME):
        path = output / filename
        check((path.stat().st_mode & 0o777) == 0o600, f"staging mode too broad: {filename}")
        check(hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][filename]["sha256"], f"hash mismatch: {filename}")
    rejects(lambda: MODULE.write_bundle(bundle, output), "non-empty output directory")

    unsafe_gateway = copy.deepcopy(live_config)
    unsafe_gateway.update({
        "enabled": True,
        "deployment_authorized": True,
        "external_delivery_authorized": True,
    })
    unsafe_gateway["admin"]["send_endpoint_enabled"] = True
    unsafe_gateway["provider"]["selected"] = "smtp_submission"
    unsafe_gateway["provider"]["profiles"]["smtp_submission"]["enabled"] = True
    rejects(lambda: MODULE.build_bundle(unsafe_gateway, policy, identities, config_root=config_root, state_root=state_root), "enabled gateway/provider")

    unsafe_policy = copy.deepcopy(policy)
    unsafe_policy["enabled"] = True
    unsafe_policy["delivery"]["smtp_cutover_authorized"] = True
    rejects(lambda: MODULE.build_bundle(live_config, unsafe_policy, identities, config_root=config_root, state_root=state_root), "enabled policy")

    malformed_identities = copy.deepcopy(identities)
    malformed_identities["outbound_activation_authorized"] = True
    malformed_identities["sender_selection"]["live_sender_allowlist"] = ["not-a-valid-sender"]
    rejects(lambda: MODULE.build_bundle(live_config, policy, malformed_identities, config_root=config_root, state_root=state_root), "activated or malformed identities")

    rejects(lambda: MODULE.build_bundle(config, policy, identities, config_root=config_root, state_root=state_root), "preparation-disabled production source")
    test_bundle = MODULE.build_bundle(
        config,
        policy,
        identities,
        config_root=config_root,
        state_root=state_root,
        require_preparation_enabled=False,
    )
    check(test_bundle["source_state"]["preparation_api_enabled"] is False, "test-only preparation state changed")

    cli_output = root / "cli"
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--existing-config", str(CONFIG_PATH),
            "--policy", str(POLICY_PATH),
            "--identities", str(IDENTITIES_PATH),
            "--config-root", str(config_root),
            "--state-root", str(state_root),
            "--output-dir", str(cli_output),
            "--allow-preparation-disabled-test-source",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(process.returncode == 0, f"bundle CLI failed: {process.stderr}")

check((config, policy, identities) == source_snapshot, "builder mutated source objects")
source = TOOL.read_text(encoding="utf-8")
for required in (
    "changing only the policy, audit, and nonce paths",
    "runtime config changed unauthorized fields",
    "source configuration is not in the required safe-disabled state",
    "source document validation failed",
    "existing runtime preparation API is not enabled",
    "credentials_read",
    "message_sent",
):
    check(required in source, f"builder missing safety marker: {required}")
for prohibited in ("smtplib", "requests.", "urllib.request", "subprocess.", "WWCX_MAIL_SMTP_PASSWORD", "getenv("):
    check(prohibited not in source, f"builder contains prohibited operation: {prohibited}")

print("Disabled outbound-mail runtime bundle validation passed")
print("Only policy, audit, and nonce paths change; preparation state is preserved")
print("Gateway, provider, policy, sender, delivery, send, and malformed source states fail closed")
print("Staged files are mode 0600 and hashed; source documents remain unmodified")
print("No credential, provider connection, runtime mutation, or message traffic occurs")
