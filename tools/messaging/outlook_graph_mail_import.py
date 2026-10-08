#!/usr/bin/env python3
"""Read-only Microsoft Graph intake for spiritcreekgardens@outlook.com.

The worker uses delegated Mail.Read only, preserves exact MIME originals in a private
archive, maintains per-folder Graph delta cursors, and projects bounded text into the
existing Mail Room. It never sends, deletes, moves, marks-read, or otherwise mutates
provider mail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))
from server.mail_room_security import stage_provider
from mail_correspondence_store import MailCorrespondenceStore
from mail_local_rfc822_source import normalize_rfc822

ACCOUNT = "spiritcreekgardens@outlook.com"
SOURCE = "outlook-spiritcreekgardens-graph"
PROVIDER_SOURCE = "microsoft-graph-outlook"
CONFIG = Path("/etc/wwcx/outlook-graph-mail.json")
STATE_ROOT = Path("/var/lib/wwcx-mail-room/outlook-graph")
STATE_DB = STATE_ROOT / "state.sqlite3"
TOKEN_CACHE = STATE_ROOT / "token-cache.json"
STATUS = STATE_ROOT / "status.json"
ARCHIVE = Path("/var/lib/wwcx-mail-room/imports/outlook-spiritcreekgardens")
CORRESPONDENCE = Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
GRAPH = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPES = "offline_access https://graph.microsoft.com/Mail.Read"
FOLDERS = {
    "inbox": {"well_known": "inbox", "direction": "inbound", "class": "mail"},
    "sent": {"well_known": "sentitems", "direction": "outbound", "class": "mail"},
    "archive": {"well_known": "archive", "direction": "inbound", "class": "mail"},
    "junk": {"well_known": "junkemail", "direction": "inbound", "class": "junk"},
}
MAX_GRAPH_BYTES = 150 * 1024 * 1024
MAX_BODY = 90_000


class GraphError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_json(path: Path, value: dict, mode: int = 0o600) -> None:
    atomic_write(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode(), mode)


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {} if default is None else default


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_state() -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    ARCHIVE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(STATE_DB) as db:
        db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS folder_state(
              folder_key TEXT PRIMARY KEY,
              delta_url TEXT,
              phase TEXT NOT NULL DEFAULT 'initial',
              last_success TEXT,
              last_error TEXT,
              pages INTEGER NOT NULL DEFAULT 0,
              observed INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS observations(
              graph_id TEXT NOT NULL,
              folder_key TEXT NOT NULL,
              internet_message_id TEXT,
              raw_sha256 TEXT,
              projection_status TEXT,
              observed_at TEXT NOT NULL,
              etag TEXT,
              PRIMARY KEY(graph_id, folder_key)
            );
            CREATE INDEX IF NOT EXISTS observations_mid_idx ON observations(internet_message_id);
            CREATE INDEX IF NOT EXISTS observations_sha_idx ON observations(raw_sha256);
            """
        )
        for key in FOLDERS:
            db.execute("INSERT OR IGNORE INTO folder_state(folder_key) VALUES(?)", (key,))
    os.chmod(STATE_DB, 0o600)


def config() -> dict:
    value = load_json(CONFIG, {})
    client_id = str(value.get("client_id", "")).strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{30,64}", client_id):
        raise RuntimeError("Microsoft Graph client_id is not configured")
    account = str(value.get("account", ACCOUNT)).strip().lower()
    if account != ACCOUNT:
        raise RuntimeError("Configured Outlook account does not match approved account")
    return {"client_id": client_id, "account": account}


def form_post(url: str, fields: dict[str, str], timeout=45) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        data = exc.read(1024 * 1024)
        try:
            payload = json.loads(data)
            detail = payload.get("error_description") or payload.get("error") or f"HTTP {exc.code}"
        except Exception:
            detail = f"HTTP {exc.code}"
        raise GraphError(detail, exc.code) from exc


def token_from_refresh() -> str:
    cfg = config()
    cache = load_json(TOKEN_CACHE, {})
    refresh = str(cache.get("refresh_token", ""))
    if not refresh:
        raise RuntimeError("Microsoft authorization has not been completed")
    result = form_post(AUTHORITY + "/token", {
        "client_id": cfg["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "scope": SCOPES,
    })
    if not result.get("access_token"):
        raise RuntimeError("Microsoft token refresh returned no access token")
    next_cache = {
        "refresh_token": result.get("refresh_token", refresh),
        "scope": result.get("scope", ""),
        "token_type": result.get("token_type", "Bearer"),
        "updated_at": utcnow(),
    }
    save_json(TOKEN_CACHE, next_cache)
    return str(result["access_token"])


def graph_request(url: str, token: str, *, mime=False, retries=4):
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "message/rfc822" if mime else "application/json",
        "Prefer": 'IdType="ImmutableId"' + ("" if mime else ", odata.maxpagesize=50"),
        "User-Agent": "Edge1-Mail-Room-Outlook-Graph/1.0",
    }
    for attempt in range(retries):
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(MAX_GRAPH_BYTES + 1)
                if len(data) > MAX_GRAPH_BYTES:
                    raise GraphError("Graph MIME message exceeds archive size limit")
                return data if mime else json.loads(data)
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 503, 504} and attempt + 1 < retries:
                delay = min(60, max(1, int(exc.headers.get("Retry-After", "2"))))
                time.sleep(delay)
                continue
            detail = f"Microsoft Graph HTTP {exc.code}"
            try:
                payload = json.loads(exc.read(1024 * 1024))
                detail = payload.get("error", {}).get("message", detail)
            except Exception:
                pass
            raise GraphError(detail, exc.code) from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < retries:
                time.sleep(min(10, 2 ** attempt))
                continue
            raise GraphError("Microsoft Graph network request failed") from exc
    raise GraphError("Microsoft Graph request failed")


def canonical_mid(value: str) -> bool:
    return bool(re.fullmatch(r"<[^<>\r\n\s]+@[^<>\r\n\s]+>", value or "")) and len(value) <= 998


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}: self.hidden += 1
        if tag in {"p", "br", "div", "li", "tr"} and not self.hidden: self.text.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"} and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden: self.text.append(data)


def body_text(message) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        try:
            content = part.get_content()
        except Exception:
            continue
        if not isinstance(content, str):
            continue
        if part.get_content_type() == "text/plain": plain.append(content)
        elif part.get_content_type() == "text/html": html.append(content)
    text = "\n".join(plain)
    if not text and html:
        parser = PlainHTML()
        for chunk in html:
            try: parser.feed(chunk)
            except Exception: pass
            parser.text.append("\n")
        text = "".join(parser.text)
    return text.replace("\x00", "")[:MAX_BODY]


def graph_addresses(item: dict, key: str) -> list[str]:
    result = []
    for entry in item.get(key, []) or []:
        address = str((entry.get("emailAddress") or {}).get("address", "")).strip()
        if address.count("@") == 1 and "\r" not in address and "\n" not in address:
            result.append(address)
    return result


def first_valid_address(values) -> str | None:
    addresses = [a for _, a in getaddresses(values) if a and a.count("@") == 1 and "\r" not in a and "\n" not in a]
    return addresses[0] if len(addresses) == 1 else None


def iso_to_rfc2822(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_projection(raw: bytes, item: dict, direction: str, message_id: str) -> bytes:
    original = BytesParser(policy=policy.default).parsebytes(raw)
    projected = EmailMessage(policy=policy.default)
    raw_sender = first_valid_address(original.get_all("From", []))
    graph_sender = str(((item.get("from") or item.get("sender") or {}).get("emailAddress") or {}).get("address", "")).strip()
    sender = raw_sender or (graph_sender if graph_sender.count("@") == 1 else None) or (ACCOUNT if direction == "outbound" else None)
    if not sender:
        raise RuntimeError("message sender cannot be normalized")
    recipients = [a for _, a in getaddresses(original.get_all("To", []) + original.get_all("Cc", [])) if a.count("@") == 1]
    if not recipients:
        recipients = graph_addresses(item, "toRecipients") + graph_addresses(item, "ccRecipients")
    if not recipients and direction == "inbound": recipients = [ACCOUNT]
    if not recipients:
        raise RuntimeError("message recipients cannot be normalized")
    projected["From"] = sender
    projected["To"] = ", ".join(dict.fromkeys(recipients[:100]))
    projected["Subject"] = str(original.get("Subject", item.get("subject", "")))[:998].replace("\x00", "")
    projected["Message-ID"] = message_id
    date_value = str(original.get("Date", "")).strip()
    try:
        parsed = parsedate_to_datetime(date_value) if date_value else None
        if parsed is None or parsed.tzinfo is None: raise ValueError()
        projected["Date"] = date_value
    except Exception:
        fallback = str(item.get("sentDateTime") or item.get("receivedDateTime") or utcnow())
        projected["Date"] = iso_to_rfc2822(fallback)
    for header in ("In-Reply-To", "References"):
        tokens = re.findall(r"<[^<>\r\n\s]+@[^<>\r\n\s]+>", str(original.get(header, "")))[:100]
        if tokens: projected[header] = " ".join(tokens)
    projected.set_content(body_text(original))
    return projected.as_bytes()


def security_bytes(raw: bytes, message_id: str) -> bytes:
    original = str(BytesParser(policy=policy.default).parsebytes(raw, headersonly=True).get("Message-ID", "")).strip()
    if original == message_id:
        return raw
    # The exact original remains separately archived. The security copy differs only by
    # adding a deterministic Message-ID needed by the existing decision-key contract.
    return (f"Message-ID: {message_id}\r\n".encode("ascii") + raw)


def archive_original(raw: bytes, folder_key: str, graph_id: str, item: dict) -> tuple[str, Path]:
    digest = hashlib.sha256(raw).hexdigest()
    target = ARCHIVE / "objects" / digest[:2] / digest
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    eml = target / "message.eml"
    if not eml.exists(): atomic_write(eml, raw)
    elif hashlib.sha256(eml.read_bytes()).hexdigest() != digest: raise RuntimeError("Outlook archive integrity mismatch")
    metadata = target / "metadata.json"
    if not metadata.exists():
        save_json(metadata, {
            "contract": "wwcx.outlook-graph-original.v1",
            "account": ACCOUNT,
            "source": SOURCE,
            "sha256": digest,
            "bytes": len(raw),
            "first_observed_folder": folder_key,
            "first_graph_id_sha256": hashlib.sha256(graph_id.encode()).hexdigest(),
            "internet_message_id": item.get("internetMessageId"),
            "archived_at": utcnow(),
            "provider_mutations": False,
        })
    return digest, eml


def correspondence_exists(mid: str) -> bool:
    with sqlite3.connect(CORRESPONDENCE) as db:
        return db.execute("SELECT 1 FROM correspondence WHERE message_id=?", (mid,)).fetchone() is not None


def native_raw_exists(digest: str) -> bool:
    root = Path("/var/lib/wwcx-mail-gateway/inbound")
    # Bounded metadata lookup; exact message-id dedupe normally resolves before this path.
    for meta in root.glob("*/*/metadata.json"):
        try:
            if meta.stat().st_size < 65536 and json.loads(meta.read_text()).get("rfc822_sha256") == digest:
                return True
        except (OSError, ValueError):
            continue
    return False


def mark_observation(graph_id, folder_key, item, digest, projection_status):
    with sqlite3.connect(STATE_DB) as db:
        db.execute(
            """INSERT INTO observations(graph_id,folder_key,internet_message_id,raw_sha256,projection_status,observed_at,etag)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(graph_id,folder_key) DO UPDATE SET
            internet_message_id=excluded.internet_message_id,raw_sha256=excluded.raw_sha256,
            projection_status=excluded.projection_status,observed_at=excluded.observed_at,etag=excluded.etag""",
            (graph_id, folder_key, item.get("internetMessageId"), digest, projection_status, utcnow(), item.get("@odata.etag")),
        )


def process_message(token: str, folder_key: str, item: dict, store: MailCorrespondenceStore) -> str:
    graph_id = str(item.get("id", ""))
    if not graph_id: return "ignored"
    raw = graph_request(f"{GRAPH}/me/messages/{urllib.parse.quote(graph_id, safe='')}/$value", token, mime=True)
    digest, _ = archive_original(raw, folder_key, graph_id, item)
    original_mid = str(BytesParser(policy=policy.default).parsebytes(raw, headersonly=True).get("Message-ID", "")).strip()
    advertised_mid = str(item.get("internetMessageId") or "").strip()
    mid = original_mid if canonical_mid(original_mid) else advertised_mid if canonical_mid(advertised_mid) else f"<outlook-{digest}@archive.ww.cx>"
    if correspondence_exists(mid) or native_raw_exists(digest):
        mark_observation(graph_id, folder_key, item, digest, "duplicate")
        return "duplicate"
    scan_raw = security_bytes(raw, mid)
    stage_provider(scan_raw, ACCOUNT, mid, provider_source=PROVIDER_SOURCE)
    scan_digest = hashlib.sha256(scan_raw).hexdigest()
    scan_meta = Path("/var/lib/wwcx-mail-gateway/inbound") / "outlook.com" / ("imap-" + scan_digest[:24]) / "metadata.json"
    if scan_meta.exists():
        meta = json.loads(scan_meta.read_text())
        meta["provider_folder"] = folder_key
        meta["provider_folder_class"] = FOLDERS[folder_key]["class"]
        meta["provider_account"] = ACCOUNT
        save_json(scan_meta, meta)
    projection = build_projection(raw, item, FOLDERS[folder_key]["direction"], mid)
    normalize_rfc822(projection, store, direction=FOLDERS[folder_key]["direction"])
    mark_observation(graph_id, folder_key, item, digest, "imported")
    return "imported"


def initial_delta(folder_key: str) -> str:
    folder = FOLDERS[folder_key]["well_known"]
    select = "id,internetMessageId,subject,receivedDateTime,sentDateTime,from,sender,toRecipients,ccRecipients,isRead,parentFolderId"
    return f"{GRAPH}/me/mailFolders/{folder}/messages/delta?" + urllib.parse.urlencode({"$select": select})


def update_folder_state(folder_key: str, **values) -> None:
    allowed = {"delta_url", "phase", "last_success", "last_error", "pages", "observed"}
    values = {k: v for k, v in values.items() if k in allowed}
    if not values: return
    with sqlite3.connect(STATE_DB) as db:
        sql = "UPDATE folder_state SET " + ",".join(k + "=?" for k in values) + " WHERE folder_key=?"
        db.execute(sql, (*values.values(), folder_key))


def folder_row(folder_key: str) -> dict:
    with sqlite3.connect(STATE_DB) as db:
        db.row_factory = sqlite3.Row
        return dict(db.execute("SELECT * FROM folder_state WHERE folder_key=?", (folder_key,)).fetchone())


def status_payload(running=False, counts=None, error=None) -> dict:
    with sqlite3.connect(STATE_DB) as db:
        db.row_factory = sqlite3.Row
        folders = {r["folder_key"]: dict(r) for r in db.execute("SELECT * FROM folder_state ORDER BY folder_key")}
        totals = dict(db.execute("SELECT projection_status,count(*) FROM observations GROUP BY projection_status").fetchall())
    complete = all(v.get("phase") == "delta" for v in folders.values())
    last_successes = [v.get("last_success") for v in folders.values() if v.get("last_success")]
    return {
        "contract": "wwcx.outlook-graph-sync-status.v1",
        "account": ACCOUNT,
        "source": SOURCE,
        "authorization": "configured" if TOKEN_CACHE.exists() else "required",
        "running": bool(running),
        "historical_complete": complete,
        "backlog": 0 if complete else "initial_sync_in_progress",
        "last_successful_sync": max(last_successes) if last_successes else None,
        "folders": folders,
        "totals": totals,
        "last_run_counts": counts or {},
        "error": error,
        "updated_at": utcnow(),
        "provider_mutations": False,
        "permissions": ["Mail.Read", "offline_access"],
    }


def sync(max_pages: int, max_messages: int) -> dict:
    init_state()
    counts = {"imported": 0, "duplicate": 0, "ignored": 0, "removed": 0, "errors": 0}
    save_json(STATUS, status_payload(running=True, counts=counts))
    token = token_from_refresh()
    store = MailCorrespondenceStore(CORRESPONDENCE, source=SOURCE, source_authoritative=True, source_scope="production_native")
    total_pages = 0
    total_messages = 0
    try:
        for folder_key in FOLDERS:
            row = folder_row(folder_key)
            url = row.get("delta_url") or initial_delta(folder_key)
            pages = int(row.get("pages") or 0)
            observed = int(row.get("observed") or 0)
            while url and total_pages < max_pages and total_messages < max_messages:
                try:
                    payload = graph_request(url, token)
                except GraphError as exc:
                    if exc.status == 404 and row.get("phase") == "initial":
                        update_folder_state(folder_key, phase="unavailable", last_error="folder unavailable", last_success=utcnow())
                        break
                    raise
                for item in payload.get("value", []):
                    if "@removed" in item:
                        counts["removed"] += 1
                        continue
                    try:
                        state = process_message(token, folder_key, item, store)
                        counts[state] = counts.get(state, 0) + 1
                    except Exception:
                        counts["errors"] += 1
                        mark_observation(str(item.get("id", "unknown")), folder_key, item, "", "error")
                    total_messages += 1
                    observed += 1
                total_pages += 1
                pages += 1
                next_url = payload.get("@odata.nextLink")
                delta_url = payload.get("@odata.deltaLink")
                if delta_url:
                    update_folder_state(folder_key, delta_url=delta_url, phase="delta", last_success=utcnow(), last_error=None, pages=pages, observed=observed)
                    url = None
                elif next_url:
                    # Persist nextLink so interruption resumes on the exact page.
                    update_folder_state(folder_key, delta_url=next_url, phase=row.get("phase") or "initial", last_success=utcnow(), last_error=None, pages=pages, observed=observed)
                    url = next_url
                else:
                    raise RuntimeError("Graph delta response had neither nextLink nor deltaLink")
                save_json(STATUS, status_payload(running=True, counts=counts))
            if total_pages >= max_pages or total_messages >= max_messages: break
        result = status_payload(running=False, counts=counts)
        save_json(STATUS, result)
        return result
    except Exception as exc:
        result = status_payload(running=False, counts=counts, error={"type": type(exc).__name__, "message": str(exc)[:300]})
        save_json(STATUS, result)
        raise


def authorize() -> None:
    init_state()
    cfg = config()
    device = form_post(AUTHORITY + "/devicecode", {"client_id": cfg["client_id"], "scope": SCOPES})
    # No token or secret is emitted; only Microsoft's short-lived user code and URL.
    print(device.get("message") or f"Open {device['verification_uri']} and enter code {device['user_code']}", flush=True)
    deadline = time.time() + int(device.get("expires_in", 900))
    interval = max(5, int(device.get("interval", 5)))
    while time.time() < deadline:
        time.sleep(interval)
        try:
            result = form_post(AUTHORITY + "/token", {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": cfg["client_id"],
                "device_code": device["device_code"],
            })
        except GraphError as exc:
            text = str(exc).lower()
            if "authorization_pending" in text: continue
            if "slow_down" in text:
                interval += 5
                continue
            raise
        if result.get("refresh_token") and result.get("access_token"):
            save_json(TOKEN_CACHE, {
                "refresh_token": result["refresh_token"],
                "scope": result.get("scope", ""),
                "token_type": result.get("token_type", "Bearer"),
                "updated_at": utcnow(),
            })
            print("Microsoft authorization stored on Edge1. No token was printed.")
            return
    raise RuntimeError("Microsoft device authorization expired before completion")


def show_status() -> None:
    init_state()
    if not STATUS.exists(): save_json(STATUS, status_payload())
    print(json.dumps(load_json(STATUS), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("authorize")
    syncp = sub.add_parser("sync")
    syncp.add_argument("--max-pages", type=int, default=40)
    syncp.add_argument("--max-messages", type=int, default=1000)
    sub.add_parser("status")
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == "authorize": authorize()
    elif args.command == "sync": print(json.dumps(sync(max(1, min(args.max_pages, 200)), max(1, min(args.max_messages, 5000))), sort_keys=True))
    else: show_status()


if __name__ == "__main__":
    main()
