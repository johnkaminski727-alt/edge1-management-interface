#!/usr/bin/env python3
"""Audit or execute one direct-MTA WW.CX outbound pilot message.

Audit is the default and performs no mutation. Execution requires root, Edge1,
PTR/A forward-confirmed reverse DNS, published DKIM/SPF/DMARC, an empty Postfix
queue, the safe-disabled Postfix baseline, an explicit environment gate, and
exactly one recipient. The temporary loopback submission service and outbound
transport are always rolled back after the single submission attempt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import smtplib
import socket
import subprocess
import sys
import tempfile
import time

EXPECTED_HOST = "edge1.ww.cx"
PUBLIC_IP = "89.126.248.191"
MAIL_HOST = "mail.ww.cx"
DKIM_NAME = "edge1-202610._domainkey.ww.cx"
AUTH_NS = (
    "ns1194.dns.dyn.com",
    "ns2150.dns.dyn.com",
    "ns3190.dns.dyn.com",
    "ns4142.dns.dyn.com",
)
ENV_GATE = "WWCX_DIRECT_MTA_PILOT_AUTHORIZED"
MILTER = "inet:127.0.0.1:11332"
PILOT_PORT = 10026

class PilotError(RuntimeError):
    pass

def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(args, text=True, capture_output=True, timeout=30)
    if check and p.returncode:
        raise PilotError(f"command failed: {args[0]}")
    return p

def dig(name: str, rrtype: str, server: str = "1.1.1.1") -> list[str]:
    p = run("dig", "+short", f"@{server}", name, rrtype)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]

def postconf(name: str) -> str:
    return run("postconf", "-h", name).stdout.strip()

def queue_state() -> tuple[bool, bool]:
    p = run("postqueue", "-p", check=False)
    if p.returncode != 0:
        return False, False
    return True, "Mail queue is empty" in p.stdout

def socket_ready(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False

def dns_state() -> dict:
    ptr = dig("191.248.126.89.in-addr.arpa", "PTR")
    a = dig(MAIL_HOST, "A")
    spf = dig("ww.cx", "TXT")
    dmarc = dig("_dmarc.ww.cx", "TXT")
    dkim = {ns: dig(DKIM_NAME, "TXT", ns) for ns in AUTH_NS}
    return {
        "ptr": ptr,
        "a": a,
        "ptr_forward_confirmed": any(x.rstrip(".") == MAIL_HOST for x in ptr) and PUBLIC_IP in a,
        "spf_overlap_published": any(PUBLIC_IP in x and "spf.privateemail.com" in x for x in spf),
        "dmarc_monitoring_published": any("v=DMARC1" in x and "p=none" in x for x in dmarc),
        "dkim_all_authoritative": all(bool(v) for v in dkim.values()),
    }

def audit(recipient: str) -> dict:
    if recipient.count("@") != 1 or any(c.isspace() for c in recipient):
        raise PilotError("recipient is invalid")
    dns = dns_state()
    state = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "host": run("hostname", "-f").stdout.strip(),
        "recipient_sha256": hashlib.sha256(recipient.casefold().encode()).hexdigest(),
        "dns": dns,
        "rspamd_milter_ready": socket_ready(11332),
        "postfix": {
            "default_transport": postconf("default_transport"),
            "relay_transport": postconf("relay_transport"),
            "smtpd_milters": postconf("smtpd_milters"),
            "non_smtpd_milters": postconf("non_smtpd_milters"),
        },
    }
    queue_available, queue_is_empty = queue_state()
    state["queue_check_available"] = queue_available
    state["queue_empty"] = queue_is_empty
    state["safe_disabled"] = (
        state["postfix"]["default_transport"].startswith("error:")
        and state["postfix"]["relay_transport"].startswith("error:")
        and not state["postfix"]["smtpd_milters"]
        and not state["postfix"]["non_smtpd_milters"]
    )
    state["ready"] = all((
        state["host"] == EXPECTED_HOST,
        dns["ptr_forward_confirmed"],
        dns["spf_overlap_published"],
        dns["dmarc_monitoring_published"],
        dns["dkim_all_authoritative"],
        state["rspamd_milter_ready"],
        state["queue_check_available"],
        state["queue_empty"],
        state["safe_disabled"],
    ))
    return state

def execute(recipient: str, evidence_dir: Path) -> dict:
    if os.geteuid() != 0:
        raise PilotError("execution requires root")
    if os.environ.get(ENV_GATE) != "yes":
        raise PilotError("execution authorization environment gate is closed")
    before = audit(recipient)
    if not before["ready"]:
        raise PilotError("pilot readiness gates are not all green")

    evidence_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    backup_main = evidence_dir / "main.cf.before"
    backup_master = evidence_dir / "master.cf.before"
    shutil.copy2("/etc/postfix/main.cf", backup_main)
    shutil.copy2("/etc/postfix/master.cf", backup_master)
    os.chmod(backup_main, 0o600); os.chmod(backup_master, 0o600)
    attempted = 0
    submission: dict[str, object] = {"accepted": False}
    failure: str | None = None
    rollback_ok = False
    try:
        with open("/etc/postfix/master.cf", "a", encoding="utf-8") as f:
            f.write("\n# WWCX DIRECT MTA PILOT - TEMPORARY LOOPBACK ONLY\n")
            f.write(f"127.0.0.1:{PILOT_PORT} inet n - y - - smtpd\n")
            f.write("  -o syslog_name=postfix/wwcxpilot\n")
            f.write(f"  -o smtpd_milters={MILTER}\n")
            f.write("  -o milter_default_action=tempfail\n")
            f.write("  -o smtpd_client_restrictions=permit_mynetworks,reject\n")
            f.write("  -o smtpd_relay_restrictions=permit_mynetworks,reject_unauth_destination\n")
            f.write("  -o smtpd_recipient_restrictions=permit_mynetworks,reject_unauth_destination\n")
        run("postconf", "-e", "default_transport=smtp")
        run("postfix", "check")
        run("postfix", "reload")
        for _ in range(30):
            if socket_ready(PILOT_PORT): break
            time.sleep(0.25)
        else: raise PilotError("pilot submission listener did not start")

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        msg = (
            "From: John Kaminski <john@ww.cx>\r\n"
            f"To: {recipient}\r\n"
            "Subject: WW.CX Edge1 outbound mail pilot\r\n"
            f"Message-ID: <wwcx-edge1-pilot-{stamp}@ww.cx>\r\n"
            f"Date: {dt.datetime.now(dt.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}\r\n"
            "\r\n"
            "This is a controlled one-message delivery test from the new WW.CX Edge1 mail server.\r\n"
        )
        attempted += 1
        with smtplib.SMTP("127.0.0.1", PILOT_PORT, timeout=15) as client:
            client.ehlo("pilot.edge1.ww.cx")
            code, response = client.mail("john@ww.cx")
            if code != 250: raise PilotError("pilot MAIL FROM rejected")
            code, response = client.rcpt(recipient)
            if code != 250: raise PilotError("pilot RCPT TO rejected")
            code, response = client.data(msg)
            if code != 250: raise PilotError("pilot DATA rejected")
            text = response.decode(errors="replace") if isinstance(response, bytes) else str(response)
            submission = {"accepted": True, "smtp_code": code, "response_sha256": hashlib.sha256(text.encode()).hexdigest()}
        time.sleep(5)
    except Exception as exc:
        failure = type(exc).__name__ + ":" + str(exc)
        raise
    finally:
        shutil.copy2(backup_main, "/etc/postfix/main.cf")
        shutil.copy2(backup_master, "/etc/postfix/master.cf")
        try:
            run("postfix", "reload")
            after = audit(recipient)
            rollback_ok = after["safe_disabled"] and not socket_ready(PILOT_PORT)
        except Exception:
            rollback_ok = False
        record = {
            "contract": "wwcx.direct-mta-one-message-pilot.v1",
            "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "recipient_sha256": before["recipient_sha256"],
            "send_attempt_count": attempted,
            "submission": submission,
            "rollback_succeeded": rollback_ok,
            "failure_sha256": hashlib.sha256(failure.encode()).hexdigest() if failure else None,
            "raw_message_stored": False,
            "raw_recipient_stored": False,
        }
        (evidence_dir / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
        os.chmod(evidence_dir / "execution.json", 0o600)
    if attempted != 1 or not rollback_ok:
        raise PilotError("pilot did not complete with exactly one attempt and successful rollback")
    return record

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--recipient", required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--evidence-dir", type=Path)
    args = p.parse_args()
    if not args.execute:
        print(json.dumps(audit(args.recipient), indent=2))
        return 0
    if args.evidence_dir is None:
        raise PilotError("--evidence-dir is required for execution")
    print(json.dumps(execute(args.recipient, args.evidence_dir), indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PilotError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
