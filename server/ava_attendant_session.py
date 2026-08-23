#!/usr/bin/env python3
"""Fail-closed call-session state machine for the Ava receptionist.

This module models receptionist, recording/transcription policy, private consultation,
and attended transfer. It does not answer, originate, bridge, record, or transfer a real
call. Concrete PBX/media adapters must execute separately commissioned typed actions.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

OPAQUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
CALL_STATES = {
    "offered",
    "notice_required",
    "screening",
    "caller_held",
    "private_owner_consult",
    "accepted",
    "declined",
    "bridged",
    "voicemail",
    "completed",
    "failed",
}
CONSENT_STATES = {"not_required", "pending", "granted", "declined"}


class AttendantSessionError(RuntimeError):
    pass


def _opaque(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not OPAQUE_RE.fullmatch(value):
        raise AttendantSessionError(f"{field_name} must be an opaque identifier")
    return value


@dataclass(frozen=True)
class MediaPolicy:
    recording_enabled: bool = True
    transcription_enabled: bool = True
    notice_required: bool = True
    consent_required: bool = False

    def validate(self) -> "MediaPolicy":
        for value in (self.recording_enabled, self.transcription_enabled, self.notice_required, self.consent_required):
            if not isinstance(value, bool):
                raise AttendantSessionError("media policy fields must be boolean")
        if self.consent_required and not self.notice_required:
            raise AttendantSessionError("consent-required media policy must also require notice")
        return self


@dataclass
class AttendantSession:
    call_ref: str
    destination_ref: str
    work_item_id: str | None = None
    media_policy: MediaPolicy = field(default_factory=MediaPolicy)
    session_id: str = field(default_factory=lambda: "attendant-" + uuid.uuid4().hex)
    state: str = "offered"
    consent_state: str = "pending"
    caller_identity_ref: str | None = None
    purpose_summary: str | None = None
    transcript_ref: str | None = None
    recording_ref: str | None = None
    owner_consult_ref: str | None = None
    transfer_ref: str | None = None
    decision: str | None = None

    def __post_init__(self) -> None:
        _opaque(self.call_ref, "call_ref")
        _opaque(self.destination_ref, "destination_ref")
        if self.work_item_id is not None:
            _opaque(self.work_item_id, "work_item_id")
        self.media_policy.validate()
        if self.state not in CALL_STATES:
            raise AttendantSessionError("call state is invalid")
        self.consent_state = "pending" if self.media_policy.notice_required else "not_required"

    def _transition(self, target: str) -> None:
        allowed = {
            "offered": {"notice_required", "screening", "failed"},
            "notice_required": {"screening", "failed"},
            "screening": {"caller_held", "voicemail", "completed", "failed"},
            "caller_held": {"private_owner_consult", "screening", "voicemail", "failed"},
            "private_owner_consult": {"accepted", "declined", "caller_held", "failed"},
            "accepted": {"bridged", "failed"},
            "declined": {"screening", "voicemail", "completed"},
            "bridged": {"completed", "failed"},
            "voicemail": {"completed", "failed"},
            "completed": set(),
            "failed": set(),
        }
        if target not in allowed[self.state]:
            raise AttendantSessionError(f"invalid attendant transition {self.state} -> {target}")
        self.state = target

    def begin(self) -> dict[str, Any]:
        if self.state != "offered":
            raise AttendantSessionError("attendant session already began")
        if self.media_policy.notice_required:
            self._transition("notice_required")
            return {
                "action": "present_recording_notice",
                "recording_requested": self.media_policy.recording_enabled,
                "transcription_requested": self.media_policy.transcription_enabled,
                "consent_required": self.media_policy.consent_required,
            }
        self._transition("screening")
        return {"action": "begin_screening", "media_capture_allowed": True}

    def record_notice_result(self, *, consent_granted: bool | None = None) -> dict[str, Any]:
        if self.state != "notice_required":
            raise AttendantSessionError("recording notice is not pending")
        if self.media_policy.consent_required:
            if consent_granted is not True:
                self.consent_state = "declined"
                self._transition("failed")
                return {"action": "fallback_without_ava_media", "reason": "required_recording_consent_not_granted"}
            self.consent_state = "granted"
        else:
            self.consent_state = "not_required"
        self._transition("screening")
        return {"action": "begin_screening", "media_capture_allowed": True}

    def attach_media_refs(self, *, transcript_ref: str | None = None, recording_ref: str | None = None) -> None:
        if self.state not in {"screening", "caller_held", "private_owner_consult", "accepted", "declined", "bridged", "voicemail"}:
            raise AttendantSessionError("media references cannot be attached in the current state")
        if transcript_ref is not None:
            self.transcript_ref = _opaque(transcript_ref, "transcript_ref")
        if recording_ref is not None:
            self.recording_ref = _opaque(recording_ref, "recording_ref")

    def set_screening_context(self, *, caller_identity_ref: str | None, purpose_summary: str) -> None:
        if self.state != "screening":
            raise AttendantSessionError("screening context can only be set while screening")
        if caller_identity_ref is not None:
            self.caller_identity_ref = _opaque(caller_identity_ref, "caller_identity_ref")
        if not isinstance(purpose_summary, str) or not purpose_summary.strip() or len(purpose_summary.encode("utf-8")) > 2000:
            raise AttendantSessionError("purpose_summary is invalid")
        self.purpose_summary = purpose_summary.strip()

    def request_warm_transfer(self) -> dict[str, Any]:
        if self.state != "screening":
            raise AttendantSessionError("warm transfer can only begin from screening")
        if not self.purpose_summary:
            raise AttendantSessionError("caller purpose must be established before warm transfer")
        self._transition("caller_held")
        return {
            "capability": "telephony.transfer.prepare",
            "summary": "Place caller on private hold and prepare owner consultation",
            "parameters": {
                "session_id": self.session_id,
                "call_ref": self.call_ref,
                "destination_ref": self.destination_ref,
            },
        }

    def begin_private_consult(self, owner_consult_ref: str) -> dict[str, Any]:
        if self.state != "caller_held":
            raise AttendantSessionError("owner consultation requires caller-held state")
        self.owner_consult_ref = _opaque(owner_consult_ref, "owner_consult_ref")
        self._transition("private_owner_consult")
        return {
            "capability": "telephony.transfer.consult",
            "summary": "Brief the owner on a private consultation leg",
            "parameters": {
                "session_id": self.session_id,
                "owner_consult_ref": self.owner_consult_ref,
                "caller_media_joined": False,
                "purpose_summary": self.purpose_summary,
            },
        }

    def owner_decision(self, decision: str) -> dict[str, Any]:
        if self.state != "private_owner_consult":
            raise AttendantSessionError("owner decision requires private consultation")
        if decision not in {"accept", "decline", "ask_ava", "voicemail"}:
            raise AttendantSessionError("owner decision is invalid")
        self.decision = decision
        if decision == "accept":
            self._transition("accepted")
            return {
                "capability": "telephony.transfer.complete",
                "summary": "Complete attended transfer after owner acceptance",
                "parameters": {
                    "session_id": self.session_id,
                    "call_ref": self.call_ref,
                    "owner_consult_ref": self.owner_consult_ref,
                },
            }
        if decision == "decline":
            self._transition("declined")
            return {"action": "return_caller_to_ava", "disclose_owner_decline": False}
        if decision == "voicemail":
            self._transition("declined")
            self._transition("voicemail")
            return {"action": "take_structured_voicemail", "disclose_owner_decline": False}
        self._transition("caller_held")
        return {"action": "return_to_caller_for_more_information", "owner_consult_private": True}

    def mark_bridged(self, transfer_ref: str) -> dict[str, Any]:
        if self.state != "accepted":
            raise AttendantSessionError("call may only be bridged after acceptance")
        self.transfer_ref = _opaque(transfer_ref, "transfer_ref")
        self._transition("bridged")
        return self.public()

    def resume_screening_after_decline(self) -> dict[str, Any]:
        if self.state != "declined":
            raise AttendantSessionError("caller can only return after decline")
        self._transition("screening")
        return {"action": "resume_screening", "disclose_owner_decline": False}

    def route_to_voicemail(self) -> dict[str, Any]:
        if self.state not in {"screening", "caller_held", "declined"}:
            raise AttendantSessionError("voicemail routing is invalid in current state")
        self._transition("voicemail")
        return {"action": "take_structured_voicemail"}

    def complete(self) -> dict[str, Any]:
        if self.state not in {"screening", "declined", "bridged", "voicemail"}:
            raise AttendantSessionError("attendant session cannot complete in current state")
        self._transition("completed")
        return self.public()

    def fail(self, reason: str) -> dict[str, Any]:
        if self.state in {"completed", "failed"}:
            raise AttendantSessionError("attendant session is terminal")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise AttendantSessionError("failure reason is invalid")
        self._transition("failed")
        return {"state": self.state, "fallback_required": True, "reason": reason.strip()}

    def public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "call_ref": self.call_ref,
            "work_item_id": self.work_item_id,
            "state": self.state,
            "consent_state": self.consent_state,
            "caller_identity_ref": self.caller_identity_ref,
            "purpose_summary": self.purpose_summary,
            "transcript_ref": self.transcript_ref,
            "recording_ref": self.recording_ref,
            "owner_consult_ref": self.owner_consult_ref,
            "transfer_ref": self.transfer_ref,
            "decision": self.decision,
            "caller_joined_private_consult": False,
        }
