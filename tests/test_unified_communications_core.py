from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "unified_communications.py"
spec = importlib.util.spec_from_file_location("unified_communications", MODULE_PATH)
assert spec and spec.loader
uc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uc)


def event(**overrides):
    value = {
        "contract": "wwcx.communications-event.v1",
        "communications_event_id": "comm_event-0001",
        "conversation_id": "conv-1",
        "thread_id": "thread-1",
        "case_id": "case-1",
        "control_id": None,
        "channel": "sms",
        "direction": "inbound",
        "timestamp_utc": "2026-08-18T06:00:00Z",
        "sender_identity_ref": "identity:phone:+15555550100",
        "recipient_identity_refs": ["identity:phone:+15555550101"],
        "native_record": {
            "record_id": "provider-message-1",
            "source": "wwcx-messaging-gateway",
            "provider": "simulator",
            "record_type": "message",
        },
        "subject_or_summary": "Delivery question",
        "status": "observed",
        "security": {
            "state": "normal",
            "reason_code": None,
            "quarantine_release_authorized": False,
        },
        "attachment_media_refs": [],
        "correspondence": {"parent_event_id": None, "relation": "none"},
        "derived": {
            "ai_generated": False,
            "derivation_type": None,
            "source_event_ids": [],
        },
        "provenance": {
            "source_channel": "sms",
            "authoritative_native_record": True,
            "transformations": ["normalized_metadata"],
        },
        "audit_refs": ["audit:messaging:1"],
    }
    value.update(overrides)
    return value


def test_valid_event_preserves_native_authority():
    validated = uc.validate_event(event())
    assert validated["native_record"]["record_id"] == "provider-message-1"
    assert validated["provenance"]["authoritative_native_record"] is True


def test_raw_message_body_is_rejected():
    candidate = event()
    candidate["body"] = "raw message text"
    with pytest.raises(uc.CommunicationsContractError, match="embedded raw/private field forbidden"):
        uc.validate_event(candidate)


def test_secret_nested_in_derived_record_is_rejected():
    candidate = event()
    candidate["derived"]["secret"] = "do-not-store"
    with pytest.raises(uc.CommunicationsContractError, match="embedded raw/private field forbidden"):
        uc.validate_event(candidate)


def test_quarantine_release_cannot_be_authorized_by_unified_layer():
    candidate = event()
    candidate["security"]["state"] = "quarantined"
    candidate["security"]["quarantine_release_authorized"] = True
    with pytest.raises(uc.CommunicationsContractError, match="cannot authorize quarantine release"):
        uc.validate_event(candidate)


def test_conversation_order_is_deterministic():
    later_b = event(
        communications_event_id="comm_event-0003",
        timestamp_utc="2026-08-18T06:01:00Z",
    )
    later_a = event(
        communications_event_id="comm_event-0002",
        timestamp_utc="2026-08-18T06:01:00Z",
    )
    ordered = uc.sort_events([later_b, event(), later_a])
    assert [item["communications_event_id"] for item in ordered] == [
        "comm_event-0001",
        "comm_event-0002",
        "comm_event-0003",
    ]


def test_search_is_bounded_to_approved_metadata():
    assert len(uc.search_events([event()], "Delivery")) == 1
    with pytest.raises(uc.CommunicationsContractError, match="unapproved search fields"):
        uc.search_events([event()], "raw", fields=["body"])


def test_identity_links_require_explicit_evidence():
    registry = {
        "correlation_policy": {"explicit_evidence_required": True},
        "links": [
            {
                "identity_refs": ["identity:email:a@example.test", "identity:phone:+15555550100"],
                "evidence_refs": ["case:verified-1"],
            },
            {
                "identity_refs": ["identity:email:a@example.test", "identity:sip:similar-name"],
                "evidence_refs": [],
            },
        ],
    }
    links = uc.resolve_identity_links(registry, "identity:email:a@example.test")
    assert len(links) == 1
    assert links[0]["evidence_refs"] == ["case:verified-1"]


def test_identity_policy_cannot_enable_implicit_correlation():
    registry = {"correlation_policy": {"explicit_evidence_required": False}, "links": []}
    with pytest.raises(uc.CommunicationsContractError, match="must require explicit evidence"):
        uc.resolve_identity_links(registry, "identity:email:a@example.test")


def test_untrusted_retrieval_cannot_grant_scopes_or_tool_authority():
    clean = uc.sanitize_derived_metadata(
        {
            "subject": "ordinary metadata",
            "requested_scopes": ["mail.send"],
            "tool_authority": "telephony.call.originate",
            "permissions": ["messages.send"],
        }
    )
    assert clean == {"subject": "ordinary metadata"}


def test_validation_returns_copy_not_mutable_source_alias():
    original = event()
    validated = uc.validate_event(original)
    validated["native_record"]["record_id"] = "changed"
    assert original["native_record"]["record_id"] == "provider-message-1"


def test_cross_channel_provenance_mismatch_fails():
    candidate = copy.deepcopy(event(channel="email"))
    with pytest.raises(uc.CommunicationsContractError, match="source_channel must match"):
        uc.validate_event(candidate)
