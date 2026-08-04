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


def expect_error(label: str, function) -> None:
    failed = False
    try:
        function()
    except MODULE.RuntimeBundleError:
        failed = True
    check(failed, f"unsafe runtime bundle source did not fail closed: {label}")


config = load(CONFIG_PATH)
policy = load(POLICY_PATH)
identities = load(IDENTITIES_PATH)
originals = copy.deepcopy((config, policy, identities))

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    config_root = folder / "etc-wwcx"
    state_root = folder / "state"
    output = folder / "bundle"
    live_like_config = copy.deepcopy(config)
    live_like_config["preparation_api"]["enabled"] = True

    bundle = MODULE.build_bundle(
        live_like_config,
        policy,
        identities,
        config_root=config_root,
        state_root=state_root,
        require_preparation_enabled=True,
    )
    check(bundle["contract"] == MODULE.CONTRACT, "bundle contract mismatch")
    check(bundle["config_changed_paths"] == [
        "paths.audit_jsonl",
        "paths.policy",
        "preparation_api.nonce_store",
    ], "runtime config change whitelist mismatch")
    runtime_config = bundle["files"][MODULE.CONFIG_FILENAME]["content"]
    check(runtime_config["preparation_api"]["enabled"] is True, "preparation API state changed")
    check(runtime_config["enabled"] is False, "runtime gateway became enabled")
    check(runtime_config["deployment_authorized"] is False, "runtime deployment became authorized")
    check(runtime_config["external_delivery_authorized"] is False, "runtime delivery became authorized")
    check(runtime_config["admin"]["send_endpoint_enabled"] is False, "runtime send endpoint became enabled")
    check(runtime_config["provider"]["selected"] == "none", "runtime provider became selected")
    check(runtime_config["paths"]["policy"] == str(config_root / MODULE.POLICY_FILENAME), "runtime policy path mismatch")
    check(runtime_config["paths"]["audit_jsonl"] == str(state_root / "audit.jsonl"), "runtime audit path mismatch")
    check(runtime_config["preparation_api"]["nonce_store"] == str(state_root / "preparation-nonces.sqlite3"), "runtime nonce path mismatch")
    check(bundle["files"][MODULE.POLICY_FILENAME]["content"] == policy, "policy copy changed")
    check(bundle["files"][MODULE.IDENTITIES_FILENAME]["content"] == identities, "identity copy changed")
    check(bundle["source_state"]["live_sender_count"] == 0, "bundle reports live sender")
    for key in (
        "credentials_read",
        "source_files_modified",
        "provider_or_sender_enabled",
        "external_delivery_enabled",
        "message_prepared",
        "message_sent",
    ):
        check(bundle[key] is False, f"bundle changed safety marker: {key}")

    written = MODULE.write_bundle(bundle, output)
    check(set(written) == {
        MODULE.CONFIG_FILENAME,
        MODULE.POLICY_FILENAME,
        MODULE.IDENTITIES_FILENAME,
        "manifest.json",
    }, "written runtime bundle file set mismatch")
    for filename, path_text in written.items():
        path = pathlib.Path(path_text)
        check(path.is_file(), f"written bundle file missing: {filename}")
        check((path.stat().st_mode & 0o777) == 0o600, f"written bundle mode too broad: {filename}")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    check(manifest["contract"] == MODULE.CONTRACT, "written manifest contract mismatch")
    check("content" not in json.dumps(manifest["files"]), "written manifest retained inline source documents")
    for filename in (MODULE.CONFIG_FILENAME, MODULE.POLICY_FILENAME, MODULE.IDENTITIES_FILENAME):
        data = (output / filename).read_bytes()
        check(hashlib.sha256(data).hexdigest() == manifest["files"][filename]["sha256"], f"written hash mismatch: {filename}")

    expect_error("non-empty output", lambda: MODULE.write_bundle(bundle, output))

    committed_bundle = MODULE.build_bundle(
        config,
        policy,
        identities,
        config_root=config_root,
        state_root=state_root,
        require_preparation_enabled=False,
    )
    check(committed_bundle["source_state"]["preparation_api_enabled"] is False, "test source preparation state changed")

    unsafe_gateway = copy.deepcopy(live_like_config)
    unsafe_gateway["enabled"] = True
    unsafe_gateway["deployment_authorized"] = True
    unsafe_gateway["external_delivery_authorized"] = True
    unsafe_gateway["admin"]["send_endpoint_enabled"] = True
    unsafe_gateway["provider"]["selected"] = "smtp_submission"
    unsafe_gateway["provider"]["profiles"]["smtp_submission"]["enabled"] = True
    expect_error(
        "enabled gateway/provider",
        lambda: MODULE.build_bundle(
            unsafe_gateway,
            policy,
            identities,
            config_root=config_root,
            state_root=state_root,
        ),
    )

    unsafe_policy = copy.deepcopy(policy)
    unsafe_policy["enabled"] = True
    unsafe_policy["delivery"]["smtp_cutover_authorized"] = True
    expect_error(
        "enabled policy",
        lambda: MODULE.build_bundle(
            live_like_config,
            unsafe_policy,
            identities,
            config_root=config_root,
            state_root=state_root,
        ),
    )

    unsafe_identities = copy.deepcopy(identities)
    first_key, first_value = next(iter(unsafe_identities["identities"].items()))
    unsafe_identities["outbound_activation_authorized"] = True
    unsafe_identities["identities"][first_key]["live_enabled"] = True
    unsafe_identities["sender_selection"]["live_sender_allowlist"] = [
        first_value.get("address", first_key)
    ]
    expect_error(
        "enabled sender",
        lambda: MODULE.build_bundle(
            live_like_config,
            policy,
            unsafe_identities,
            config_root=config_root,
            state_root=state_root,
        ),
    )

    expect_error(
        "preparation-disabled production source",
        lambda: MODULE.build_bundle(
            config,
            policy,
            identities,
            config_root=config_root,
            state_root=state_root,
            require_preparation_enabled=True,
        ),
    )

    cli_output = folder / "cli-bundle"
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--existing-config",
            str(CONFIG_PATH),
            "--policy",
            str(POLICY_PATH),
            "--identities",
            str(IDENTITIES_PATH),
            "--config-root",
            str(config_root),
            "--state-root",
            str(state_root),
            "--output-dir",
            str(cli_output),
            "--allow-preparation-disabled-test-source",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"runtime bundle CLI test mode failed: {process.stderr}")
    cli_result = json.loads(process.stdout)
    check(cli_result["contract"] == MODULE.CONTRACT, "runtime bundle CLI contract mismatch")

    production_cli = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--existing-config",
            str(CONFIG_PATH),
            "--policy",
            str(POLICY_PATH),
            "--identities",
            str(IDENTITIES_PATH),
            "--output-dir",
            str(folder / "production-bundle"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(production_cli.returncode == 2, "runtime bundle CLI accepted preparation-disabled production source")
    check("preparation API is not enabled" in production_cli.stderr, "runtime bundle CLI refusal reason changed")

check((config, policy, identities) == originals, "runtime bundle builder mutated source objects")
source_text = TOOL.read_text(encoding="utf-8")
for required in (
    "changing only the policy, audit, and nonce paths",
    "runtime config changed unauthorized fields",
    "source configuration is not in the required safe-disabled state",
    "existing runtime preparation API is not enabled",
    "source document validation failed",
    "credentials_read",
    "source_files_modified",
    "message_sent",
):
    check(required in source_text, f"runtime bundle builder missing safety marker: {required}")
for prohibited in (
    "smtplib",
    "requests.",
    "urllib.request",
    "subprocess.",
    "WWCX_MAIL_SMTP_PASSWORD",
    "getenv(",
):
    check(prohibited not in source_text, f"runtime bundle builder contains prohibited operation: {prohibited}")

print("Disabled outbound-mail runtime bundle validation passed")
print("Only policy, audit, and nonce paths change; preparation state is preserved")
print("Provider, policy, sender, delivery, send, and malformed source activation fail closed")
print("Bundle files are mode 0600, hashed, and source documents remain unmodified")
print("No credential, provider connection, runtime mutation, or message traffic occurs")
