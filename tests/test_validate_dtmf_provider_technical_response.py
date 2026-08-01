#!/usr/bin/env python3
"""Regression tests for DTMF provider technical-response intake."""

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools/telephony/validate_dtmf_provider_technical_response.py"
EXAMPLE_PATH = ROOT / "examples/telephony/dtmf-provider-technical-response.example.json"
SCHEMA_PATH = ROOT / "schemas/telephony/dtmf-provider-technical-response.schema.json"

spec = importlib.util.spec_from_file_location(
    "validate_dtmf_provider_technical_response", str(VALIDATOR_PATH)
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def expect_failure(record, expected_fragment):
    try:
        validator.validate_record(record)
    except validator.ValidationError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                "expected %r in validation error %r" % (expected_fragment, str(exc))
            )
    else:
        raise AssertionError("record unexpectedly passed validation")


def reviewed_record():
    record = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    record["response_state"] = "reviewed"
    record["response_evidence"]["received_at"] = "2026-08-01T20:45:00Z"
    record["response_evidence"]["summary"] = (
        "A restricted provider response was reviewed and summarized without identifiers."
    )
    answer = record["questions"][0]
    answer["answer_status"] = "documented"
    answer["evidence_strength"] = "service-guarantee"
    answer["scopes"] = ["outbound"]
    answer["details"] = (
        "Outbound RTP-event behavior is directly documented for the reviewed service scope."
    )
    answer["evidence_refs"] = [record["response_evidence"]["evidence_id"]]
    record["decision"]["matrix_update_allowed"] = True
    record["decision"]["notes"] = (
        "Only the explicitly scoped service-guarantee answer may be considered for promotion."
    )
    return record


def main():
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    validator.validate_record(example)
    assert schema["title"] == "WW.CX DTMF Provider Technical Response"
    assert example["response_state"] == "pending"
    assert example["decision"]["matrix_update_allowed"] is False
    assert example["decision"]["live_test_authorized"] is False
    assert len(example["questions"]) == 9
    assert {item["question_id"] for item in example["questions"]} == validator.QUESTION_IDS

    reviewed = reviewed_record()
    validator.validate_record(reviewed)

    duplicate = copy.deepcopy(example)
    duplicate["questions"][1]["question_id"] = duplicate["questions"][0]["question_id"]
    expect_failure(duplicate, "duplicate question_id")

    pending_answer = copy.deepcopy(example)
    pending_answer["questions"][0]["answer_status"] = "documented"
    pending_answer["questions"][0]["evidence_strength"] = "service-guarantee"
    pending_answer["questions"][0]["scopes"] = ["outbound"]
    pending_answer["questions"][0]["evidence_refs"] = [
        pending_answer["response_evidence"]["evidence_id"]
    ]
    expect_failure(pending_answer, "cannot be answered while response_state is pending")

    leaked_email = copy.deepcopy(example)
    leaked_email["questions"][0]["details"] = "Contact operator@example.test for details."
    expect_failure(leaked_email, "contains an email address")

    guidance_promotion = reviewed_record()
    guidance_promotion["questions"][0]["evidence_strength"] = "configuration-guidance"
    expect_failure(
        guidance_promotion,
        "matrix update requires at least one scoped service-guarantee answer",
    )

    unknown_guarantee = reviewed_record()
    unknown_guarantee["questions"][0]["scopes"] = ["unknown"]
    expect_failure(unknown_guarantee, "service guarantee requires a concrete scope")

    invalid_test_required = copy.deepcopy(example)
    invalid_test_required["response_state"] = "received"
    invalid_test_required["response_evidence"]["received_at"] = "2026-08-01T20:45:00Z"
    invalid_test_required["questions"][0]["answer_status"] = "test-required"
    invalid_test_required["questions"][0]["evidence_strength"] = "best-effort"
    invalid_test_required["questions"][0]["scopes"] = ["outbound"]
    invalid_test_required["questions"][0]["evidence_refs"] = [
        invalid_test_required["response_evidence"]["evidence_id"]
    ]
    expect_failure(
        invalid_test_required,
        "test-required answer must use controlled-test-only strength",
    )

    unauthorized_live_test = copy.deepcopy(example)
    unauthorized_live_test["decision"]["live_test_authorized"] = True
    expect_failure(unauthorized_live_test, "technical response cannot authorize a live test")

    print("DTMF provider technical response intake tests passed")


if __name__ == "__main__":
    main()
