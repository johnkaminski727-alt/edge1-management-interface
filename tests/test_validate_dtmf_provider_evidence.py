#!/usr/bin/env python3
"""Regression tests for privacy-safe DTMF provider evidence intake."""

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools/telephony/validate_dtmf_provider_evidence.py"
EXAMPLE_PATH = ROOT / "examples/telephony/dtmf-provider-evidence.example.json"
SCHEMA_PATH = ROOT / "schemas/telephony/dtmf-provider-evidence.schema.json"

spec = importlib.util.spec_from_file_location("validate_dtmf_provider_evidence", str(VALIDATOR_PATH))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def expect_failure(record, expected_fragment):
    try:
        validator.validate_record(record)
    except validator.ValidationError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError("expected %r in validation error %r" % (expected_fragment, str(exc)))
    else:
        raise AssertionError("record unexpectedly passed validation")


def main():
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    validator.validate_record(example)

    assert schema["title"] == "WW.CX DTMF Provider Evidence Record"
    assert schema["properties"]["privacy"]["properties"]["credential_retained"]["const"] is False
    assert example["review_state"] == "unverified"
    assert example["decision"]["matrix_eligible"] is False
    assert example["decision"]["carrier_interoperability"] == "unverified"
    assert example["decision"]["live_test_authorized"] is False

    dated_summary = copy.deepcopy(example)
    dated_summary["evidence"][0]["summary"] = (
        "Reviewed on 2026-08-01; no provider-specific DTMF transport capability was documented."
    )
    validator.validate_record(dated_summary)

    leaked_email = copy.deepcopy(example)
    leaked_email["decision"]["notes"] = "Contact operator@example.test for the provider record."
    expect_failure(leaked_email, "contains an email address")

    leaked_number = copy.deepcopy(example)
    leaked_number["evidence"][0]["summary"] = "Customer account 123456789 was activated."
    expect_failure(leaked_number, "contains a telephone, account, or personal number")

    dated_leaked_number = copy.deepcopy(example)
    dated_leaked_number["evidence"][0]["summary"] = (
        "Reviewed on 2026-08-01 for customer account 123456789."
    )
    expect_failure(dated_leaked_number, "contains a telephone, account, or personal number")

    private_public = copy.deepcopy(example)
    private_public["evidence"][0]["retention"] = "repository-public"
    expect_failure(private_public, "private provider evidence cannot use repository-public retention")

    undocumented_claim = copy.deepcopy(example)
    undocumented_claim["review_state"] = "provider-documented"
    undocumented_claim["capabilities"]["rfc4733"]["status"] = "documented"
    undocumented_claim["capabilities"]["rfc4733"]["event_range"] = "0-15"
    expect_failure(undocumented_claim, "requires evidence for status documented")

    invalid_test_claim = copy.deepcopy(example)
    invalid_test_claim["review_state"] = "controlled-test-reviewed"
    invalid_test_claim["capabilities"]["sip_info"]["status"] = "controlled-test-passed"
    invalid_test_claim["capabilities"]["sip_info"]["evidence_refs"] = ["general-pbx-compatibility-001"]
    expect_failure(invalid_test_claim, "controlled-test status requires controlled-test-record evidence")

    invalid_matrix_promotion = copy.deepcopy(example)
    invalid_matrix_promotion["decision"]["matrix_eligible"] = True
    invalid_matrix_promotion["decision"]["carrier_interoperability"] = "documented"
    expect_failure(invalid_matrix_promotion, "matrix_eligible requires at least one supported capability")

    documented = copy.deepcopy(example)
    documented["review_state"] = "provider-documented"
    documented["capabilities"]["rfc4733"] = {
        "status": "documented",
        "event_range": "0-15",
        "evidence_refs": ["general-pbx-compatibility-001"],
    }
    documented["decision"] = {
        "matrix_eligible": True,
        "carrier_interoperability": "partially-documented",
        "live_test_authorized": False,
        "notes": "Only RFC 4733 and its event range are supported by the retained provider evidence.",
    }
    validator.validate_record(documented)

    print("DTMF provider evidence intake tests passed")


if __name__ == "__main__":
    main()
