#!/usr/bin/env python3
"""Validate the accepted safe-disabled outbound-mail runtime deployment record."""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "records/messaging/deployment-evidence/outbound-mail-safe-disabled-runtime-acceptance-20260804.json"
EXPECTED_DEPLOYED_COMMIT = "1f79d030bec94c6247e3fb5bc93a7f6a76d65ad6"
EXPECTED_VERIFIED_COMMIT = "681806b1190e0639d12120566fa8733430fd3fae"
EXPECTED_SOURCE_SHA256 = "b82b6e9c74245d40ce4eb467bbd9aee4006a9b3db0538a5df8801f0764485db4"
EVIDENCE_ROOT = "/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration/"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_PATH = re.compile(r"^/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration/20260804T[0-9]{6}Z$")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def walk(value: Any, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            for prohibited in (
                "password",
                "credential_value",
                "secret_value",
                "private_key_content",
                "access_token",
                "refresh_token",
            ):
                check(prohibited not in lowered, f"secret-bearing key is prohibited at {path}.{key}")
            walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        check("-----BEGIN" not in value, f"PEM material is prohibited at {path}")
        check("@" not in value, f"email addresses are prohibited in minimized acceptance evidence at {path}")


check(RECORD.is_file(), f"missing {RECORD}")
check(not RECORD.is_symlink(), f"record must not be a symlink: {RECORD}")
record = json.loads(RECORD.read_text(encoding="utf-8"))
check(isinstance(record, dict), "acceptance record must be an object")
walk(record)

check(record.get("contract") == "wwcx.outbound-mail-runtime-acceptance.v1", "unexpected contract")
check(record.get("accepted_at") == "2026-08-04T05:14:35Z", "unexpected acceptance timestamp")
check(record.get("verified_at") == "2026-08-04T05:33:16Z", "unexpected post-fix verification timestamp")

source = record.get("acceptance_source", {})
check(
    source
    == {
        "issue": 187,
        "issue_comment_id": 5174900763,
        "post_fix_issue_comment_id": 5175033877,
        "operator_transcript_reviewed": True,
    },
    "acceptance source drift",
)

deployment = record.get("deployment", {})
check(deployment.get("host") == "edge1.ww.cx", "unexpected host")
check(deployment.get("repository") == "/opt/edge1-management-interface", "unexpected repository")
check(deployment.get("branch") == "main", "unexpected branch")
check(deployment.get("deployed_commit") == EXPECTED_DEPLOYED_COMMIT, "unexpected deployed commit")
check(deployment.get("current_verified_commit") == EXPECTED_VERIFIED_COMMIT, "unexpected verified commit")
check(deployment.get("repair_pull_request") == 291, "unexpected repair PR")
check(deployment.get("git_index_fix_pull_request") == 293, "unexpected Git-index fix PR")
check(deployment.get("service") == "wwcx-outbound-mail-gateway.service", "unexpected service")
check(deployment.get("listener") == "127.0.0.1:8104", "listener is not loopback-only")
check(deployment.get("runtime_state") == "runtime_migration_active_safe_disabled", "runtime is not accepted safe-disabled")
check(deployment.get("state_root") == "/var/lib/wwcx-outbound-mail", "unexpected state root")
check(deployment.get("required_systemd_write_path") == deployment.get("state_root"), "systemd writable path does not match state root")
check(deployment.get("installed_via_bounded_wrapper") is True, "bounded wrapper provenance missing")

evidence = record.get("evidence", {})
evidence_fields = ("audit_directory", "install_directory", "verify_directory")
for field in evidence_fields:
    value = evidence.get(field)
    check(isinstance(value, str) and value.startswith(EVIDENCE_ROOT), f"invalid {field}")
    check(TIMESTAMP_PATH.fullmatch(value) is not None, f"unexpected {field} timestamp shape")
check(len({evidence[field] for field in evidence_fields}) == len(evidence_fields), "evidence directories must be distinct")
check(evidence.get("audit_failures") == 0, "audit failures recorded")
check(evidence.get("install_failures") == 0, "install failures recorded")
check(evidence.get("verify_failures") == 0, "post-fix verification failures recorded")
check(evidence.get("rollback_executed") is False, "successful deployment unexpectedly rolled back")
check(evidence.get("source_config_preserved") is True, "source configuration was not preserved")
check(evidence.get("installer_verification_passed") is True, "installer verification was not accepted")
check(evidence.get("post_fix_verification_passed") is True, "post-fix verification was not accepted")
check(evidence.get("independent_manifest_recheck_recorded") is False, "record overclaims independent manifest verification")

source_configuration = record.get("source_configuration", {})
sha256 = source_configuration.get("sha256")
check(isinstance(sha256, str) and HEX64.fullmatch(sha256) is not None, "source SHA-256 is malformed")
check(sha256 == EXPECTED_SOURCE_SHA256, "source SHA-256 drift")
check(source_configuration.get("modified") is False, "source configuration mutation recorded")

repository_integrity = record.get("repository_integrity", {})
check(
    repository_integrity
    == {
        "git_index_owner": "wwadmin",
        "git_index_group": "wwadmin",
        "git_index_mode": "0644",
        "worktree_clean_after_root_verification": True,
        "root_verification_preserved_index_ownership": True,
        "git_optional_locks_disabled_for_root_wrapper": True,
    },
    "repository-integrity evidence drift",
)

boundaries = record.get("preserved_boundaries", {})
expected_false_boundaries = {
    "provider_credentials_read",
    "hmac_secret_read",
    "provider_enabled",
    "sender_enabled",
    "policy_enabled",
    "external_delivery_enabled",
    "message_prepared",
    "message_sent",
    "dns_modified",
    "firewall_modified",
    "public_listener_added",
}
check(set(boundaries) == expected_false_boundaries, "preserved-boundary field set drift")
check(all(boundaries[key] is False for key in expected_false_boundaries), "a preserved safety boundary is no longer false")

phase_e = record.get("phase_e_effect", {})
check(phase_e.get("safe_disabled_runtime_migration_completed") is True, "runtime migration completion not recorded")
for field in (
    "provider_activation_authorized",
    "credential_use_authorized",
    "smtp_auth_canary_authorized",
    "production_message_authorized",
):
    check(phase_e.get(field) is False, f"unauthorized Phase E gate changed: {field}")
check(
    phase_e.get("remaining_state") == "blocked_pending_separate_explicit_authorizations_and_live_evidence",
    "remaining Phase E state drift",
)

print("Safe-disabled outbound-mail runtime acceptance record validation passed")
print("Post-fix live verification and operator-owned Git index integrity are accepted")
print("Credential, provider, sender, DNS, and production-message authorization remain blocked")
