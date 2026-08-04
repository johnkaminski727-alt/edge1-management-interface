#!/usr/bin/env python3
"""Validate the offline outbound-mail Phase E readiness auditor."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/messaging/outbound_mail_phase_e_readiness.py"
SPEC = importlib.util.spec_from_file_location("phase_e_readiness", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase E readiness module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


gateway = load("config/messaging/outbound-mail-gateway.json")
policy = load("config/messaging/outbound-mail-policy.json")
identities = load("config/messaging/mail-identities.json")

os.environ["WWCX_MAIL_SMTP_PASSWORD"] = "SYNTHETIC_SECRET_MUST_NOT_APPEAR"
os.environ["WWCX_MAIL_SMTP_USERNAME"] = "synthetic-user"
report = MODULE.analyze(gateway, policy, identities)
serialized = json.dumps(report, sort_keys=True)

check(report["contract"] == MODULE.REPORT_CONTRACT, "report contract mismatch")
check(report["readiness_state"] == "safe_disabled", "committed state must remain safely disabled")
check(report["ready_for_provider_activation"] is False, "committed state became provider-ready")
check(report["runtime_credentials_inspected"] is False, "auditor inspected credential values")
check(report["network_or_dns_queries_performed"] is False, "auditor claims network activity")
check(report["message_prepared"] is False and report["message_sent"] is False, "auditor changed message state")
check("SYNTHETIC_SECRET_MUST_NOT_APPEAR" not in serialized, "environment secret leaked into report")
check(report["selected_provider"] == "none", "committed provider selection changed")
check(report["first_implemented_delivery_adapter"] == "smtp_submission", "SMTP adapter assessment changed")
check(report["live_sender_allowlist"] == [], "committed live sender allowlist is not empty")
check(report["enabled_sender_profiles"] == [], "committed sender profile unexpectedly enabled")

codes = {item["code"] for item in report["blockers"]}
required_codes = {
    "gateway_disabled",
    "provider_not_selected",
    "policy_disabled",
    "smtp_cutover_not_authorized",
    "live_sender_allowlist_empty",
    "no_sender_profile_enabled",
    "dkim_evidence_required",
    "dmarc_review_required",
    "provider_inventory_incomplete",
    "runtime_credentials_absent",
    "spf_alignment_unverified",
    "bounce_ingestion_undefined",
    "production_message_not_authorized",
}
check(required_codes.issubset(codes), "expected readiness blockers are missing")
check(report["blocker_count"] == len(report["blockers"]), "blocker count mismatch")
check(all(item["ready_for_pilot"] is False for item in report["candidate_senders"]), "sender became pilot-ready")

unsafe_gateway = copy.deepcopy(gateway)
unsafe_gateway["external_delivery_authorized"] = True
unsafe = MODULE.analyze(unsafe_gateway, policy, identities)
check(unsafe["readiness_state"] == "unsafe_partial_activation", "partial activation was not flagged unsafe")
check(unsafe["ready_for_provider_activation"] is False, "partial activation became ready")

malformed = copy.deepcopy(gateway)
malformed["provider"]["profiles"]["smtp_submission"]["password_env"] = "bad env name"
failed_closed = False
try:
    MODULE.analyze(malformed, policy, identities)
except MODULE.ReadinessError:
    failed_closed = True
check(failed_closed, "invalid credential environment name did not fail closed")

with tempfile.TemporaryDirectory() as temporary:
    output = pathlib.Path(temporary) / "phase-e-readiness.json"
    process = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--output",
            str(output),
            "--pretty",
            "--require-safe-disabled",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"CLI validation failed: {process.stderr}")
    cli_report = json.loads(output.read_text(encoding="utf-8"))
    check(cli_report["readiness_state"] == "safe_disabled", "CLI readiness state mismatch")

print("Outbound mail Phase E readiness validation passed")
print("Safe-disabled state, exact blockers, secret non-inspection, and partial-activation detection verified")
