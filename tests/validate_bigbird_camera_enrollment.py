#!/usr/bin/env python3
"""Validate Project Big Bird camera enrollment token/state boundaries."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import bigbird_camera_enrollment as enrollment


def new_db():
    return enrollment.connect(":memory:")


def test_token_digest_and_one_time_use():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "qr", now=1000)
    row = db.execute("SELECT token_digest,token_consumed_at,token_kind FROM camera_enrollments WHERE session_id=?", (created.session_id,)).fetchone()
    assert created.token not in row["token_digest"]
    assert len(row["token_digest"]) == 64
    assert row["token_kind"] == "bigbird_enrollment"
    assert row["token_consumed_at"] is None
    enrollment.consume_enrollment_token(db, created.session_id, created.token, now=1001)
    try:
        enrollment.consume_enrollment_token(db, created.session_id, created.token, now=1002)
    except enrollment.EnrollmentTokenRejected:
        pass
    else:
        raise AssertionError("replay was not rejected")


def test_wrong_token_rejected():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "unknown", now=1000)
    try:
        enrollment.consume_enrollment_token(db, created.session_id, "not-the-token", now=1001)
    except enrollment.EnrollmentTokenRejected:
        pass
    else:
        raise AssertionError("wrong token was accepted")


def test_expiry():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "ap", ttl_seconds=60, now=1000)
    try:
        enrollment.consume_enrollment_token(db, created.session_id, created.token, now=1060)
    except enrollment.EnrollmentExpired:
        pass
    else:
        raise AssertionError("expired token was accepted")
    assert enrollment.get_enrollment(db, created.session_id)["state"] == "EXPIRED"


def test_state_machine_and_device_binding():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "smartconfig", now=1000)
    enrollment.transition(db, created.session_id, "WAITING_FOR_PROVISIONING", now=1001)
    enrollment.transition(db, created.session_id, "WAITING_FOR_CAMERA", now=1002)
    enrollment.record_observed_device(db, created.session_id, ip="192.0.2.10", mac="00:11:22:33:44:55", now=1003)
    assert enrollment.get_enrollment(db, created.session_id)["state"] == "CAMERA_OBSERVED"
    enrollment.bind_device(db, created.session_id, "camera-test-01", now=1004)
    enrollment.transition(db, created.session_id, "FIRST_FRAME_PENDING", now=1005)
    enrollment.transition(db, created.session_id, "FIRST_FRAME_CAPTURED", now=1006)
    assert enrollment.get_enrollment(db, created.session_id)["state"] == "FIRST_FRAME_CAPTURED"


def test_invalid_transition_rejected():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "unknown", now=1000)
    try:
        enrollment.transition(db, created.session_id, "FIRST_FRAME_CAPTURED", now=1001)
    except enrollment.EnrollmentError:
        pass
    else:
        raise AssertionError("invalid state jump was accepted")


def test_secret_like_audit_fields_rejected():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "unknown", now=1000)
    try:
        enrollment._audit(db, created.session_id, "bad", {"wifi_password": "secret"}, 1001)
    except enrollment.EnrollmentError:
        pass
    else:
        raise AssertionError("secret-like audit field was accepted")


def test_vendor_token_namespace_is_not_bigbird_token():
    db = new_db()
    created = enrollment.create_enrollment(db, "bazz-wfcamout", "qr", now=1000)
    public = enrollment.get_enrollment(db, created.session_id)
    assert public["token_kind"] == "bigbird_enrollment"
    assert "vendor_activation_token" not in public
    assert "wifi_password" not in public
    assert not hasattr(enrollment, "build_vendor_qr")


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"Big Bird camera enrollment validation passed ({len(tests)} tests)")
    print("WW.CX enrollment token remains distinct from vendor activation material")
    print("No Wi-Fi password or vendor activation-token handling is implemented")


if __name__ == "__main__":
    main()
