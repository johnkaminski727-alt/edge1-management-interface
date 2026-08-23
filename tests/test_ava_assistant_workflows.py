#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from server.ava_appointment_workflow import (
    AppointmentWorkflow,
    AppointmentWorkflowError,
    CandidateSlot,
    SchedulingPreferences,
)
from server.ava_attendant_session import AttendantSession, AttendantSessionError, MediaPolicy


class AvaAppointmentWorkflowTests(unittest.TestCase):
    def _workflow(self) -> AppointmentWorkflow:
        return AppointmentWorkflow(
            work_item_id="work-12345678",
            contact_ref="contact-dentist",
            purpose="Routine dental appointment",
            timezone="America/Edmonton",
            duration_minutes=60,
            preferences=SchedulingPreferences(
                earliest_hour_local=13,
                latest_hour_local=17,
                preferred_weekdays=(1, 2, 3),
                minimum_buffer_minutes=30,
            ),
        )

    def test_negotiation_produces_typed_actions_without_side_effects(self) -> None:
        flow = self._workflow()
        read = flow.request_availability_action()
        self.assertEqual(read["capability"], "calendar.read")
        slots = flow.ingest_availability([
            CandidateSlot("slot-0002", "2026-08-26T21:00:00Z", "2026-08-26T22:00:00Z"),
            CandidateSlot("slot-0001", "2026-08-25T20:00:00Z", "2026-08-25T21:00:00Z"),
        ])
        self.assertEqual([slot["slot_id"] for slot in slots], ["slot-0001", "slot-0002"])
        offer = flow.prepare_offer_action(["slot-0001", "slot-0002"])
        self.assertEqual(offer["capability"], "communication.draft")
        create = flow.record_external_selection("slot-0002")
        self.assertEqual(create["capability"], "calendar.event.create")
        self.assertEqual(flow.state, "ready_to_schedule")
        scheduled = flow.mark_scheduled("event-12345678")
        self.assertEqual(scheduled["state"], "scheduled")
        self.assertEqual(flow.complete()["state"], "completed")

    def test_external_party_cannot_select_unoffered_slot(self) -> None:
        flow = self._workflow()
        flow.request_availability_action()
        flow.ingest_availability([
            CandidateSlot("slot-0001", "2026-08-25T20:00:00Z", "2026-08-25T21:00:00Z"),
            CandidateSlot("slot-0002", "2026-08-26T20:00:00Z", "2026-08-26T21:00:00Z"),
        ])
        flow.prepare_offer_action(["slot-0001"])
        with self.assertRaises(AppointmentWorkflowError):
            flow.record_external_selection("slot-0002")

    def test_empty_availability_escalates_to_owner(self) -> None:
        flow = self._workflow()
        flow.request_availability_action()
        self.assertEqual(flow.ingest_availability([]), [])
        self.assertEqual(flow.state, "needs_owner")

    def test_slot_must_be_timezone_aware_and_forward(self) -> None:
        with self.assertRaises(AppointmentWorkflowError):
            CandidateSlot("slot-0001", "2026-08-25T10:00:00", "2026-08-25T11:00:00").validate()
        with self.assertRaises(AppointmentWorkflowError):
            CandidateSlot("slot-0001", "2026-08-25T11:00:00Z", "2026-08-25T10:00:00Z").validate()


class AvaAttendantSessionTests(unittest.TestCase):
    def _session(self, *, consent_required: bool = False) -> AttendantSession:
        return AttendantSession(
            call_ref="call-12345678",
            destination_ref="owner-cell-primary",
            work_item_id="work-12345678",
            media_policy=MediaPolicy(
                recording_enabled=True,
                transcription_enabled=True,
                notice_required=True,
                consent_required=consent_required,
            ),
        )

    def test_warm_transfer_keeps_private_consult_isolated(self) -> None:
        session = self._session()
        self.assertEqual(session.begin()["action"], "present_recording_notice")
        session.record_notice_result()
        session.attach_media_refs(transcript_ref="transcript-1234", recording_ref="recording-1234")
        session.set_screening_context(caller_identity_ref="contact-jane", purpose_summary="Equipment return")
        prepare = session.request_warm_transfer()
        self.assertEqual(prepare["capability"], "telephony.transfer.prepare")
        consult = session.begin_private_consult("consult-12345678")
        self.assertEqual(consult["parameters"]["caller_media_joined"], False)
        complete = session.owner_decision("accept")
        self.assertEqual(complete["capability"], "telephony.transfer.complete")
        public = session.mark_bridged("transfer-12345678")
        self.assertEqual(public["state"], "bridged")
        self.assertFalse(public["caller_joined_private_consult"])
        self.assertEqual(session.complete()["state"], "completed")

    def test_decline_does_not_disclose_owner_rejection(self) -> None:
        session = self._session()
        session.begin()
        session.record_notice_result()
        session.set_screening_context(caller_identity_ref=None, purpose_summary="Sales inquiry")
        session.request_warm_transfer()
        session.begin_private_consult("consult-12345678")
        result = session.owner_decision("decline")
        self.assertFalse(result["disclose_owner_decline"])
        resumed = session.resume_screening_after_decline()
        self.assertFalse(resumed["disclose_owner_decline"])
        self.assertEqual(session.state, "screening")

    def test_voicemail_can_follow_owner_decline(self) -> None:
        session = self._session()
        session.begin()
        session.record_notice_result()
        session.set_screening_context(caller_identity_ref="contact-jane", purpose_summary="Callback request")
        session.request_warm_transfer()
        session.begin_private_consult("consult-12345678")
        result = session.owner_decision("voicemail")
        self.assertEqual(result["action"], "take_structured_voicemail")
        self.assertEqual(session.state, "voicemail")

    def test_required_consent_fails_to_deterministic_fallback(self) -> None:
        session = self._session(consent_required=True)
        session.begin()
        result = session.record_notice_result(consent_granted=False)
        self.assertEqual(session.state, "failed")
        self.assertTrue(result["action"].startswith("fallback"))

    def test_cannot_bridge_without_owner_acceptance(self) -> None:
        session = self._session()
        session.begin()
        session.record_notice_result()
        with self.assertRaises(AttendantSessionError):
            session.mark_bridged("transfer-12345678")


class AvaCallRecordSchemaTests(unittest.TestCase):
    def test_schema_requires_privacy_and_integrity_fields(self) -> None:
        path = Path(__file__).parents[1] / "schemas" / "ava" / "call-record.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        segment = schema["properties"]["segments"]["items"]
        self.assertIn("privacy", segment["required"])
        self.assertIn("private_owner_consult", segment["properties"]["kind"]["enum"])
        self.assertIn("private_owner", segment["properties"]["privacy"]["enum"])
        self.assertIn("integrity", schema["required"])


if __name__ == "__main__":
    unittest.main()
