#!/usr/bin/env python3
"""Validate a privacy-minimized DTMF provider technical-response worksheet."""

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_VALIDATOR_PATH = ROOT / "tools/telephony/validate_dtmf_provider_evidence.py"

spec = importlib.util.spec_from_file_location(
    "validate_dtmf_provider_evidence", str(BASE_VALIDATOR_PATH)
)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ValidationError = base.ValidationError
require = base.require
exact_keys = base.exact_keys
validate_identifier = base.validate_identifier
validate_timestamp = base.validate_timestamp
walk_for_prohibited_keys = base.walk_for_prohibited_keys
walk_for_sensitive_text = base.walk_for_sensitive_text

TOP_LEVEL_KEYS = {
    "schema_version",
    "provider_id",
    "route_id",
    "response_state",
    "response_evidence",
    "questions",
    "privacy",
    "decision",
}
QUESTION_IDS = {
    "rfc4733-directionality",
    "rfc4733-event-range",
    "extended-abcd",
    "sip-info",
    "inband-codecs",
    "auto-fallback",
    "route-exceptions",
    "diagnostic-scope",
    "asterisk-pjsip-settings",
}
RESPONSE_STATES = {"pending", "received", "reviewed"}
ANSWER_STATUSES = {
    "unanswered",
    "documented",
    "not-supported",
    "conditional",
    "test-required",
}
EVIDENCE_STRENGTHS = {
    "none",
    "service-guarantee",
    "best-effort",
    "configuration-guidance",
    "controlled-test-only",
}
SCOPES = {"account-level", "inbound", "outbound", "internal", "unknown"}
PRIVACY_KEYS = {
    "provider_name_retained",
    "account_identifier_retained",
    "credential_retained",
    "telephone_number_retained",
    "sip_uri_retained",
    "personal_identifier_retained",
}
QUESTION_KEYS = {
    "question_id",
    "answer_status",
    "evidence_strength",
    "scopes",
    "details",
    "evidence_refs",
}


def validate_response_evidence(value, response_state):
    expected = {
        "evidence_id",
        "source_type",
        "retention",
        "received_at",
        "summary",
    }
    exact_keys(value, expected, "response_evidence")
    validate_identifier(value["evidence_id"], "response_evidence.evidence_id")
    require(
        value["source_type"] == "provider-private-correspondence",
        "response_evidence.source_type must be provider-private-correspondence",
    )
    require(
        value["retention"] == "internal-restricted",
        "response_evidence.retention must be internal-restricted",
    )
    validate_timestamp(value["received_at"], "response_evidence.received_at")
    require(
        isinstance(value["summary"], str) and 1 <= len(value["summary"]) <= 500,
        "response_evidence.summary must contain 1 to 500 characters",
    )
    if response_state == "pending":
        require(
            value["received_at"] is None,
            "pending response_evidence.received_at must be null",
        )
    else:
        require(
            value["received_at"] is not None,
            "received or reviewed response requires response_evidence.received_at",
        )
    return value["evidence_id"]


def validate_question(question, index, evidence_id, response_state):
    location = "questions[%d]" % index
    exact_keys(question, QUESTION_KEYS, location)
    question_id = question["question_id"]
    require(question_id in QUESTION_IDS, "%s.question_id is unsupported" % location)

    answer_status = question["answer_status"]
    strength = question["evidence_strength"]
    require(answer_status in ANSWER_STATUSES, "%s.answer_status is unsupported" % location)
    require(strength in EVIDENCE_STRENGTHS, "%s.evidence_strength is unsupported" % location)

    scopes = question["scopes"]
    require(isinstance(scopes, list) and scopes, "%s.scopes must be a non-empty array" % location)
    require(len(scopes) == len(set(scopes)), "%s.scopes contains duplicates" % location)
    require(set(scopes) <= SCOPES, "%s.scopes contains an unsupported value" % location)
    require(
        not ("unknown" in scopes and len(scopes) > 1),
        "%s.scopes cannot mix unknown with a concrete scope" % location,
    )

    details = question["details"]
    require(
        isinstance(details, str) and 1 <= len(details) <= 500,
        "%s.details must contain 1 to 500 characters" % location,
    )

    refs = question["evidence_refs"]
    require(isinstance(refs, list), "%s.evidence_refs must be an array" % location)
    require(len(refs) == len(set(refs)), "%s.evidence_refs contains duplicates" % location)
    for ref in refs:
        validate_identifier(ref, "%s.evidence_refs reference" % location)
        require(ref == evidence_id, "%s references unsupported evidence: %s" % (location, ref))

    if answer_status == "unanswered":
        require(strength == "none", "%s unanswered item must use evidence_strength none" % location)
        require(scopes == ["unknown"], "%s unanswered item must use only unknown scope" % location)
        require(not refs, "%s unanswered item cannot reference evidence" % location)
    else:
        require(response_state != "pending", "%s cannot be answered while response_state is pending" % location)
        require(strength != "none", "%s answered item requires evidence strength" % location)
        require(refs == [evidence_id], "%s answered item must reference the retained response" % location)

    if answer_status == "test-required":
        require(
            strength == "controlled-test-only",
            "%s test-required answer must use controlled-test-only strength" % location,
        )
    if strength == "controlled-test-only":
        require(
            answer_status == "test-required",
            "%s controlled-test-only strength requires test-required status" % location,
        )
    if strength == "service-guarantee":
        require(
            "unknown" not in scopes,
            "%s service guarantee requires a concrete scope" % location,
        )

    return question_id


def validate_record(record):
    exact_keys(record, TOP_LEVEL_KEYS, "record")
    walk_for_prohibited_keys(record)
    walk_for_sensitive_text(record)

    require(record["schema_version"] == 1, "schema_version must be 1")
    validate_identifier(record["provider_id"], "provider_id")
    validate_identifier(record["route_id"], "route_id")

    response_state = record["response_state"]
    require(response_state in RESPONSE_STATES, "response_state is unsupported")
    evidence_id = validate_response_evidence(record["response_evidence"], response_state)

    questions = record["questions"]
    require(isinstance(questions, list), "questions must be an array")
    require(len(questions) == len(QUESTION_IDS), "questions must contain every required question exactly once")
    observed = []
    for index, question in enumerate(questions):
        observed.append(validate_question(question, index, evidence_id, response_state))
    require(len(observed) == len(set(observed)), "questions contains duplicate question_id values")
    require(set(observed) == QUESTION_IDS, "questions does not contain the complete required question set")

    exact_keys(record["privacy"], PRIVACY_KEYS, "privacy")
    for key, value in record["privacy"].items():
        require(value is False, "privacy.%s must be false" % key)

    exact_keys(
        record["decision"],
        {"matrix_update_allowed", "live_test_authorized", "notes"},
        "decision",
    )
    matrix_update_allowed = record["decision"]["matrix_update_allowed"]
    require(isinstance(matrix_update_allowed, bool), "decision.matrix_update_allowed must be boolean")
    require(record["decision"]["live_test_authorized"] is False, "technical response cannot authorize a live test")
    require(
        isinstance(record["decision"]["notes"], str)
        and 1 <= len(record["decision"]["notes"]) <= 500,
        "decision.notes must contain 1 to 500 characters",
    )

    eligible_answers = [
        question
        for question in questions
        if question["answer_status"] in {"documented", "conditional"}
        and question["evidence_strength"] == "service-guarantee"
        and "unknown" not in question["scopes"]
    ]

    if response_state != "reviewed":
        require(
            matrix_update_allowed is False,
            "matrix update cannot be allowed before the response is reviewed",
        )
    if matrix_update_allowed:
        require(
            bool(eligible_answers),
            "matrix update requires at least one scoped service-guarantee answer",
        )

    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args(argv)

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        validate_record(record)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print("DTMF provider technical response validation failed: %s" % exc, file=sys.stderr)
        return 1

    print("DTMF provider technical response validation passed: %s" % args.record)
    print("provider_id=%s" % record["provider_id"])
    print("route_id=%s" % record["route_id"])
    print("response_state=%s" % record["response_state"])
    print("matrix_update_allowed=%s" % str(record["decision"]["matrix_update_allowed"]).lower())
    print("live_test_authorized=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
