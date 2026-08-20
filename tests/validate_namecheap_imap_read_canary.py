#!/usr/bin/env python3
"""Validate the explicit Namecheap Private Email header-only IMAP canary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/namecheap_imap_read_canary.py"
SCHEMA = ROOT / "schemas/messaging/namecheap-imap-read-canary-authorization.schema.json"
DOC = ROOT / "docs/messaging-operations/namecheap-imap-read-canary-20260820.md"
SPEC = importlib.util.spec_from_file_location("namecheap_imap_canary", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Namecheap IMAP canary")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(value: str | bytes) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def authorization(username: str, now: datetime, *, max_messages: int = 2) -> dict:
    return {
        "contract": MODULE.AUTH_CONTRACT,
        "provider_read_canary_authorized": True,
        "expected_host_sha256": sha256(MODULE.NAMECHEAP_IMAP_HOST),
        "expected_port": MODULE.NAMECHEAP_IMAP_PORT,
        "expected_username_sha256": sha256(username),
        "mailbox": "INBOX",
        "max_messages": max_messages,
        "expires_at": (now + timedelta(minutes=20)).isoformat(timespec="seconds"),
        "message_body_fetch_authorized": False,
        "mailbox_mutation_authorized": False,
        "store_write_authorized": False,
        "mail_send_authorized": False,
    }


def rejects(function, label: str) -> None:
    try:
        function()
    except MODULE.NamecheapIMAPCanaryError:
        return
    raise RuntimeError(f"unsafe Namecheap IMAP canary state did not fail closed: {label}")


HEADER_A = b"\r\n".join(
    [
        b"From: sender@example.test",
        b"To: john@ww.cx",
        b"Delivered-To: blank@ww.cx",
        b"Date: Thu, 20 Aug 2026 22:40:00 +0000",
        b"Message-ID: <canary-a@example.test>",
        b"Subject: Header canary A",
        b"",
        b"",
    ]
)
HEADER_B = b"\r\n".join(
    [
        b"From: sender@example.test",
        b"Cc: records@ww.cx",
        b"X-Original-To: records@ww.cx",
        b"Date: Thu, 20 Aug 2026 22:41:00 +0000",
        b"Message-ID: <canary-b@example.test>",
        b"Subject: Header canary B",
        b"",
        b"",
    ]
)
HEADER_NO_ID = b"\r\n".join(
    [
        b"From: sender@example.test",
        b"To: role@ww.cx",
        b"Date: Thu, 20 Aug 2026 22:42:00 +0000",
        b"Subject: Header canary no id",
        b"",
        b"",
    ]
)


class FakeIMAP:
    instances: list["FakeIMAP"] = []

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.messages = {
            b"10": HEADER_A,
            b"2": HEADER_NO_ID,
            b"100": HEADER_B,
        }
        self.__class__.instances.append(self)

    def login(self, user: str, password: str):
        self.calls.append(("login", user, password))
        check(user == "blank@ww.cx", "IMAP username changed")
        check(password == "synthetic-secret-not-for-network", "IMAP password changed")
        return "OK", [b"logged in"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False):
        self.calls.append(("select", mailbox, readonly))
        check(mailbox == "INBOX", "canary selected a non-INBOX mailbox")
        check(readonly is True, "canary did not select mailbox read-only")
        return "OK", [b"3"]

    def response(self, code: str):
        self.calls.append(("response", code))
        check(code == "UIDVALIDITY", "unexpected IMAP response metadata requested")
        return "UIDVALIDITY", [b"4242"]

    def uid(self, command: str, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            check(args == (None, "ALL"), "unexpected UID SEARCH arguments")
            return "OK", [b"10 2 100"]
        if command == "FETCH":
            uid, selector = args
            check(selector == "(BODY.PEEK[HEADER])", "canary fetched more than headers")
            payload = self.messages[uid]
            return "OK", [(b"1 (BODY[HEADER] {%d}" % len(payload), payload), b")"]
        raise RuntimeError(f"unexpected IMAP command: {command}")

    def logout(self):
        self.calls.append(("logout",))
        return "BYE", [b"logout"]


for path in (TOOL, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["properties"]["contract"]["const"] == MODULE.AUTH_CONTRACT, "authorization schema contract mismatch")
check(schema["additionalProperties"] is False, "authorization schema permits extra fields")
check(schema["properties"]["expected_port"]["const"] == MODULE.NAMECHEAP_IMAP_PORT, "authorization schema port mismatch")
check(schema["properties"]["mailbox"]["const"] == "INBOX", "authorization schema permits another mailbox")
check(schema["properties"]["max_messages"]["maximum"] == MODULE.MAX_CANARY_MESSAGES, "authorization schema message bound mismatch")
for key in (
    "message_body_fetch_authorized",
    "mailbox_mutation_authorized",
    "store_write_authorized",
    "mail_send_authorized",
):
    check(schema["properties"][key]["const"] is False, f"schema permits prohibited activity: {key}")

now = datetime(2026, 8, 20, 23, 0, 0, tzinfo=timezone.utc)
username = "blank@ww.cx"
auth = authorization(username, now)
settings = MODULE.load_runtime_settings(
    {
        MODULE.USERNAME_ENV: username,
        MODULE.PASSWORD_ENV: "synthetic-secret-not-for-network",
    }
)
result = MODULE.run_canary(settings, auth, session_factory=FakeIMAP, now=now)
serialized = json.dumps(result, sort_keys=True)

check(result["contract"] == MODULE.RESULT_CONTRACT, "result contract mismatch")
check(result["provider"] == "namecheap_private_email", "provider mismatch")
check(result["host_sha256"] == sha256(MODULE.NAMECHEAP_IMAP_HOST), "host hash mismatch")
check(result["port"] == 993, "port mismatch")
check(result["username_sha256"] == sha256(username), "username hash mismatch")
check(result["mailbox"] == "INBOX", "mailbox mismatch")
check(result["uidvalidity"] == "4242", "UIDVALIDITY mismatch")
check(result["selected_count"] == 2, "bounded tail count mismatch")
check(result["network_activity"] is True, "live canary did not report network activity")
check(result["tls_verification_required"] is True, "TLS verification marker changed")
check(result["mailbox_read_only"] is True, "read-only marker changed")
for key in (
    "message_body_fetched",
    "mailbox_mutation_authorized",
    "store_write_authorized",
    "mail_send_authorized",
    "credentials_output",
):
    check(result[key] is False, f"safety marker changed: {key}")

check(len(result["messages"]) == 2, "unexpected message summary count")
check(result["messages"][0]["uid_sha256"] == sha256(b"10"), "UID numeric ordering changed")
check(result["messages"][1]["uid_sha256"] == sha256(b"100"), "bounded newest UID selection changed")
check(result["messages"][0]["message_id_sha256"] == sha256("<canary-a@example.test>"), "Message-ID hash mismatch")
check(result["messages"][1]["message_id_sha256"] == sha256("<canary-b@example.test>"), "Message-ID hash mismatch")
check(result["messages"][0]["to_present"] is True, "To presence not reported")
check(result["messages"][0]["delivery_header_names_present"] == ["delivered-to"], "delivery header presence mismatch")
check(result["messages"][1]["cc_present"] is True, "Cc presence not reported")
check(result["messages"][1]["delivery_header_names_present"] == ["x-original-to"], "delivery header presence mismatch")

for raw_value in (
    MODULE.NAMECHEAP_IMAP_HOST,
    username,
    "synthetic-secret-not-for-network",
    "10",
    "100",
    "<canary-a@example.test>",
    "<canary-b@example.test>",
    "john@ww.cx",
    "records@ww.cx",
    "Header canary A",
    "Header canary B",
):
    check(raw_value not in serialized, f"raw provider/message value leaked into result: {raw_value}")
check(settings["password"] == "", "password was not cleared from runtime settings after canary")

session = FakeIMAP.instances[-1]
check(session.calls[0][0] == "login", "first provider operation was not LOGIN")
check(session.calls[1] == ("select", "INBOX", True), "mailbox was not selected read-only")
uid_calls = [call for call in session.calls if call[0] == "uid"]
check([call[1] for call in uid_calls] == ["SEARCH", "FETCH", "FETCH"], "unexpected IMAP UID command sequence")
check(all(call[-1] == "(BODY.PEEK[HEADER])" for call in uid_calls if call[1] == "FETCH"), "full body fetch was attempted")
check(session.calls[-1] == ("logout",), "canary did not log out")

fresh_settings = {
    "username": username,
    "password": "synthetic-secret-not-for-network",
}
wrong_user = authorization("other@ww.cx", now)
factory_called = {"value": False}

def forbidden_factory():
    factory_called["value"] = True
    raise RuntimeError("network factory must not run")

rejects(lambda: MODULE.run_canary(fresh_settings, wrong_user, session_factory=forbidden_factory, now=now), "username mismatch")
check(factory_called["value"] is False, "provider session opened before authorization binding")

expired = authorization(username, now)
expired["expires_at"] = (now - timedelta(seconds=1)).isoformat()
rejects(lambda: MODULE.validate_authorization_structure(expired, now=now), "expired authorization")
long_lived = authorization(username, now)
long_lived["expires_at"] = (now + timedelta(days=2)).isoformat()
rejects(lambda: MODULE.validate_authorization_structure(long_lived, now=now), "authorization over 24 hours")
wrong_host = authorization(username, now)
wrong_host["expected_host_sha256"] = "f" * 64
rejects(lambda: MODULE.validate_authorization_structure(wrong_host, now=now), "host mismatch")
wrong_port = authorization(username, now)
wrong_port["expected_port"] = 143
rejects(lambda: MODULE.validate_authorization_structure(wrong_port, now=now), "port mismatch")
wrong_mailbox = authorization(username, now)
wrong_mailbox["mailbox"] = "Archive"
rejects(lambda: MODULE.validate_authorization_structure(wrong_mailbox, now=now), "mailbox mismatch")
too_many = authorization(username, now, max_messages=MODULE.MAX_CANARY_MESSAGES + 1)
rejects(lambda: MODULE.validate_authorization_structure(too_many, now=now), "message bound")
body_auth = authorization(username, now)
body_auth["message_body_fetch_authorized"] = True
rejects(lambda: MODULE.validate_authorization_structure(body_auth, now=now), "body fetch authorization")
mutation_auth = authorization(username, now)
mutation_auth["mailbox_mutation_authorized"] = True
rejects(lambda: MODULE.validate_authorization_structure(mutation_auth, now=now), "mailbox mutation authorization")
store_auth = authorization(username, now)
store_auth["store_write_authorized"] = True
rejects(lambda: MODULE.validate_authorization_structure(store_auth, now=now), "store write authorization")
send_auth = authorization(username, now)
send_auth["mail_send_authorized"] = True
rejects(lambda: MODULE.validate_authorization_structure(send_auth, now=now), "mail send authorization")
extra = authorization(username, now)
extra["unexpected"] = True
rejects(lambda: MODULE.validate_authorization_structure(extra, now=now), "extra authorization key")
invalid_hash = authorization(username, now)
invalid_hash["expected_username_sha256"] = "not-a-hash"
rejects(lambda: MODULE.validate_authorization_structure(invalid_hash, now=now), "invalid username hash")

for missing in (MODULE.USERNAME_ENV, MODULE.PASSWORD_ENV):
    candidate = {
        MODULE.USERNAME_ENV: username,
        MODULE.PASSWORD_ENV: "synthetic-secret-not-for-network",
    }
    candidate.pop(missing)
    rejects(lambda candidate=candidate: MODULE.load_runtime_settings(candidate), f"missing {missing}")

audit = MODULE.audit_result(auth, now=now)
check(audit["network_activity"] is False, "audit-only mode claims network activity")
check(audit["credential_read"] is False, "audit-only mode claims credential access")
check(audit["message_body_fetched"] is False, "audit-only mode permits body fetch")

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    auth_path = folder / "authorization.json"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    auth_path.chmod(0o644)
    rejects(lambda: MODULE._private_regular_file(auth_path, "authorization"), "broad authorization permissions")
    auth_path.chmod(0o600)
    MODULE._private_regular_file(auth_path, "authorization")

    audit_cli = subprocess.run(
        [sys.executable, str(TOOL), "--authorization", str(auth_path)],
        cwd=ROOT,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    check(audit_cli.returncode == 0, f"audit-only CLI failed: {audit_cli.stderr}")
    audit_cli_result = json.loads(audit_cli.stdout)
    check(audit_cli_result["network_activity"] is False, "audit-only CLI contacted provider")
    check(audit_cli_result["credential_read"] is False, "audit-only CLI read credentials")

    execute_without_credentials = subprocess.run(
        [sys.executable, str(TOOL), "--authorization", str(auth_path), "--execute"],
        cwd=ROOT,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    check(execute_without_credentials.returncode == 2, "execute mode ran without credentials")
    check("IMAP username is unavailable or invalid" in execute_without_credentials.stderr, "missing-credential refusal changed")

    forbidden_output = ROOT / "var" / "forbidden-namecheap-imap-canary.json"
    refused = subprocess.run(
        [sys.executable, str(TOOL), "--authorization", str(auth_path), "--output", str(forbidden_output)],
        cwd=ROOT,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    check(refused.returncode == 2, "IMAP CLI accepted output inside Git tree")
    check("refusing IMAP canary output" in refused.stderr, "worktree output refusal reason changed")
    check(not forbidden_output.exists(), "IMAP CLI wrote forbidden output")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "header-only Namecheap Private Email IMAP canary",
    "BODY.PEEK[HEADER]",
    "readonly=True",
    "authorization window exceeds 24 hours",
    "message_body_fetched",
    "store_write_authorized",
    "mail_send_authorized",
    "refusing IMAP canary authorization inside the Git working tree",
):
    check(required in source, f"IMAP canary missing safety marker: {required}")
for prohibited in (
    "(BODY.PEEK[])",
    ".store(",
    ".copy(",
    ".append(",
    ".expunge(",
    "smtplib",
    "sendmail",
    "send_message",
    "print(settings",
    "print(password",
):
    check(prohibited not in source, f"IMAP canary contains prohibited operation: {prohibited}")

print("Namecheap Private Email read-only IMAP canary validation passed")
print("Expiring endpoint/username-bound authorization and private-file checks verified")
print("Verified TLS, read-only INBOX selection, bounded UID search, and BODY.PEEK[HEADER] fetches verified")
print("Audit-only default performs no network or credential read")
print("No message body, mailbox mutation, Mail Room write, SMTP send, or credential output is implemented")
