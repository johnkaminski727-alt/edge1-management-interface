#!/usr/bin/env python3
"""Validate a privacy-minimized DTMF provider evidence record."""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SIP_URI_RE = re.compile(r"(?i)\bsips?:[^\s]+")
ISO_DATE_TOKEN_RE = re.compile(
    r"(?<![0-9])"
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"(?:T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?"
    r"(?![0-9])"
)
LONG_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\+?[0-9][0-9 ()-]{5,}[0-9](?![A-Za-z0-9])")
QUERY_URL_RE = re.compile(r"(?i)https?://[^\s?#]+\?[^\s]+")

TOP_LEVEL_KEYS = {
    "schema_version",
    "provider_id",
    "route_id",
    "direction",
    "review_state",
    "evidence",
    "capabilities",
    "privacy",
    "decision",
}

DIRECTIONS = {"inbound", "outbound", "bidirectional"}
REVIEW_STATES = {"unverified", "provider-documented", "controlled-test-reviewed"}
SOURCE_TYPES = {
    "provider-public-documentation",
    "provider-private-correspondence",
    "provider-portal-record",
    "executed-agreement",
    "controlled-test-record",
}
RETENTION_CLASSES = {"external-private", "internal-restricted", "repository-public"}
CAPABILITY_STATUSES = {
    "unknown",
    "documented",
    "controlled-test-passed",
    "controlled-test-failed",
}
CARRIER_STATES = {
    "unverified",
    "partially-documented",
    "documented",
    "controlled-test-passed",
    "controlled-test-failed",
}
EVENT_RANGES = {"unknown", "0-11", "0-15", "other"}
CAPABILITY_KEYS = {"rfc4733", "sip_info", "inband", "extended_abcd"}
PRIVACY_KEYS = {
    "provider_name_retained",
    "account_identifier_retained",
    "credential_retained",
    "telephone_number_retained",
    "sip_uri_retained",
    "personal_identifier_retained",
}
PROHIBITED_KEYS = {
    "provider_name",
    "provider_legal_name",
    "account",
    "account_id",
    "account_number",
    "customer_id",
    "username",
    "user_name",
    "password",
    "secret",
    "token",
    "api_key",
    "credential",
    "credentials",
    "telephone_number",
    "phone_number",
    "did",
    "sip_uri",
    "email",
    "email_address",
    "personal_name",
    "contact_name",
    "street_address",
    "postal_address",
    "tax_identifier",
    "government_identifier",
}


class ValidationError(Exception):
    """Raised when an evidence record violates the intake contract."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def exact_keys(value, expected, location):
    require(isinstance(value, dict), "%s must be an object" % location)
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    require(not missing, "%s is missing keys: %s" % (location, ", ".join(missing)))
    require(not extra, "%s has unsupported keys: %s" % (location, ", ".join(extra)))


def validate_identifier(value, location, max_length=96):
    require(isinstance(value, str), "%s must be a string" % location)
    require(len(value) <= max_length, "%s is too long" % location)
    require(ID_RE.fullmatch(value) is not None, "%s must be a sanitized lowercase identifier" % location)


def validate_timestamp(value, location):
    require(value is None or isinstance(value, str), "%s must be null or an RFC 3339 string" % location)
    if value is None:
        return
    require(value.endswith("Z"), "%s must use UTC with a trailing Z" % location)
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValidationError("%s is not a valid UTC timestamp: %s" % (location, exc))


def strip_valid_iso_date_tokens(value):
    """Mask valid ISO dates and UTC timestamps before long-number scanning."""

    def replace(match):
        token = match.group(0)
        fmt = "%Y-%m-%dT%H:%M:%SZ" if "T" in token else "%Y-%m-%d"
        try:
            datetime.datetime.strptime(token, fmt)
        except ValueError:
            return token
        return " " * len(token)

    return ISO_DATE_TOKEN_RE.sub(replace, value)


def walk_for_prohibited_keys(value, location="record"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in PROHIBITED_KEYS:
                raise ValidationError("%s contains prohibited key: %s" % (location, key))
            walk_for_prohibited_keys(child, "%s.%s" % (location, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_for_prohibited_keys(child, "%s[%d]" % (location, index))


def walk_for_sensitive_text(value, location="record"):
    if isinstance(value, dict):
        for key, child in value.items():
            walk_for_sensitive_text(child, "%s.%s" % (location, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_for_sensitive_text(child, "%s[%d]" % (location, index))
    elif isinstance(value, str):
        number_scan_value = strip_valid_iso_date_tokens(value)
        require(EMAIL_RE.search(value) is None, "%s contains an email address" % location)
        require(SIP_URI_RE.search(value) is None, "%s contains a SIP URI" % location)
        require(LONG_NUMBER_RE.search(number_scan_value) is None,
                "%s contains a telephone, account, or personal number" % location)
        require(QUERY_URL_RE.search(value) is None, "%s contains a URL with a query string" % location)
        require("-----BEGIN " not in value, "%s contains key or certificate material" % location)


def validate_evidence(records):
    require(isinstance(records, list), "evidence must be an array")
    evidence_by_id = {}
    expected_keys = {"evidence_id", "source_type", "reviewed_at", "retention", "summary"}

    for index, record in enumerate(records):
        location = "evidence[%d]" % index
        exact_keys(record, expected_keys, location)
        validate_identifier(record["evidence_id"], "%s.evidence_id" % location)
        require(record["evidence_id"] not in evidence_by_id, "duplicate evidence_id: %s" % record["evidence_id"])
        require(record["source_type"] in SOURCE_TYPES, "%s.source_type is unsupported" % location)
        validate_timestamp(record["reviewed_at"], "%s.reviewed_at" % location)
        require(record["retention"] in RETENTION_CLASSES, "%s.retention is unsupported" % location)
        require(isinstance(record["summary"], str) and 1 <= len(record["summary"]) <= 500,
                "%s.summary must contain 1 to 500 characters" % location)

        if record["source_type"] in {"provider-private-correspondence", "provider-portal-record", "executed-agreement"}:
            require(record["retention"] != "repository-public",
                    "%s private provider evidence cannot use repository-public retention" % location)
        if record["source_type"] == "controlled-test-record":
            require(record["retention"] == "internal-restricted",
                    "%s controlled-test evidence must remain internal-restricted" % location)

        evidence_by_id[record["evidence_id"]] = record

    return evidence_by_id


def validate_refs(refs, location, evidence_by_id, status):
    require(isinstance(refs, list), "%s must be an array" % location)
    require(len(refs) == len(set(refs)), "%s contains duplicate references" % location)
    for ref in refs:
        validate_identifier(ref, "%s reference" % location)
        require(ref in evidence_by_id, "%s references unknown evidence_id: %s" % (location, ref))

    if status == "unknown":
        require(not refs, "%s must be empty while capability status is unknown" % location)
    else:
        require(bool(refs), "%s requires evidence for status %s" % (location, status))


def validate_capability(name, capability, evidence_by_id):
    if name == "rfc4733":
        expected = {"status", "event_range", "evidence_refs"}
    elif name == "inband":
        expected = {"status", "codec_constraints", "evidence_refs"}
    else:
        expected = {"status", "evidence_refs"}

    location = "capabilities.%s" % name
    exact_keys(capability, expected, location)
    status = capability["status"]
    require(status in CAPABILITY_STATUSES, "%s.status is unsupported" % location)
    validate_refs(capability["evidence_refs"], "%s.evidence_refs" % location, evidence_by_id, status)

    if name == "rfc4733":
        require(capability["event_range"] in EVENT_RANGES, "%s.event_range is unsupported" % location)
        if status == "unknown":
            require(capability["event_range"] == "unknown",
                    "%s.event_range must remain unknown without capability evidence" % location)
        elif status == "documented":
            require(capability["event_range"] != "unknown",
                    "%s documented RFC 4733 support requires an event range" % location)

    if name == "inband":
        codecs = capability["codec_constraints"]
        require(isinstance(codecs, list), "%s.codec_constraints must be an array" % location)
        require(len(codecs) == len(set(codecs)), "%s.codec_constraints contains duplicates" % location)
        for codec in codecs:
            require(isinstance(codec, str) and re.fullmatch(r"[A-Za-z0-9._+-]{1,32}", codec),
                    "%s has an invalid codec constraint" % location)
        if status == "unknown":
            require(not codecs, "%s codec constraints require capability evidence" % location)

    refs = capability["evidence_refs"]
    if status.startswith("controlled-test-"):
        for ref in refs:
            require(evidence_by_id[ref]["source_type"] == "controlled-test-record",
                    "%s controlled-test status requires controlled-test-record evidence" % location)
    elif status == "documented":
        for ref in refs:
            require(evidence_by_id[ref]["source_type"] != "controlled-test-record",
                    "%s documented status must use provider or agreement evidence" % location)


def validate_record(record):
    exact_keys(record, TOP_LEVEL_KEYS, "record")
    require(record["schema_version"] == 1, "schema_version must be 1")
    validate_identifier(record["provider_id"], "provider_id", 64)
    validate_identifier(record["route_id"], "route_id", 64)
    require(record["direction"] in DIRECTIONS, "direction is unsupported")
    require(record["review_state"] in REVIEW_STATES, "review_state is unsupported")

    walk_for_prohibited_keys(record)
    walk_for_sensitive_text(record)

    evidence_by_id = validate_evidence(record["evidence"])

    exact_keys(record["capabilities"], CAPABILITY_KEYS, "capabilities")
    for name in sorted(CAPABILITY_KEYS):
        validate_capability(name, record["capabilities"][name], evidence_by_id)

    exact_keys(record["privacy"], PRIVACY_KEYS, "privacy")
    for key in sorted(PRIVACY_KEYS):
        require(record["privacy"][key] is False, "privacy.%s must be false" % key)

    decision_keys = {"matrix_eligible", "carrier_interoperability", "live_test_authorized", "notes"}
    exact_keys(record["decision"], decision_keys, "decision")
    decision = record["decision"]
    require(isinstance(decision["matrix_eligible"], bool), "decision.matrix_eligible must be boolean")
    require(decision["carrier_interoperability"] in CARRIER_STATES,
            "decision.carrier_interoperability is unsupported")
    require(decision["live_test_authorized"] is False,
            "decision.live_test_authorized must remain false in an evidence intake record")
    require(isinstance(decision["notes"], str) and 1 <= len(decision["notes"]) <= 500,
            "decision.notes must contain 1 to 500 characters")

    statuses = [record["capabilities"][name]["status"] for name in sorted(CAPABILITY_KEYS)]
    known_statuses = [status for status in statuses if status != "unknown"]
    test_statuses = [status for status in statuses if status.startswith("controlled-test-")]

    if record["review_state"] == "unverified":
        require(not known_statuses, "unverified review_state cannot contain capability claims")
    elif record["review_state"] == "provider-documented":
        require(bool(known_statuses), "provider-documented review_state requires a capability claim")
        require(not test_statuses, "provider-documented review_state cannot contain controlled-test claims")
    elif record["review_state"] == "controlled-test-reviewed":
        require(bool(test_statuses), "controlled-test-reviewed review_state requires controlled-test evidence")

    if decision["matrix_eligible"]:
        require(bool(known_statuses), "matrix_eligible requires at least one supported capability")
        require(decision["carrier_interoperability"] != "unverified",
                "matrix_eligible cannot use unverified carrier_interoperability")
    else:
        require(decision["carrier_interoperability"] == "unverified" or not known_statuses,
                "an ineligible record with capability claims must explain a non-unverified evidence state")

    if not known_statuses:
        require(decision["matrix_eligible"] is False,
                "an all-unknown record cannot be matrix eligible")
        require(decision["carrier_interoperability"] == "unverified",
                "an all-unknown record must keep carrier interoperability unverified")

    if "controlled-test-passed" in statuses:
        require(decision["carrier_interoperability"] in {"controlled-test-passed", "partially-documented"},
                "passed controlled-test evidence must be reflected in the decision")
    if "controlled-test-failed" in statuses:
        require(decision["carrier_interoperability"] in {"controlled-test-failed", "partially-documented"},
                "failed controlled-test evidence must be reflected in the decision")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="JSON provider evidence record")
    args = parser.parse_args(argv)

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        validate_record(record)
    except (OSError, ValueError, ValidationError) as exc:
        print("DTMF provider evidence validation failed: %s" % exc, file=sys.stderr)
        return 1

    print("DTMF provider evidence validation passed: %s" % args.record)
    print("provider_id=%s" % record["provider_id"])
    print("route_id=%s" % record["route_id"])
    print("review_state=%s" % record["review_state"])
    print("matrix_eligible=%s" % str(record["decision"]["matrix_eligible"]).lower())
    print("carrier_interoperability=%s" % record["decision"]["carrier_interoperability"])
    print("live_test_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
