#!/usr/bin/env python3
"""Provider-independent appointment negotiation for Ava.

The workflow produces typed intentions only. It never reads or writes a calendar,
sends a message, or contacts a provider directly. Concrete adapters remain responsible
for those effects after office-manager policy authorization.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

UTC = dt.timezone.utc
OPAQUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
STATES = {
    "requested",
    "awaiting_availability",
    "ready_to_offer",
    "awaiting_external",
    "needs_owner",
    "ready_to_schedule",
    "scheduled",
    "completed",
    "cancelled",
}


class AppointmentWorkflowError(RuntimeError):
    pass


def _utc(value: str, field_name: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise AppointmentWorkflowError(f"{field_name} is required")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppointmentWorkflowError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AppointmentWorkflowError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _opaque(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not OPAQUE_RE.fullmatch(value):
        raise AppointmentWorkflowError(f"{field_name} must be an opaque identifier")
    return value


@dataclass(frozen=True)
class CandidateSlot:
    slot_id: str
    start_at_utc: str
    end_at_utc: str
    source: str = "calendar"

    def validate(self) -> "CandidateSlot":
        _opaque(self.slot_id, "slot_id")
        start = _utc(self.start_at_utc, "start_at_utc")
        end = _utc(self.end_at_utc, "end_at_utc")
        if end <= start:
            raise AppointmentWorkflowError("appointment slot end must follow start")
        if end - start > dt.timedelta(hours=12):
            raise AppointmentWorkflowError("appointment slot duration is out of bounds")
        if self.source not in {"calendar", "external", "owner"}:
            raise AppointmentWorkflowError("appointment slot source is invalid")
        return self

    def public(self) -> dict[str, str]:
        self.validate()
        return {
            "slot_id": self.slot_id,
            "start_at_utc": _iso(_utc(self.start_at_utc, "start_at_utc")),
            "end_at_utc": _iso(_utc(self.end_at_utc, "end_at_utc")),
            "source": self.source,
        }


@dataclass(frozen=True)
class SchedulingPreferences:
    earliest_hour_local: int | None = None
    latest_hour_local: int | None = None
    preferred_weekdays: tuple[int, ...] = ()
    minimum_buffer_minutes: int = 0

    def validate(self) -> "SchedulingPreferences":
        for name, value in (("earliest_hour_local", self.earliest_hour_local), ("latest_hour_local", self.latest_hour_local)):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 23):
                raise AppointmentWorkflowError(f"{name} is invalid")
        if self.earliest_hour_local is not None and self.latest_hour_local is not None and self.latest_hour_local <= self.earliest_hour_local:
            raise AppointmentWorkflowError("latest appointment hour must follow earliest hour")
        if any(not isinstance(day, int) or isinstance(day, bool) or not 0 <= day <= 6 for day in self.preferred_weekdays):
            raise AppointmentWorkflowError("preferred weekday is invalid")
        if not isinstance(self.minimum_buffer_minutes, int) or isinstance(self.minimum_buffer_minutes, bool) or not 0 <= self.minimum_buffer_minutes <= 720:
            raise AppointmentWorkflowError("minimum buffer is invalid")
        return self


@dataclass
class AppointmentWorkflow:
    work_item_id: str
    contact_ref: str
    purpose: str
    timezone: str
    duration_minutes: int
    preferences: SchedulingPreferences = field(default_factory=SchedulingPreferences)
    state: str = "requested"
    workflow_id: str = field(default_factory=lambda: "appt-" + uuid.uuid4().hex)
    candidate_slots: list[CandidateSlot] = field(default_factory=list)
    offered_slot_ids: list[str] = field(default_factory=list)
    selected_slot_id: str | None = None
    calendar_event_ref: str | None = None

    def __post_init__(self) -> None:
        _opaque(self.work_item_id, "work_item_id")
        _opaque(self.contact_ref, "contact_ref")
        if not isinstance(self.purpose, str) or not self.purpose.strip() or len(self.purpose.encode("utf-8")) > 2000:
            raise AppointmentWorkflowError("appointment purpose is invalid")
        if not isinstance(self.timezone, str) or not self.timezone.strip() or len(self.timezone) > 128:
            raise AppointmentWorkflowError("appointment timezone is invalid")
        if not isinstance(self.duration_minutes, int) or isinstance(self.duration_minutes, bool) or not 5 <= self.duration_minutes <= 720:
            raise AppointmentWorkflowError("appointment duration is invalid")
        self.preferences.validate()
        if self.state not in STATES:
            raise AppointmentWorkflowError("appointment state is invalid")

    def _transition(self, target: str) -> None:
        allowed = {
            "requested": {"awaiting_availability", "cancelled"},
            "awaiting_availability": {"ready_to_offer", "needs_owner", "cancelled"},
            "ready_to_offer": {"awaiting_external", "needs_owner", "cancelled"},
            "awaiting_external": {"ready_to_schedule", "ready_to_offer", "needs_owner", "cancelled"},
            "needs_owner": {"awaiting_availability", "ready_to_offer", "ready_to_schedule", "cancelled"},
            "ready_to_schedule": {"scheduled", "needs_owner", "cancelled"},
            "scheduled": {"completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if target not in allowed[self.state]:
            raise AppointmentWorkflowError(f"invalid appointment transition {self.state} -> {target}")
        self.state = target

    def request_availability_action(self) -> dict[str, Any]:
        if self.state != "requested":
            raise AppointmentWorkflowError("availability can only be requested once from requested state")
        self._transition("awaiting_availability")
        return {
            "capability": "calendar.read",
            "summary": "Read bounded availability for appointment scheduling",
            "parameters": {
                "workflow_id": self.workflow_id,
                "duration_minutes": self.duration_minutes,
                "timezone": self.timezone,
            },
        }

    def ingest_availability(self, slots: list[CandidateSlot]) -> list[dict[str, str]]:
        if self.state != "awaiting_availability":
            raise AppointmentWorkflowError("availability is not expected in the current state")
        if not isinstance(slots, list) or len(slots) > 100:
            raise AppointmentWorkflowError("appointment slot list is invalid")
        validated = [slot.validate() for slot in slots]
        unique = {slot.slot_id: slot for slot in validated}
        ranked = sorted(unique.values(), key=lambda slot: _utc(slot.start_at_utc, "start_at_utc"))
        self.candidate_slots = ranked
        if not ranked:
            self._transition("needs_owner")
            return []
        self._transition("ready_to_offer")
        return [slot.public() for slot in ranked]

    def prepare_offer_action(self, slot_ids: list[str]) -> dict[str, Any]:
        if self.state != "ready_to_offer":
            raise AppointmentWorkflowError("appointment slots are not ready to offer")
        if not isinstance(slot_ids, list) or not 1 <= len(slot_ids) <= 5:
            raise AppointmentWorkflowError("offer must contain between one and five slots")
        available = {slot.slot_id for slot in self.candidate_slots}
        normalized = [_opaque(value, "slot_id") for value in slot_ids]
        if len(set(normalized)) != len(normalized) or any(value not in available for value in normalized):
            raise AppointmentWorkflowError("offer references an unavailable or duplicate slot")
        self.offered_slot_ids = normalized
        self._transition("awaiting_external")
        return {
            "capability": "communication.draft",
            "summary": "Prepare appointment time options for the external party",
            "parameters": {
                "workflow_id": self.workflow_id,
                "contact_ref": self.contact_ref,
                "slot_ids": normalized,
            },
        }

    def record_external_selection(self, slot_id: str) -> dict[str, Any]:
        if self.state != "awaiting_external":
            raise AppointmentWorkflowError("external appointment selection is not expected")
        slot_id = _opaque(slot_id, "slot_id")
        if slot_id not in self.offered_slot_ids:
            raise AppointmentWorkflowError("external party selected a slot that was not offered")
        self.selected_slot_id = slot_id
        self._transition("ready_to_schedule")
        slot = next(slot for slot in self.candidate_slots if slot.slot_id == slot_id)
        return {
            "capability": "calendar.event.create",
            "summary": "Create the confirmed appointment",
            "parameters": {
                "workflow_id": self.workflow_id,
                "contact_ref": self.contact_ref,
                "slot": slot.public(),
                "purpose": self.purpose,
                "timezone": self.timezone,
            },
        }

    def mark_scheduled(self, calendar_event_ref: str) -> dict[str, Any]:
        if self.state != "ready_to_schedule":
            raise AppointmentWorkflowError("appointment is not ready to be marked scheduled")
        self.calendar_event_ref = _opaque(calendar_event_ref, "calendar_event_ref")
        self._transition("scheduled")
        return self.public()

    def complete(self) -> dict[str, Any]:
        self._transition("completed")
        return self.public()

    def cancel(self) -> dict[str, Any]:
        if self.state in {"completed", "cancelled"}:
            raise AppointmentWorkflowError("appointment workflow is already terminal")
        self._transition("cancelled")
        return self.public()

    def public(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "work_item_id": self.work_item_id,
            "contact_ref": self.contact_ref,
            "state": self.state,
            "timezone": self.timezone,
            "duration_minutes": self.duration_minutes,
            "candidate_slot_ids": [slot.slot_id for slot in self.candidate_slots],
            "offered_slot_ids": list(self.offered_slot_ids),
            "selected_slot_id": self.selected_slot_id,
            "calendar_event_ref": self.calendar_event_ref,
        }
