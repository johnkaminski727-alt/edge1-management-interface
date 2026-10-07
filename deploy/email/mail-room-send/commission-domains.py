#!/usr/bin/env python3
"""Phase 2: commission creekco.ca and omegafx.com for local-MTA sending; finish scgardens.ca inbound.

    sudo python3 deploy/email/mail-room-send/commission-domains.py           # read-only: show evidence found
    sudo python3 deploy/email/mail-room-send/commission-domains.py --apply   # record evidence, enable domains

Evidence comes only from this host: the Postfix log (outbound test queue IDs and
external inbound deliveries from the test mailbox) and live DNS. Nothing is
recorded unless every required item is found. Backups go to /root.
"""
from __future__ import annotations

import glob
import gzip
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

COMMISSIONING = "/etc/wwcx/mail-commissioning.json"
GATEWAY = "/etc/wwcx/outbound-mail/gateway.json"
TEST_MAILBOX = "spiritcreekgardens@outlook.com"
MAIL_IP = "89.126.248.191"
APPROVAL = "John William Kaminski (operator), via chat approval 2026-10-07"
# Outbound tests sent directly from edge1 on 2026-10-06; Outlook.com headers forwarded by John
# showed spf=pass, dkim=pass (s=edge1-202610), dmarc=pass, compauth=pass for each.
OUTBOUND = {
    "creekco.ca": ("DA8E21448BC", "contact@creekco.ca", "SCL 1, Inbox"),
    "omegafx.com": ("6F1311448BD", "john@omegafx.com", "SCL 5, Junk on reputation (SpamFilterAuthJ); marked Not junk"),
    "scgardens.ca": ("63A451448BC", "john@scgardens.ca", "SCL 5, Junk on reputation (SpamFilterAuthJ)"),
}
NEW_DOMAINS = ["creekco.ca", "omegafx.com"]
INBOUND_DOMAINS = ["creekco.ca", "omegafx.com", "scgardens.ca"]


def log_lines() -> list[str]:
    lines: list[str] = []
    for path in sorted(glob.glob("/var/log/mail.log*")):
        opener = gzip.open if path.endswith(".gz") else open
        try:
            with opener(path, "rt", errors="replace") as handle:
                lines.extend(handle)
        except OSError:
            pass
    if not lines:  # journald-only hosts
        out = subprocess.run(["journalctl", "--since", "2026-10-05", "-o", "short-iso", "--no-pager", "SYSLOG_FACILITY=2"],
                             capture_output=True, text=True).stdout
        lines = out.splitlines()
    return lines


def parse(lines: list[str]) -> dict[str, dict]:
    queue: dict[str, dict] = {}
    pat = re.compile(r"^(\S+(?:\s+\d+\s+[\d:]+)?)\s.*postfix/(\w+)\[\d+\]: ([0-9A-F]{8,}): (.*)$")
    for line in lines:
        m = pat.match(line.strip())
        if not m:
            continue
        stamp, proc, qid, rest = m.groups()
        q = queue.setdefault(qid, {"deliveries": []})
        if proc == "smtpd" and rest.startswith("client="):
            q["client"] = rest[7:].split(",")[0]
        elif proc == "qmgr" and rest.startswith("from=<"):
            q["from"] = rest[6:rest.index(">")].lower()
        elif "to=<" in rest and "status=" in rest:
            to = re.search(r"to=<([^>]*)>", rest).group(1).lower()
            orig = re.search(r"orig_to=<([^>]*)>", rest)
            q["deliveries"].append({"time": stamp, "to": to, "orig_to": orig.group(1).lower() if orig else None,
                                    "relay": (re.search(r"relay=([^,\s]+)", rest) or [None, None])[1],
                                    "status": re.search(r"status=(\w+)", rest).group(1),
                                    "detail": rest[rest.index("status="):][:140]})
    return queue


def dig(name: str, rtype: str) -> list[str]:
    out = subprocess.run(["dig", "+short", name, rtype], capture_output=True, text=True, timeout=15).stdout
    return [x.strip().strip('"') for x in out.splitlines() if x.strip()]


def main() -> int:
    apply = "--apply" in sys.argv
    queue = parse(log_lines())
    evidence: dict[str, dict] = {}
    missing: list[str] = []

    for domain, (qid, sender, placement) in OUTBOUND.items():
        sent = [d for d in queue.get(qid, {}).get("deliveries", []) if d["status"] == "sent" and d["to"] == TEST_MAILBOX]
        if sent:
            d = sent[-1]
            evidence.setdefault(domain, {})["outbound_delivery"] = (
                f"{d['time']} {sender} -> {TEST_MAILBOX}, Postfix queue {qid}, relay={d['relay']} {d['detail']}. "
                f"Outlook.com Authentication-Results: spf=pass, dkim=pass header.d={domain} s=edge1-202610, dmarc=pass, compauth=pass reason=100; {placement}.")
            evidence[domain]["sender_authentication"] = (
                f"Queue {qid} signed d={domain} s=edge1-202610 by rspamd; received as spf=pass (89.126.248.191), dkim=pass, dmarc=pass at Outlook.com 2026-10-06.")
            print(f"OK   outbound  {domain}: queue {qid} status=sent to {TEST_MAILBOX}")
        else:
            missing.append(f"outbound {domain} (queue {qid} with status=sent)")
            print(f"MISS outbound  {domain}: queue {qid} not found as sent in the mail log")

    for domain in INBOUND_DOMAINS:
        hits = []
        for qid, q in queue.items():
            if q.get("from") != TEST_MAILBOX:
                continue
            for d in q["deliveries"]:
                target = d["orig_to"] or d["to"]
                if target.endswith("@" + domain) and d["status"] == "sent" and (d["relay"] or "").startswith("wwcxmail"):
                    hits.append((d["time"], qid, target, q.get("client", "unknown client")))
        if hits:
            when, qid, target, client = hits[-1]
            evidence.setdefault(domain, {})["inbound_delivery"] = (
                f"{when} external message from {TEST_MAILBOX} ({client}) to {target}, queue {qid}, delivered via wwcxmail (status=sent).")
            print(f"OK   inbound   {domain}: queue {qid} {TEST_MAILBOX} -> {target} via wwcxmail")
        else:
            missing.append(f"inbound {domain} (from {TEST_MAILBOX}, relay=wwcxmail, status=sent)")
            print(f"MISS inbound   {domain}: no delivery from {TEST_MAILBOX} via wwcxmail found")

    for domain in NEW_DOMAINS:
        mx, txt = dig(domain, "MX"), dig(domain, "TXT")
        dmarc, dkim = dig("_dmarc." + domain, "TXT"), dig("edge1-202610._domainkey." + domain, "TXT")
        spf = [t for t in txt if t.startswith("v=spf1")]
        ok = any(m.endswith("mail.ww.cx.") for m in mx) and len(spf) == 1 and f"ip4:{MAIL_IP}" in spf[0] \
            and any(d.startswith("v=DMARC1") for d in dmarc) and any("DKIM1" in d for d in dkim)
        if ok:
            evidence.setdefault(domain, {})["public_dns"] = (
                f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ} via edge1 resolver: MX {', '.join(mx)}; SPF {spf[0]}; "
                f"DMARC {dmarc[0]}; edge1-202610._domainkey published.")
            print(f"OK   dns       {domain}: MX/SPF/DMARC/DKIM correct")
        else:
            missing.append(f"public DNS {domain}")
            print(f"MISS dns       {domain}: MX={mx} SPF={spf} DMARC={dmarc} DKIM={'yes' if dkim else 'no'}")

    if missing:
        print("\nNot all evidence is present; nothing recorded. Missing:\n  - " + "\n  - ".join(missing))
        return 1
    if not apply:
        print("\nAll evidence found. Re-run with --apply to record it and enable creekco.ca and omegafx.com.")
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for path in (COMMISSIONING, GATEWAY):
        shutil.copy2(path, f"/root/{path.rsplit('/', 1)[1]}.pre-phase2-{stamp}")

    record = json.load(open(COMMISSIONING))
    for domain in NEW_DOMAINS:
        record["domains"][domain] = {
            "commissioned": True, "migration_state": "live_on_edge1", "provider_credentials": "not_applicable",
            "public_dns": "verified", "inbound_delivery": "verified", "outbound_delivery": "verified",
            "sender_authentication": "verified", "rollback_rehearsal": "not_verified",
            "evidence": {**evidence[domain], "approved_by": APPROVAL,
                         "rollback_rehearsal": "not performed; previous MX target recorded in records/messaging DNS inventories."},
        }
    scg = record["domains"]["scgardens.ca"]
    scg["inbound_delivery"] = "verified"
    scg.setdefault("evidence", {})["inbound_delivery"] = evidence["scgardens.ca"]["inbound_delivery"]
    record["recorded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["approved_by"] = APPROVAL
    record["recorded_by"] = "Claude (desktop session) via operator-run commission-domains.py"
    with open(COMMISSIONING, "w") as handle:  # in place: keeps owner and mode
        handle.write(json.dumps(record, indent=1) + "\n")

    gateway = json.load(open(GATEWAY))
    allowed = gateway["provider"]["profiles"]["edge1_local_mta"]["allowed_from_domains"]
    for domain in NEW_DOMAINS:
        if domain not in allowed:
            allowed.append(domain)
    with open(GATEWAY, "w") as handle:
        handle.write(json.dumps(gateway, indent=2) + "\n")

    subprocess.run(["systemctl", "restart", "wwcx-outbound-mail-gateway"], check=False)
    time.sleep(3)
    if subprocess.run(["systemctl", "is-active", "--quiet", "wwcx-outbound-mail-gateway"]).returncode != 0:
        for path in (COMMISSIONING, GATEWAY):
            shutil.copy2(f"/root/{path.rsplit('/', 1)[1]}.pre-phase2-{stamp}", path)
        subprocess.run(["systemctl", "restart", "wwcx-outbound-mail-gateway"], check=False)
        print("FAIL: gateway did not start with the new config; restored both files. See journalctl -u wwcx-outbound-mail-gateway.")
        return 1
    print(f"\nRecorded. allowed_from_domains = {allowed}")
    print(f"Backups: /root/mail-commissioning.json.pre-phase2-{stamp}, /root/gateway.json.pre-phase2-{stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
