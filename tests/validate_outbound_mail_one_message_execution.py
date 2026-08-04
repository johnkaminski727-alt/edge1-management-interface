#!/usr/bin/env python3
"""Validate the audited, rollback-first one-message pilot executor."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/execute_outbound_mail_one_message_pilot.py"
BUILDER = ROOT / "tools/messaging/build_outbound_mail_controlled_activation_bundle.py"
SCHEMA = ROOT / "schemas/messaging/outbound-mail-one-message-execution.schema.json"
DOC = ROOT / "docs/messaging-operations/outbound-mail-one-message-execution-20260804.md"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module("pilot_executor", TOOL)
ACTIVATION = load_module("activation_builder", BUILDER)
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
import outbound_mail_delivery_events as delivery_events


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def rejects(function, expected: str) -> None:
    try:
        function()
    except MODULE.PilotExecutionError as exc:
        check(expected in str(exc), f"unexpected refusal for {expected}: {exc}")
        return
    raise RuntimeError(f"unsafe operation did not fail closed: {expected}")


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, value: dict, mode: int = 0o600) -> None:
    path.write_bytes(ACTIVATION.canonical_bytes(value))
    os.chmod(path, mode)


def choose_sender(identities: dict) -> tuple[str, str]:
    allowed = set(identities["sender_selection"]["recipient_to_sender"].values())
    allowed.add(identities["sender_selection"]["system_sender"])
    for key, profile in identities["sender_profiles"].items():
        address = str(profile["address"]).casefold()
        if address in allowed and profile["outbound_enabled"] is False:
            return key, address
    raise RuntimeError("no disabled mapped sender profile is available")


def build_authorization(
    config: dict,
    policy: dict,
    identities: dict,
    sender_key: str,
    sender_address: str,
    request: dict,
    recipient: str,
    now: datetime,
) -> dict:
    return {
        "contract": ACTIVATION.AUTH_CONTRACT,
        "authorization_id": "WWCX-PILOT-EXEC-0001",
        "authorized_by": "john-k",
        "authorization_reference": "github-issue-187",
        "issued_at": (now - timedelta(minutes=5)).isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(minutes=30)).isoformat(timespec="seconds"),
        "provider_profile": "smtp_submission",
        "sender_identity_key": sender_key,
        "sender_address": sender_address,
        "runtime_config_sha256": ACTIVATION.sha256_document(config),
        "runtime_policy_sha256": ACTIVATION.sha256_document(policy),
        "runtime_identities_sha256": ACTIVATION.sha256_document(identities),
        "smtp_auth_canary_sha256": "a" * 64,
        "pilot_recipient_sha256": hashlib.sha256(recipient.encode("utf-8")).hexdigest(),
        "pilot_payload_sha256": ACTIVATION.sha256_document(request),
        "smtp_authentication_verified": True,
        "sender_provider_capability_verified": True,
        "dkim_dns_verified": True,
        "dmarc_monitoring_published": True,
        "aggregate_report_mailbox_ready": True,
        "bounce_ingestion_ready": True,
        "complaint_ingestion_ready": True,
        "suppression_gate_ready": True,
        "owned_recipient_verified": True,
        "activation_authorized": True,
        "one_message_authorized": True,
        "max_recipient_count": 1,
        "rollback_required": True,
        "bulk_authorized": False,
        "commercial_authorized": False,
        "regulatory_authorized": False,
        "emergency_authorized": False,
    }


def finalize_suppression_database(path: pathlib.Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
        check(mode is not None and str(mode[0]).casefold() == "delete", "fixture journal mode did not become DELETE")
    finally:
        connection.close()
    for suffix in ("-wal", "-shm"):
        sidecar = pathlib.Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


class Fixture:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.now = datetime(2026, 8, 4, 7, 0, 0, tzinfo=timezone.utc)
        self.runtime_root = root / "runtime"
        self.runtime_root.mkdir(mode=0o700)
        self.bundle_dir = root / "bundle"
        self.authorization_path = root / "authorization.json"
        self.request_path = root / "request.json"
        self.suppression_database = root / "delivery-state.sqlite3"
        self.evidence_dir = root / "evidence"

        self.config = load("config/messaging/outbound-mail-gateway.json")
        self.config["preparation_api"]["enabled"] = True
        self.policy = load("config/messaging/outbound-mail-policy.json")
        self.policy["organization"]["mailing_address"] = "123 Test Street, Regina SK S4P 0A1, Canada"
        self.identities = load("config/messaging/mail-identities.json")
        self.sender_key, self.sender_address = choose_sender(self.identities)
        self.recipient = "owned.pilot@example.test"
        self.request = {
            "to": [self.recipient],
            "subject": "Controlled one-message pilot",
            "body": "Synthetic pilot content used only by the fake CI runtime.",
            "message_class": "business_correspondence",
            "identity_hint": self.sender_address,
            "signer_name": "John Kaminski",
            "signer_title": "Authorized Representative",
            "mailing_address": self.policy["organization"]["mailing_address"],
            "confirm_send": True,
        }
        self.authorization = build_authorization(
            self.config,
            self.policy,
            self.identities,
            self.sender_key,
            self.sender_address,
            self.request,
            self.recipient,
            self.now,
        )
        self.bundle = ACTIVATION.build_bundle(
            self.config,
            self.policy,
            self.identities,
            self.authorization,
            now=self.now,
        )
        ACTIVATION.write_bundle(self.bundle, self.bundle_dir)
        write_json(self.authorization_path, self.authorization)
        write_json(self.request_path, self.request)
        for filename, document in zip(
            MODULE.RUNTIME_FILENAMES,
            (self.config, self.policy, self.identities),
        ):
            write_json(self.runtime_root / filename, document, mode=0o644)

        delivery_events.apply_event(
            self.suppression_database,
            {
                "contract": delivery_events.CONTRACT,
                "event_id": "event-pilot-unrelated-0001",
                "event_type": "provider_accepted",
                "occurred_at": "2026-08-04T06:30:00Z",
                "provider_profile": "smtp_submission",
                "provider_message_id_sha256": "b" * 64,
                "control_id": "WWCX-PILOT-UNRELATED-0001",
                "recipient_sha256": "f" * 64,
                "source_evidence_sha256": "c" * 64,
                "source_authentication": "synthetic_test",
                "source_verified": True,
                "diagnostic_class": "none",
                "retryable": False,
                "raw_recipient_stored": False,
                "raw_payload_stored": False,
                "message_content_stored": False,
            },
            allow_synthetic=True,
        )
        finalize_suppression_database(self.suppression_database)
        os.chmod(self.suppression_database, 0o600)
        self.context = MODULE.ExecutionContext(
            runtime_root=self.runtime_root,
            bundle_dir=self.bundle_dir,
            authorization_path=self.authorization_path,
            request_path=self.request_path,
            suppression_database=self.suppression_database,
            evidence_dir=self.evidence_dir,
            expected_commit="d" * 40,
            service=MODULE.DEFAULT_SERVICE,
            gateway_url=MODULE.DEFAULT_GATEWAY_URL,
            expected_host=MODULE.EXPECTED_HOST,
        )

    def audit(self) -> dict:
        original = MODULE.validate_runtime_file
        MODULE.validate_runtime_file = lambda path: path
        try:
            with mock.patch.object(
                MODULE,
                "validate_repository",
                return_value={"commit": "d" * 40, "branch": "main", "clean": True, "exact": True},
            ):
                return MODULE.audit_context(self.context, now=self.now, execute=False)
        finally:
            MODULE.validate_runtime_file = original


class FakeAdapter(MODULE.RuntimeAdapter):
    def __init__(
        self,
        runtime_root: pathlib.Path,
        *,
        send_status: int = 202,
        fail_restart_calls: set[int] | None = None,
    ) -> None:
        self.runtime_root = runtime_root
        self.send_status = send_status
        self.fail_restart_calls = fail_restart_calls or set()
        self.restart_calls = 0
        self.send_calls = 0
        self.replace_calls = 0

    def replace_runtime(self, source_files: dict[str, pathlib.Path], runtime_root: pathlib.Path) -> None:
        self.replace_calls += 1
        for filename, source in source_files.items():
            shutil.copyfile(source, runtime_root / filename)
            os.chmod(runtime_root / filename, 0o644)

    def restart_service(self, service: str) -> None:
        check(service == MODULE.DEFAULT_SERVICE, "executor changed service name")
        self.restart_calls += 1
        if self.restart_calls in self.fail_restart_calls:
            raise MODULE.PilotExecutionError("synthetic restart failure")

    def get_json(self, url: str) -> tuple[int, dict]:
        if url.endswith("/healthz"):
            return 200, {"status": "ok"}
        config = json.loads((self.runtime_root / MODULE.RUNTIME_FILENAMES[0]).read_text())
        identities = json.loads((self.runtime_root / MODULE.RUNTIME_FILENAMES[2]).read_text())
        live_count = sum(
            1 for profile in identities["sender_profiles"].values() if profile["outbound_enabled"]
        )
        return 200, {
            "external_delivery_enabled": config["external_delivery_authorized"],
            "sender_selection": {"live_sender_count": live_count},
        }

    def send_once(self, url: str, payload: dict) -> tuple[int, dict]:
        check(url == MODULE.DEFAULT_GATEWAY_URL + "/outbound-mail/send", "executor changed send endpoint")
        self.send_calls += 1
        check(self.send_calls == 1, "executor attempted more than one send")
        check(payload["to"] == ["owned.pilot@example.test"], "payload changed")
        if self.send_status == 202:
            return 202, {
                "status": "accepted",
                "provider": "synthetic",
                "provider_message_id": "sensitive-provider-message-id",
                "audit_event": {"event_id": "sensitive-event-id"},
            }
        return self.send_status, {"status": "rejected", "error": "synthetic"}


def read_runtime(root: pathlib.Path) -> dict[str, bytes]:
    return {filename: (root / filename).read_bytes() for filename in MODULE.RUNTIME_FILENAMES}


def test_validate_and_audit() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        before = read_runtime(fixture.runtime_root)
        db_before = hashlib.sha256(fixture.suppression_database.read_bytes()).hexdigest()
        check(not pathlib.Path(str(fixture.suppression_database) + "-wal").exists(), "fixture retained a WAL")
        check(not pathlib.Path(str(fixture.suppression_database) + "-shm").exists(), "fixture retained SHM")
        audit = fixture.audit()
        check(audit["authorization"]["authorization_id"] == "WWCX-PILOT-EXEC-0001", "authorization was not accepted")
        check(audit["suppression_state"]["suppression_active"] is False, "recipient was incorrectly suppressed")
        check(read_runtime(fixture.runtime_root) == before, "audit mutated runtime files")
        check(hashlib.sha256(fixture.suppression_database.read_bytes()).hexdigest() == db_before, "audit mutated suppression database")
        check(not pathlib.Path(str(fixture.suppression_database) + "-wal").exists(), "audit created a suppression WAL")
        check(not pathlib.Path(str(fixture.suppression_database) + "-shm").exists(), "audit created suppression shared memory")


def test_request_and_bundle_tamper_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        changed = copy.deepcopy(fixture.request)
        changed["body"] = "Tampered body"
        rejects(lambda: MODULE.validate_request(changed, fixture.authorization, fixture.policy), "request hash")
        activated = fixture.bundle_dir / "activated" / MODULE.RUNTIME_FILENAMES[0]
        document = json.loads(activated.read_text())
        document["admin"]["max_body_bytes"] += 1
        write_json(activated, document)
        manifest_path = fixture.bundle_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["file_sha256"][f"activated/{MODULE.RUNTIME_FILENAMES[0]}"] = hashlib.sha256(activated.read_bytes()).hexdigest()
        write_json(manifest_path, manifest)
        rejects(fixture.audit, "not the expected document")


def test_suppressed_recipient_fails_before_execution() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        delivery_events.apply_event(
            fixture.suppression_database,
            {
                "contract": delivery_events.CONTRACT,
                "event_id": "event-pilot-complaint-0001",
                "event_type": "complaint",
                "occurred_at": "2026-08-04T06:40:00Z",
                "provider_profile": "smtp_submission",
                "provider_message_id_sha256": "e" * 64,
                "control_id": "WWCX-PILOT-COMPLAINT-0001",
                "recipient_sha256": fixture.authorization["pilot_recipient_sha256"],
                "source_evidence_sha256": "f" * 64,
                "source_authentication": "synthetic_test",
                "source_verified": True,
                "diagnostic_class": "spam_complaint",
                "retryable": False,
                "raw_recipient_stored": False,
                "raw_payload_stored": False,
                "message_content_stored": False,
            },
            allow_synthetic=True,
        )
        finalize_suppression_database(fixture.suppression_database)
        rejects(fixture.audit, "suppression is active")


def run_execute(fixture: Fixture, adapter: FakeAdapter) -> dict:
    audit = fixture.audit()

    def test_runtime_documents(root: pathlib.Path):
        documents = [json.loads((root / filename).read_text()) for filename in MODULE.RUNTIME_FILENAMES]
        paths = {filename: root / filename for filename in MODULE.RUNTIME_FILENAMES}
        return documents[0], documents[1], documents[2], paths

    def test_evidence(path: pathlib.Path, *, owner_uid: int):
        del owner_uid
        path.mkdir(mode=0o700)
        return path

    fake_hostname = SimpleNamespace(returncode=0, stdout=MODULE.EXPECTED_HOST + "\n")
    with mock.patch.object(MODULE, "validate_execution_targets"), mock.patch.object(
        MODULE.os, "geteuid", return_value=0
    ), mock.patch.dict(
        MODULE.os.environ, {MODULE.EXECUTION_ENVIRONMENT_GATE: "yes"}, clear=False
    ), mock.patch.object(
        MODULE.subprocess, "run", return_value=fake_hostname
    ), mock.patch.object(
        MODULE, "audit_context", return_value=audit
    ), mock.patch.object(
        MODULE, "validate_runtime_documents", side_effect=test_runtime_documents
    ), mock.patch.object(
        MODULE, "prepare_evidence_directory", side_effect=test_evidence
    ):
        return MODULE.execute_pilot(fixture.context, adapter, now=fixture.now)


def test_success_sends_once_and_rolls_back() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        before = read_runtime(fixture.runtime_root)
        adapter = FakeAdapter(fixture.runtime_root)
        record = run_execute(fixture, adapter)
        check(adapter.send_calls == 1, "successful pilot did not send exactly once")
        check(adapter.restart_calls == 2 and adapter.replace_calls == 2, "successful pilot transaction count changed")
        check(record["send_attempt_count"] == 1 and record["submission"]["accepted"] is True, "accepted send evidence changed")
        check(record["rollback_succeeded"] is True, "successful pilot did not rollback")
        check(record["failure_code"] is None and record["rollback_error_code"] is None, "successful pilot recorded an error")
        check(read_runtime(fixture.runtime_root) == before, "runtime was not restored")
        evidence_path = fixture.evidence_dir / "execution.json"
        evidence_text = evidence_path.read_text()
        check((evidence_path.stat().st_mode & 0o777) == 0o600, "execution evidence mode too broad")
        for forbidden in (
            fixture.recipient,
            fixture.request["body"],
            "sensitive-provider-message-id",
            "sensitive-event-id",
        ):
            check(forbidden not in evidence_text, f"execution evidence leaked {forbidden}")


def test_provider_failure_still_rolls_back_without_retry() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        before = read_runtime(fixture.runtime_root)
        adapter = FakeAdapter(fixture.runtime_root, send_status=503)
        rejects(lambda: run_execute(fixture, adapter), "did not accept")
        check(adapter.send_calls == 1, "provider failure was retried")
        check(adapter.restart_calls == 2, "provider failure did not rollback service")
        check(read_runtime(fixture.runtime_root) == before, "provider failure did not restore runtime")
        record = json.loads((fixture.evidence_dir / "execution.json").read_text())
        check(record["rollback_succeeded"] is True and record["send_attempt_count"] == 1, "provider failure transaction evidence changed")
        check(record["failure_code"] == "PilotExecutionError", "provider failure code changed")
        check(len(record["failure_detail_sha256"]) == 64, "provider failure detail was not hashed")
        check("provider did not accept" not in json.dumps(record), "provider failure detail leaked")


def test_activation_failure_rolls_back_before_send() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        before = read_runtime(fixture.runtime_root)
        adapter = FakeAdapter(fixture.runtime_root, fail_restart_calls={1})
        rejects(lambda: run_execute(fixture, adapter), "restart failure")
        check(adapter.send_calls == 0, "send occurred after activation failure")
        check(adapter.restart_calls == 2, "activation failure did not attempt rollback restart")
        check(read_runtime(fixture.runtime_root) == before, "activation failure did not restore runtime")


def test_rollback_failure_is_terminal() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        adapter = FakeAdapter(fixture.runtime_root, fail_restart_calls={2})
        rejects(lambda: run_execute(fixture, adapter), "automatic rollback failed")
        check(adapter.send_calls == 1, "rollback failure changed send count")
        evidence_text = (fixture.evidence_dir / "execution.json").read_text()
        record = json.loads(evidence_text)
        check(record["rollback_succeeded"] is False, "rollback failure recorded as success")
        check(record["rollback_error_code"] == "PilotExecutionError", "rollback failure code changed")
        check(len(record["rollback_error_detail_sha256"]) == 64, "rollback failure detail was not hashed")
        check("synthetic restart failure" not in evidence_text, "rollback failure detail leaked")


def test_schema_and_static_safety() -> None:
    schema = json.loads(SCHEMA.read_text())
    check(schema["additionalProperties"] is False, "execution schema permits extra fields")
    check(schema["properties"]["send_attempt_count"]["maximum"] == 1, "schema permits retry")
    for field in (
        "failure_code",
        "failure_detail_sha256",
        "rollback_error_code",
        "rollback_error_detail_sha256",
    ):
        check(field in schema["required"], f"schema does not require {field}")
    check("failure" not in schema["properties"] and "rollback_error" not in schema["properties"], "schema permits raw failure detail")

    source = TOOL.read_text()
    for required in (
        "Audit is the default and performs no mutation",
        "fixed loopback send is attempted at",
        "most once and is never retried",
        "WWCX_ONE_MESSAGE_PILOT_AUTHORIZED",
        "execution requires exact clean main",
        "one-message execution requires root",
        "one-message execution is on the wrong host",
        "execution runtime root is not /etc/wwcx",
        "execution suppression database path is unexpected",
        "execution service name is unexpected",
        "gateway URL is not the fixed loopback endpoint",
        "activation bundle {section} document is not the expected document",
        "pilot recipient suppression is active",
        "mode=ro",
        "post-rollback runtime hashes do not match preflight",
        "post-rollback gateway is not safe-disabled",
        "send_attempt_count",
        "failure_detail_sha256",
        "rollback_error_detail_sha256",
        "raw_provider_response_stored",
    ):
        check(required in source, f"executor missing safety marker: {required}")
    check(source.count("adapter.send_once(") == 1, "executor has multiple send call sites")
    check("while " not in source[source.index("def execute_pilot"):], "executor contains a retry loop")
    for prohibited in (
        "smtp_password",
        "WWCX_MAIL_SMTP_PASSWORD",
        "mail(",
        "sendmail",
        "smtplib",
        "requests.",
        "systemctl enable",
        "rm -rf",
        "curl -k",
        "--insecure",
    ):
        check(prohibited not in source, f"executor contains prohibited operation: {prohibited}")


for test in (
    test_validate_and_audit,
    test_request_and_bundle_tamper_fail_closed,
    test_suppressed_recipient_fails_before_execution,
    test_success_sends_once_and_rolls_back,
    test_provider_failure_still_rolls_back_without_retry,
    test_activation_failure_rolls_back_before_send,
    test_rollback_failure_is_terminal,
    test_schema_and_static_safety,
):
    test()

check(TOOL.is_file() and TOOL.stat().st_size > 10000, "executor is missing or undersized")
check(DOC.is_file() and DOC.stat().st_size > 1000, "execution runbook is missing")
print("One-message outbound-mail execution wrapper validation passed")
print("Audit-only default, read-only suppression lookup, exact bundle recomputation, and suppression refusal verified")
print("Successful and failed submissions attempt at most one send and always enter rollback")
print("Activation, provider, and rollback failure paths are covered with a fake runtime")
print("Failure details and provider evidence are retained only as SHA-256")
print("No production credential, provider, DNS, service, or message operation occurs in CI")
