#!/usr/bin/env python3
"""Repository validation for the read-only Unified Communications workspace."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import unified_communications as core
import unified_communications_server as workspace


def event(event_id: str, timestamp: str, channel: str = "sms", summary: str = "Delivery question") -> dict:
    return {
        "contract": "wwcx.communications-event.v1",
        "communications_event_id": event_id,
        "conversation_id": "conv-1",
        "thread_id": "thread-1",
        "case_id": "case-1",
        "control_id": None,
        "channel": channel,
        "direction": "inbound",
        "timestamp_utc": timestamp,
        "sender_identity_ref": "identity:phone:+15555550100",
        "recipient_identity_refs": ["identity:phone:+15555550101"],
        "native_record": {"record_id": f"native-{event_id}", "source": "test-native", "provider": "simulator", "record_type": "message"},
        "subject_or_summary": summary,
        "status": "observed",
        "security": {"state": "normal", "reason_code": None, "quarantine_release_authorized": False},
        "attachment_media_refs": [],
        "correspondence": {"parent_event_id": None, "relation": "none"},
        "derived": {"ai_generated": False, "derivation_type": None, "source_event_ids": []},
        "provenance": {"source_channel": channel, "authoritative_native_record": True, "transformations": ["normalized_metadata"]},
        "audit_refs": [f"audit:{event_id}"],
    }


# Core contract failure paths are exercised by repository validation, not only pytest.
valid = event("comm_event-0001", "2026-08-18T06:00:00Z")
assert core.validate_event(valid)["native_record"]["record_id"] == "native-comm_event-0001"
raw = dict(valid)
raw["body"] = "raw message body"
try:
    core.validate_event(raw)
except core.CommunicationsContractError:
    pass
else:
    raise AssertionError("canonical event accepted a raw message body")

clean = core.sanitize_derived_metadata({"subject": "ok", "requested_scopes": ["mail.send"], "tool_authority": "telephony.call.originate"})
assert clean == {"subject": "ok"}

with tempfile.TemporaryDirectory() as temporary_directory:
    snapshot = pathlib.Path(temporary_directory) / "events.jsonl"
    events = [
        event("comm_event-0002", "2026-08-18T06:01:00Z", "email", "Records follow-up"),
        valid,
    ]
    snapshot.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
    store = workspace.SnapshotStore(snapshot)
    ordered = store.events()
    assert [item["communications_event_id"] for item in ordered] == ["comm_event-0001", "comm_event-0002"]
    assert [item["communications_event_id"] for item in store.query(text="Records")] == ["comm_event-0002"]
    assert [item["communications_event_id"] for item in store.query(channel="sms")] == ["comm_event-0001"]
    application = workspace.CommunicationsApplication(snapshot)
    payload = application.query({"q": ["Delivery"], "limit": ["50"]})
    assert payload["mutation_authorized"] is False
    assert payload["content_is_untrusted"] is True
    assert payload["events"][0]["communications_event_id"] == "comm_event-0001"
    assert application.event("comm_event-0002")["channel"] == "email"

source = (SERVER / "unified_communications_server.py").read_text(encoding="utf-8")
for required in ("Refusing non-loopback bind", "read_only_workspace", "mutation_authorized", "communications/api/v1/readiness", "communications/api/v1/events"):
    assert required in source, required
for forbidden in ("smtplib", "send_message(", "originate", "dialplan", "subprocess", "os.system"):
    assert forbidden not in source, forbidden

page = (ROOT / "src" / "web" / "communications" / "index.html").read_text(encoding="utf-8")
script = ROOT / "src" / "web" / "communications" / "app.js"
style = (ROOT / "src" / "web" / "communications" / "styles.css").read_text(encoding="utf-8")
for token in ("All activity", "Inbox", "Drafts", "Quarantine", "Search safe metadata", "Timeline", "Inspector", "Readiness matrix", "Specialist tools", "Read does not mean write", "Draft does not mean send"):
    assert token in page, token
for token in ("api/v1/events", "api/v1/readiness", "mutation_authorized", "content_is_untrusted", "channel-filters"):
    assert token in script.read_text(encoding="utf-8"), token
assert "@media(max-width:980px)" in style
assert "@media(max-width:700px)" in style
assert "prefers-reduced-motion" in style

node = subprocess.run(["node", "--check", str(script)], cwd=ROOT, capture_output=True, text=True, check=False)
assert node.returncode == 0, node.stderr

print("Unified Communications workspace validation passed")
print("Canonical metadata search, ordering, inspector and readiness API are read-only")
print("Mutation verbs remain fail-closed and specialist channel tools remain separate")
