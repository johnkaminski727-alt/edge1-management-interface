#!/usr/bin/env python3
"""Validate the explicit SMTP STARTTLS/authentication-only canary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import smtplib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/outbound_mail_smtp_auth_canary.py"
SCHEMA = ROOT / "schemas/messaging/smtp-auth-canary-authorization.schema.json"
DOC = ROOT / "docs/messaging-operations/outbound-mail-smtp-auth-canary-20260804.md"
SPEC = importlib.util.spec_from_file_location("smtp_canary", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load SMTP canary")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def authorization(settings: dict, now: datetime) -> dict:
    return {
        "contract": MODULE.AUTH_CONTRACT,
        "authentication_canary_authorized": True,
        "provider_profile": "smtp_submission",
        "expected_host_sha256": hashlib.sha256(settings["host"].encode()).hexdigest(),
        "expected_port": settings["port"],
        "expected_username_sha256": hashlib.sha256(settings["username"].encode()).hexdigest(),
        "expires_at": (now + timedelta(minutes=20)).isoformat(timespec="seconds"),
        "mail_from_authorized": False,
        "recipient_authorized": False,
        "message_authorized": False,
    }


def rejects(function, label: str) -> None:
    try:
        function()
    except MODULE.SmtpCanaryError:
        return
    raise RuntimeError(f"unsafe SMTP canary state did not fail closed: {label}")


class FakeSocket:
    def getpeercert(self, binary_form=False):
        return b"synthetic-peer-certificate" if binary_form else {}

    def version(self):
        return "TLSv1.3"

    def cipher(self):
        return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, *, host, port, timeout):
        self.operations: list[str] = ["connect"]
        self.sock = FakeSocket()
        self.tls = False
        self.__class__.instances.append(self)
        check(host == "smtp.example.net", "host changed")
        check(port == 587, "port changed")
        check(timeout > 0, "timeout changed")

    def ehlo(self):
        self.operations.append("ehlo")
        return (250, b"hello")

    def has_extn(self, name):
        self.operations.append("has:" + name)
        return name == "starttls" or (name == "auth" and self.tls)

    def starttls(self, *, context):
        check(context is not None, "TLS context was not provided")
        self.operations.append("starttls")
        self.tls = True
        return (220, b"ready")

    def login(self, username, password):
        check(self.tls, "authentication occurred before TLS")
        check(username == "mailer@ww.cx", "username changed")
        check(password == "synthetic-secret-not-for-network", "password changed")
        self.operations.append("login")
        return (235, b"authenticated")

    def noop(self):
        self.operations.append("noop")
        return (250, b"ok")

    def rset(self):
        self.operations.append("rset")
        return (250, b"reset")

    def quit(self):
        self.operations.append("quit")
        return (221, b"bye")

    def close(self):
        self.operations.append("close")


class NoStarttlsSmtp(FakeSmtp):
    def has_extn(self, name):
        self.operations.append("has:" + name)
        return False


class RejectingSmtp(FakeSmtp):
    def login(self, username, password):
        self.operations.append("login")
        raise smtplib.SMTPAuthenticationError(535, b"rejected")


for path in (TOOL, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["properties"]["contract"]["const"] == MODULE.AUTH_CONTRACT, "authorization schema contract mismatch")
check(schema["additionalProperties"] is False, "authorization schema permits extra fields")
check(schema["properties"]["message_authorized"]["const"] is False, "schema permits message authorization")

profile = MODULE.load_profile(ROOT / "config/messaging/outbound-mail-gateway.json")
environment = {
    profile["host_env"]: "SMTP.EXAMPLE.NET",
    profile["port_env"]: "587",
    profile["username_env"]: "mailer@ww.cx",
    profile["password_env"]: "synthetic-secret-not-for-network",
}
settings = MODULE.load_runtime_settings(profile, environment)
check(settings["host"] == "smtp.example.net", "host normalization mismatch")
check(settings["port"] == 587, "port parsing mismatch")
now = datetime(2026, 8, 4, 5, 0, 0, tzinfo=timezone.utc)
auth = authorization(settings, now)
result = MODULE.run_canary(settings, auth, smtp_factory=FakeSmtp, now=now)
serialized = json.dumps(result, sort_keys=True)
check(result["contract"] == MODULE.RESULT_CONTRACT, "result contract mismatch")
check(result["authenticated"] is True, "authentication was not confirmed")
check(result["starttls_supported"] is True and result["tls_active"] is True, "TLS state mismatch")
check(result["tls_version"] == "TLSv1.3", "TLS version mismatch")
check(result["cipher_name"] == "TLS_AES_256_GCM_SHA384", "cipher mismatch")
check(result["peer_certificate_sha256"] == hashlib.sha256(b"synthetic-peer-certificate").hexdigest(), "certificate hash mismatch")
check(result["noop_code"] == 250 and result["rset_code"] == 250 and result["quit_code"] == 221, "SMTP control response mismatch")
for key in (
    "envelope_command_issued",
    "recipient_command_issued",
    "content_command_issued",
    "message_submission_attempted",
    "message_sent",
    "credentials_output",
):
    check(result[key] is False, f"message/credential safety marker changed: {key}")
check(settings["host"] not in serialized, "raw host leaked into result")
check(settings["username"] not in serialized, "raw username leaked into result")
check(settings["password"] not in serialized, "password leaked into result")
check(FakeSmtp.instances[-1].operations == [
    "connect",
    "ehlo",
    "has:starttls",
    "starttls",
    "ehlo",
    "has:auth",
    "login",
    "noop",
    "rset",
    "quit",
], f"unexpected SMTP operations: {FakeSmtp.instances[-1].operations}")

rejects(lambda: MODULE.run_canary(settings, auth, smtp_factory=NoStarttlsSmtp, now=now), "missing STARTTLS")
check("login" not in NoStarttlsSmtp.instances[-1].operations, "authentication attempted without STARTTLS")
rejects(lambda: MODULE.run_canary(settings, auth, smtp_factory=RejectingSmtp, now=now), "rejected authentication")
check("noop" not in RejectingSmtp.instances[-1].operations, "NOOP ran after rejected authentication")

expired = authorization(settings, now)
expired["expires_at"] = (now - timedelta(seconds=1)).isoformat()
rejects(lambda: MODULE.validate_authorization(expired, settings, now=now), "expired authorization")
long_lived = authorization(settings, now)
long_lived["expires_at"] = (now + timedelta(days=2)).isoformat()
rejects(lambda: MODULE.validate_authorization(long_lived, settings, now=now), "authorization over 24 hours")
wrong_host = authorization(settings, now)
wrong_host["expected_host_sha256"] = "f" * 64
rejects(lambda: MODULE.validate_authorization(wrong_host, settings, now=now), "host mismatch")
wrong_user = authorization(settings, now)
wrong_user["expected_username_sha256"] = "e" * 64
rejects(lambda: MODULE.validate_authorization(wrong_user, settings, now=now), "username mismatch")
message_auth = authorization(settings, now)
message_auth["message_authorized"] = True
rejects(lambda: MODULE.validate_authorization(message_auth, settings, now=now), "message authorization")
extra_key = authorization(settings, now)
extra_key["unexpected"] = True
rejects(lambda: MODULE.validate_authorization(extra_key, settings, now=now), "extra authorization key")

for missing in (profile["host_env"], profile["port_env"], profile["username_env"], profile["password_env"]):
    candidate = dict(environment)
    candidate.pop(missing)
    rejects(lambda candidate=candidate: MODULE.load_runtime_settings(profile, candidate), f"missing {missing}")

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    auth_path = folder / "authorization.json"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    auth_path.chmod(0o644)
    rejects(lambda: MODULE._private_regular_file(auth_path, "authorization"), "broad authorization permissions")
    auth_path.chmod(0o600)
    MODULE._private_regular_file(auth_path, "authorization")

    output_in_repo = ROOT / "var" / "forbidden-smtp-canary.json"
    refused = subprocess.run(
        [sys.executable, str(TOOL), "--authorization", str(auth_path), "--output", str(output_in_repo)],
        cwd=ROOT,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    check(refused.returncode == 2, "SMTP CLI accepted output inside Git tree")
    check("refusing SMTP canary output" in refused.stderr, "SMTP worktree refusal reason changed")
    check(not output_in_repo.exists(), "SMTP CLI wrote forbidden output")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "authentication-only canary",
    "never issues envelope, recipient, content, or submission commands",
    "authorization window exceeds 24 hours",
    "SMTP server does not advertise STARTTLS",
    "SMTP server does not advertise AUTH after STARTTLS",
    "message_submission_attempted",
    "credentials_output",
    "refusing SMTP authorization inside the Git working tree",
):
    check(required in source, f"SMTP canary missing safety marker: {required}")
for prohibited in (
    ".sendmail(",
    ".send_message(",
    ".mail(",
    ".rcpt(",
    ".data(",
    ".docmd(",
    "set_debuglevel",
    "print(settings",
    "print(password",
):
    check(prohibited not in source, f"SMTP canary contains prohibited message operation: {prohibited}")

print("SMTP authentication-only canary validation passed")
print("Expiring host/port/username-bound authorization and private-file checks verified")
print("STARTTLS, post-TLS AUTH, login, NOOP, RSET, QUIT, and sanitized TLS evidence verified")
print("No envelope, recipient, content, submission, credential output, or message traffic is implemented")
