#!/usr/bin/env python3
"""Validate the reconciled Unified Communications completion and fresh runtime state."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

paths = {
    "registry": ROOT / "config" / "communications" / "unified-communications.json",
    "event": ROOT / "config" / "communications" / "communications-event-v1.json",
    "identity": ROOT / "config" / "communications" / "identity-registry-v1.json",
    "readiness": ROOT / "config" / "communications" / "readiness-matrix-v1.json",
    "core": ROOT / "server" / "unified_communications.py",
    "workspace_server": ROOT / "server" / "unified_communications_server.py",
    "workspace_page": ROOT / "src" / "web" / "communications" / "index.html",
    "workspace_script": ROOT / "src" / "web" / "communications" / "app.js",
    "mail_ai": ROOT / "server" / "mail_ai_adapter.py",
    "messaging_main": ROOT / "services" / "wwcx-messaging-gateway" / "app" / "main.py",
    "mms_quarantine": ROOT / "services" / "wwcx-messaging-gateway" / "app" / "media_quarantine.py",
    "agent_state": ROOT / ".agent" / "unified-communications.md",
    "validation_record": ROOT / ".agent" / "unified-communications-validation-20260818.md",
    "backlog": ROOT / ".agent" / "unified-communications-backlog-20260818.md",
    "handoff": ROOT / "docs" / "handoff" / "unified-communications-completion-20260818.md",
    "live_acceptance": ROOT / "docs" / "communications" / "unified-communications-live-acceptance-20260818.md",
}

for label, path in paths.items():
    assert path.is_file(), (label, path)
    assert path.stat().st_size > 100, (label, path)

registry = json.loads(paths["registry"].read_text(encoding="utf-8"))
assert registry["production_traffic_authorized"] is False
assert registry["generic_execution_authorized"] is False
assistant = registry["assistant"]
assert assistant["edge1_gateway_version"] == "0.3.4-alpha.3"
assert set(assistant["accepted_live_capabilities"]) == {
    "communications.read",
    "telephony.read",
    "messages.status.read",
    "messages.conversation.read",
    "messages.draft.prepare",
}
assert set(assistant["repository_ready_capabilities"]) == {"mail.status.read", "mail.draft.prepare"}
assert assistant["pending_capabilities"] == ["mail.correspondence.read"]
for forbidden in {
    "messages.send",
    "mail.send",
    "telephony.call.originate",
    "telephony.route.modify",
    "mail.route.modify",
}:
    assert forbidden not in assistant["accepted_live_capabilities"]
    assert forbidden not in assistant["repository_ready_capabilities"]

schema = json.loads(paths["event"].read_text(encoding="utf-8"))
assert schema["$id"] == "wwcx.communications-event.v1"
assert schema["properties"]["security"]["properties"]["quarantine_release_authorized"]["const"] is False
identity = json.loads(paths["identity"].read_text(encoding="utf-8"))
assert identity["correlation_policy"]["explicit_evidence_required"] is True
assert identity["correlation_policy"]["name_similarity_is_evidence"] is False
assert identity["correlation_policy"]["cross_channel_inference_enabled"] is False

readiness = json.loads(paths["readiness"].read_text(encoding="utf-8"))
assert readiness["generated_from"] == "repository_and_fresh_edge1_operator_evidence"
assert readiness["fresh_edge1_runtime_verified"] is False
assert readiness["channels"]["mail"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["mail"]["private_ai_adapter"] == "runtime_ready"
assert readiness["channels"]["sms_mms"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["sms_mms"]["private_ai_adapter"] == "runtime_ready"
assert readiness["channels"]["sms_mms"]["security_quarantine"] == "degraded"
assert readiness["channels"]["sms_mms"]["production_authorization"] == "blocked"
assert readiness["channels"]["private_ai"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["private_ai"]["live_acceptance"] == "runtime_ready"
assert readiness["channels"]["communications_workspace"]["repository_implementation"] == "repository_ready"
assert readiness["channels"]["communications_workspace"]["edge1_runtime"] == "degraded"
assert readiness["channels"]["communications_workspace"]["live_acceptance"] == "degraded"
assert readiness["channels"]["communications_workspace"]["production_authorization"] == "blocked"
assert readiness["rules"]["repository_ready_does_not_imply_runtime_ready"] is True
assert readiness["rules"]["runtime_ready_does_not_imply_live_authorized"] is True
assert readiness["rules"]["historical_acceptance_is_not_fresh_runtime_evidence"] is True

core = paths["core"].read_text(encoding="utf-8")
for token in ("FORBIDDEN_EMBEDDED_KEYS", "SEARCH_FIELDS", "sanitize_derived_metadata", "resolve_identity_links"):
    assert token in core, token

workspace = paths["workspace_server"].read_text(encoding="utf-8")
for token in ("Refusing non-loopback bind", "read_only_workspace", "mutation_authorized", "SnapshotStore"):
    assert token in workspace, token
for forbidden in ("smtplib", "send_message(", "os.system"):
    assert forbidden not in workspace, forbidden

page = paths["workspace_page"].read_text(encoding="utf-8")
for token in ("All activity", "Inbox", "Drafts", "Quarantine", "Search safe metadata", "Timeline", "Inspector", "Readiness matrix"):
    assert token in page, token
script = paths["workspace_script"].read_text(encoding="utf-8")
assert "payload.mutation_authorized !== false" in script
assert "payload.content_is_untrusted !== true" in script

mail_ai = paths["mail_ai"].read_text(encoding="utf-8")
for token in ("mail.status.read", "mail.draft.prepare", "prepared_not_sent", "blocked_pending_authoritative_source"):
    assert token in mail_ai, token
for forbidden in ("smtplib", "send_message(", ".send("):
    assert forbidden not in mail_ai, forbidden

messaging = paths["messaging_main"].read_text(encoding="utf-8")
for token in ("messages.status.read", "messages.conversation.read", "mutation_authorized", "media_quarantine"):
    assert token in messaging, token
mms = paths["mms_quarantine"].read_text(encoding="utf-8")
for token in ("quarantined_pending_scan", "scanned_clean_held", "quarantined_malicious", "quarantined_scan_error", "release_authorized"):
    assert token in mms, token

handoff = paths["handoff"].read_text(encoding="utf-8")
for token in ("PR #384", "PR #385", "PR #386", "PR #387", "PR #389", "fresh_edge1_runtime_verified", "mail.correspondence.read"):
    assert token in handoff, token

live_acceptance = paths["live_acceptance"].read_text(encoding="utf-8")
for token in (
    "Messaging Gateway",
    "0.4.2",
    "0.3.4-alpha.3",
    "messages.conversation.read",
    "messages.draft.prepare",
    "prepared_not_sent",
    "release_authorized: false",
    "wwcx-communications-workspace.service` is not installed",
    "clamscan",
):
    assert token in live_acceptance, token

print("Unified Communications completion validation passed")
print("Fresh Messaging Gateway and BigBird read/draft runtime acceptance is reconciled")
print("Fresh Mail status/draft local adapter acceptance is reconciled")
print("Persistent Communications workspace and MMS scanner/private storage remain incomplete")
print("Global fresh_edge1_runtime_verified remains false until those safe-scope gaps close")
print("No live communications or generic execution authority is accepted by this completion state")
