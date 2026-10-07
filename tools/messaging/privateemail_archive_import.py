#!/usr/bin/env python3
"""Resumable read-only PrivateEmail copy; originals and flags remain unchanged."""
import collections
import hashlib
import imaplib
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import sys
import tempfile
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from mail_correspondence_store import MailCorrespondenceStore
from mail_local_rfc822_source import normalize_rfc822
from mail_local_mta import scan

ROOT = Path("/var/lib/wwcx-mail-room/imports/privateemail-20261007")
DB = Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
ACCOUNTS = ("blank@ww.cx", "webmaster@omegafx.com", "domaincontact@ww.cx")

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def save(path, data):
    write(path, (json.dumps(data, sort_keys=True, indent=2) + "\n").encode())

def folders(client):
    status, rows = client.list()
    if status != "OK":
        raise RuntimeError("folder inventory failed")
    result = []
    for row in rows:
        match = re.match(rb'^\((.*?)\) "[^"]*" (.*)$', row)
        if not match:
            raise RuntimeError("unsupported folder inventory response")
        flags, name = match.groups()
        if b"\\Noselect" not in flags:
            result.append(name.decode("ascii"))
    return sorted(result, key=lambda name: (0 if name.strip('"').upper() == "INBOX" else 2 if name.strip('"').lower() in {"spam", "junk"} else 1, name))

class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li", "tr"} and not self.hidden:
            self.text.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"} and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)

def readable_bytes(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    parts = [part for part in message.walk() if not part.is_multipart() and part.get_content_disposition() != "attachment"]
    if any(part.get_content_type() == "text/plain" for part in parts):
        return raw, False
    html = [part for part in parts if part.get_content_type() == "text/html"]
    if not html:
        return raw, False
    parser = PlainHTML()
    for part in html:
        parser.feed(part.get_content())
        parser.text.append("\n")
    message.clear_content()
    message.set_content("".join(parser.text))
    return message.as_bytes(), True

def project(raw, account, folder, store):
    if folder.strip('"').lower() in {"spam", "junk", "trash", "drafts"}:
        return {"status": "archive_only", "reason": "original_provider_folder"}
    try:
        result = scan(raw)
        if result["state"] != "clean":
            return {"status": "held", "reason": "malware_scan_not_clean"}
        mid = str(BytesParser(policy=policy.default).parsebytes(raw, headersonly=True).get("Message-ID", ""))
        with sqlite3.connect(DB) as db:
            exists = db.execute("SELECT 1 FROM correspondence WHERE message_id=?", (mid,)).fetchone()
        if exists:
            return {"status": "duplicate"}
        direction = "outbound" if folder.strip('"').lower() == "sent" else "inbound"
        readable, derived = readable_bytes(raw)
        record = normalize_rfc822(readable, store, direction=direction)
        return {"status": "imported", "message_id_sha256": hashlib.sha256(record["message_id"].encode()).hexdigest(), "scan": "clean", "html_text_derived": derived}
    except Exception as exc:
        return {"status": "held", "reason": type(exc).__name__}

def main():
    if os.geteuid() != 0:
        raise SystemExit("root required for credential access")
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = ROOT / "correspondence-before-import.sqlite3"
    if not backup.exists():
        with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        backup.chmod(0o600)
    store = MailCorrespondenceStore(DB, source="privateemail-historical-import", source_authoritative=True, source_scope="local_native")
    summary = {"status": "running", "accounts": {}, "provider_mutations": False}
    save(ROOT / "summary.json", summary)
    for account in ACCOUNTS:
        credential = Path("/etc/wwcx/privateemail-import") / (account + ".json")
        if not credential.exists():
            summary["accounts"][account] = {"status": "credential_missing"}
            save(ROOT / "summary.json", summary)
            continue
        counts = collections.Counter()
        current = {"status": "running", "folders": [], "counts": {}}
        summary["accounts"][account] = current
        client = None
        try:
            secret = json.loads(credential.read_text())
            client = imaplib.IMAP4_SSL("mail.privateemail.com", 993, ssl_context=ssl.create_default_context(), timeout=90)
            client.authenticate("PLAIN", lambda _: ("\x00" + secret["username"] + "\x00" + secret["password"]).encode())
            secret.clear()
            for name in folders(client):
                status, n = client.select(name, readonly=True)
                if status != "OK":
                    raise RuntimeError("read-only folder selection failed")
                validity = client.response("UIDVALIDITY")[1][0].decode()
                if not validity.isdigit():
                    raise RuntimeError("invalid UIDVALIDITY")
                status, data = client.uid("SEARCH", None, "ALL")
                if status != "OK":
                    raise RuntimeError("UID inventory failed")
                uids = data[0].split()
                if any(not u.isdigit() for u in uids):
                    raise RuntimeError("invalid UID")
                directory = ROOT / account / (hashlib.sha256(name.encode()).hexdigest()[:16] + "-" + validity)
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                folder_report = {"folder": name, "expected": len(uids), "copied": 0, "counts": {}}
                current["folders"].append(folder_report)
                fc = collections.Counter()
                for offset in range(0, len(uids), 10):
                    batch = uids[offset:offset+10]
                    needed = [u for u in batch if not (directory / (u.decode()+".json")).exists()]
                    fetched = {}
                    if needed:
                        status, rows = client.uid("FETCH", b",".join(needed), "(UID BODY.PEEK[])")
                        if status != "OK":
                            raise RuntimeError("message fetch failed")
                        for row in rows:
                            if isinstance(row, tuple):
                                match = re.search(rb'UID (\d+)', row[0])
                                if match:
                                    fetched[match.group(1)] = row[1]
                    for uid in batch:
                        stem = uid.decode()
                        metadata = directory / (stem + ".json")
                        raw_path = directory / (stem + ".eml")
                        if metadata.exists():
                            record = json.loads(metadata.read_text())
                            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != record["sha256"]:
                                raise RuntimeError("archive integrity mismatch")
                        else:
                            raw = fetched.get(uid)
                            if not raw:
                                raise RuntimeError("incomplete fetch")
                            write(raw_path, raw)
                            record = {"account": account, "folder": name, "uid": stem, "uidvalidity": validity, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "projection": project(raw, account, name, store)}
                            save(metadata, record)
                        state = record["projection"]["status"]
                        counts[state] += 1
                        fc[state] += 1
                        folder_report["copied"] += 1
                    folder_report["counts"] = dict(fc)
                    current["counts"] = dict(counts)
                    save(ROOT / "summary.json", summary)
                print(json.dumps({"account": account, **folder_report}), flush=True)
            current["status"] = "complete"
        except Exception as exc:
            current["status"] = "interrupted"
            current["error_type"] = type(exc).__name__
        finally:
            if client:
                try:
                    client.logout()
                except Exception:
                    pass
            save(ROOT / "summary.json", summary)
    summary["status"] = "complete" if all(v["status"] in {"complete", "credential_missing"} for v in summary["accounts"].values()) else "interrupted"
    save(ROOT / "summary.json", summary)
    print(json.dumps(summary), flush=True)

if __name__ == "__main__":
    main()
