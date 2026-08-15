"""SQLite storage for accounts, NNTP articles, IRC history and audit metadata."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Iterator

from .auth import hash_password, verify_password


DEFAULT_GROUPS = (
    ("wwcx.general", "General WW.CX discussion", 0),
    ("wwcx.announce", "WW.CX announcements", 1),
    ("wwcx.projects.bigbird", "Project Big Bird", 0),
    ("wwcx.projects.edge1", "Edge1 engineering and operations", 0),
    ("wwcx.telecom", "Telecommunications engineering", 0),
    ("wwcx.security", "Security engineering", 1),
    ("wwcx.test", "Protocol and client testing", 0),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Account:
    username: str
    roles: tuple[str, ...]
    enabled: bool

    def has_role(self, role: str) -> bool:
        return role in self.roles or "founder" in self.roles


class CommsStore:
    def __init__(self, path: str | Path, *, password_iterations: int = 240_000) -> None:
        self.path = Path(path)
        self.password_iterations = password_iterations
        self._lock = threading.RLock()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    salt_b64 TEXT NOT NULL,
                    digest_b64 TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS newsgroups (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    moderated INTEGER NOT NULL DEFAULT 0,
                    retention_days INTEGER NOT NULL DEFAULT 3650,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL REFERENCES newsgroups(name),
                    message_id TEXT NOT NULL UNIQUE,
                    author TEXT NOT NULL,
                    account TEXT,
                    subject TEXT NOT NULL,
                    date_rfc5322 TEXT NOT NULL,
                    references_text TEXT NOT NULL DEFAULT '',
                    headers_json TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_articles_group_id ON articles(group_name, id);
                CREATE TABLE IF NOT EXISTS irc_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    account TEXT,
                    nick TEXT NOT NULL,
                    event TEXT NOT NULL,
                    body TEXT,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_irc_history_channel_id ON irc_history(channel, id);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    actor TEXT,
                    protocol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    outcome TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                """
            )
            now = utc_now()
            for name, description, moderated in DEFAULT_GROUPS:
                conn.execute(
                    "INSERT OR IGNORE INTO newsgroups(name,description,moderated,retention_days,created_at_utc) VALUES(?,?,?,?,?)",
                    (name, description, moderated, 3650, now),
                )

    def add_account(self, username: str, password: str, roles: list[str] | tuple[str, ...]) -> None:
        clean = username.strip().lower()
        if not clean or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in clean):
            raise ValueError("username contains unsupported characters")
        role_values = sorted({role.strip().lower() for role in roles if role.strip()})
        salt, digest = hash_password(password, iterations=self.password_iterations)
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO accounts(username,salt_b64,digest_b64,roles_json,enabled,created_at_utc) VALUES(?,?,?,?,1,?)",
                (clean, salt, digest, json.dumps(role_values), utc_now()),
            )
        self.audit(clean, "control", "account.add", clean, "ok", {"roles": role_values})

    def set_account_password(self, username: str, password: str) -> bool:
        salt, digest = hash_password(password, iterations=self.password_iterations)
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                "UPDATE accounts SET salt_b64=?, digest_b64=? WHERE username=? COLLATE NOCASE",
                (salt, digest, username),
            )
        ok = cur.rowcount > 0
        self.audit(username, "control", "account.password", username, "ok" if ok else "missing", {})
        return ok

    def set_account_enabled(self, username: str, enabled: bool) -> bool:
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                "UPDATE accounts SET enabled=? WHERE username=? COLLATE NOCASE", (1 if enabled else 0, username)
            )
        ok = cur.rowcount > 0
        self.audit(username, "control", "account.enable" if enabled else "account.disable", username, "ok" if ok else "missing", {})
        return ok

    def get_account(self, username: str) -> Account | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT username,roles_json,enabled FROM accounts WHERE username=? COLLATE NOCASE", (username,)
            ).fetchone()
        if not row:
            return None
        try:
            roles = tuple(str(item) for item in json.loads(row["roles_json"]))
        except (json.JSONDecodeError, TypeError):
            roles = ()
        return Account(str(row["username"]), roles, bool(row["enabled"]))

    def authenticate(self, username: str, password: str, *, protocol: str) -> Account | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT username,salt_b64,digest_b64,roles_json,enabled FROM accounts WHERE username=? COLLATE NOCASE",
                (username,),
            ).fetchone()
        if not row or not bool(row["enabled"]):
            self.audit(username, protocol, "auth", username, "denied", {"reason": "unknown_or_disabled"})
            return None
        ok = verify_password(
            password,
            str(row["salt_b64"]),
            str(row["digest_b64"]),
            iterations=self.password_iterations,
        )
        self.audit(username, protocol, "auth", username, "ok" if ok else "denied", {})
        if not ok:
            return None
        return Account(str(row["username"]), tuple(json.loads(row["roles_json"])), True)

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT username,roles_json,enabled,created_at_utc FROM accounts ORDER BY username COLLATE NOCASE").fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["roles"] = json.loads(item.pop("roles_json"))
            item["enabled"] = bool(item["enabled"])
            result.append(item)
        return result

    def list_groups(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT g.name,g.description,g.moderated,g.retention_days,
                       COALESCE(MIN(a.id),0) AS low, COALESCE(MAX(a.id),0) AS high, COUNT(a.id) AS count
                FROM newsgroups g LEFT JOIN articles a ON a.group_name=g.name
                GROUP BY g.name ORDER BY g.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def group_info(self, group_name: str) -> dict[str, Any] | None:
        for row in self.list_groups():
            if row["name"] == group_name:
                return row
        return None

    def add_group(self, name: str, description: str, *, moderated: bool = False, retention_days: int = 3650) -> None:
        if not name or any(part == "" for part in name.split(".")):
            raise ValueError("invalid newsgroup name")
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO newsgroups(name,description,moderated,retention_days,created_at_utc) VALUES(?,?,?,?,?)",
                (name, description, 1 if moderated else 0, retention_days, utc_now()),
            )
        self.audit(None, "control", "group.add", name, "ok", {"moderated": moderated, "retention_days": retention_days})

    def can_post(self, account: Account | None, group_name: str) -> bool:
        info = self.group_info(group_name)
        if not info:
            return False
        if not info["moderated"]:
            return account is not None
        return account is not None and (account.has_role("moderator") or account.has_role(f"moderator:{group_name}"))

    def post_article(
        self,
        *,
        group_name: str,
        author: str,
        account: str | None,
        subject: str,
        body: str,
        references: str = "",
        extra_headers: dict[str, str] | None = None,
        message_id: str | None = None,
        server_name: str = "edge1.ww.cx",
    ) -> dict[str, Any]:
        if not self.group_info(group_name):
            raise ValueError("unknown newsgroup")
        now_dt = dt.datetime.now(dt.timezone.utc)
        msg_id = message_id or f"<{uuid.uuid4().hex}.{int(now_dt.timestamp())}@{server_name}>"
        date_header = format_datetime(now_dt)
        headers = {"From": author, "Subject": subject, "Newsgroups": group_name, "Message-ID": msg_id, "Date": date_header}
        if references:
            headers["References"] = references
        for key, value in (extra_headers or {}).items():
            if key.lower() not in {"from", "subject", "newsgroups", "message-id", "date", "references"}:
                headers[key] = value
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO articles(group_name,message_id,author,account,subject,date_rfc5322,references_text,headers_json,body,created_at_utc)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (group_name, msg_id, author, account, subject, date_header, references, json.dumps(headers, sort_keys=True), body, utc_now()),
            )
            article_id = int(cur.lastrowid)
        self.audit(account, "nntp", "post", group_name, "ok", {"message_id": msg_id, "article_id": article_id})
        return self.get_article(group_name=group_name, article_id=article_id) or {}

    def get_article(self, *, group_name: str | None = None, article_id: int | None = None, message_id: str | None = None) -> dict[str, Any] | None:
        with self.connect() as conn:
            if message_id is not None:
                row = conn.execute("SELECT * FROM articles WHERE message_id=?", (message_id,)).fetchone()
            elif article_id is not None and group_name is not None:
                row = conn.execute("SELECT * FROM articles WHERE id=? AND group_name=?", (article_id, group_name)).fetchone()
            else:
                return None
        if not row:
            return None
        result = dict(row)
        result["headers"] = json.loads(result.pop("headers_json"))
        return result

    def articles_for_group(self, group_name: str, *, start: int | None = None, end: int | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        query = "SELECT * FROM articles WHERE group_name=?"
        args: list[Any] = [group_name]
        if start is not None:
            query += " AND id>=?"
            args.append(start)
        if end is not None:
            query += " AND id<=?"
            args.append(end)
        query += " ORDER BY id LIMIT ?"
        args.append(max(1, min(limit, 5000)))
        with self.connect() as conn:
            rows = conn.execute(query, args).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["headers"] = json.loads(item.pop("headers_json"))
            result.append(item)
        return result

    def record_irc(self, channel: str, account: str | None, nick: str, event: str, body: str | None) -> None:
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO irc_history(channel,account,nick,event,body,created_at_utc) VALUES(?,?,?,?,?,?)",
                (channel, account, nick, event, body, utc_now()),
            )

    def recent_irc(self, channel: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM irc_history WHERE channel=? ORDER BY id DESC LIMIT ?", (channel, max(1, min(limit, 500)))
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def audit(self, actor: str | None, protocol: str, action: str, target: str | None, outcome: str, detail: dict[str, Any]) -> None:
        safe_detail = {key: value for key, value in detail.items() if key.lower() not in {"password", "credential", "body", "content"}}
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO audit(created_at_utc,actor,protocol,action,target,outcome,detail_json) VALUES(?,?,?,?,?,?,?)",
                (utc_now(), actor, protocol, action, target, outcome, json.dumps(safe_detail, sort_keys=True)),
            )

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json"))
            result.append(item)
        return result

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            accounts = int(conn.execute("SELECT COUNT(*) FROM accounts WHERE enabled=1").fetchone()[0])
            groups = int(conn.execute("SELECT COUNT(*) FROM newsgroups").fetchone()[0])
            articles = int(conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
            irc_events = int(conn.execute("SELECT COUNT(*) FROM irc_history").fetchone()[0])
        return {"enabled_accounts": accounts, "newsgroups": groups, "articles": articles, "irc_history_events": irc_events}
