"""Durable SQLite storage for Edge1 Communications Relay."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Iterator

from .auth import hash_password, verify_password

DEFAULT_GROUPS = (
    ('wwcx.general', 'General WW.CX discussion', 0),
    ('wwcx.announce', 'WW.CX announcements', 1),
    ('wwcx.projects.bigbird', 'Project Big Bird', 0),
    ('wwcx.projects.edge1', 'Edge1 engineering and operations', 0),
    ('wwcx.telecom', 'Telecommunications engineering', 0),
    ('wwcx.security', 'Security engineering', 1),
    ('wwcx.test', 'Protocol and client testing', 0),
)
GROUP_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9+_-]*(?:\.[A-Za-z0-9][A-Za-z0-9+_-]*)+$')
MESSAGE_ID_RE = re.compile(r'^<[^<>\s@]+@[^<>\s@]+>$')


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _cutoff(days: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _safe_header(value: str, name: str, *, limit: int = 998) -> str:
    clean = value.strip()
    if not clean or '\r' in clean or '\n' in clean or len(clean.encode()) > limit:
        raise ValueError(f'invalid {name}')
    return clean


def _safe_ingest_token(value: str, name: str, *, limit: int) -> str:
    clean = value.strip()
    if not clean or '\r' in clean or '\n' in clean or len(clean.encode()) > limit:
        raise ValueError(f'invalid {name}')
    return clean


@dataclass(frozen=True)
class Account:
    username: str
    roles: tuple[str, ...]
    enabled: bool

    def has_role(self, role: str) -> bool:
        return role in self.roles or 'founder' in self.roles


class CommsStore:
    def __init__(
        self,
        path: str | Path,
        *,
        password_iterations: int = 600_000,
        min_password_length: int = 12,
        default_news_days: int = 3650,
        irc_history_days: int = 30,
        audit_days: int = 365,
    ) -> None:
        self.path = Path(path)
        self.password_iterations = password_iterations
        self.min_password_length = min_password_length
        self.default_news_days = default_news_days
        self.irc_history_days = irc_history_days
        self.audit_days = audit_days
        self._lock = threading.RLock()
        if str(self.path) != ':memory:':
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.path.parent, 0o750)
            except OSError:
                pass
        self._initialize()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=5000')
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self.connect() as conn:
            if str(self.path) != ':memory:':
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA wal_autocheckpoint=1000')
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS accounts(
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    salt_b64 TEXT NOT NULL,
                    digest_b64 TEXT NOT NULL,
                    password_iterations INTEGER NOT NULL DEFAULT 240000,
                    roles_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS newsgroups(
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    moderated INTEGER NOT NULL DEFAULT 0,
                    retention_days INTEGER NOT NULL DEFAULT 3650,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS articles(
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
                CREATE INDEX IF NOT EXISTS idx_articles_group_id ON articles(group_name,id);
                CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at_utc);
                CREATE TABLE IF NOT EXISTS irc_history(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    account TEXT,
                    nick TEXT NOT NULL,
                    event TEXT NOT NULL,
                    body TEXT,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_irc_history_channel_id ON irc_history(channel,id);
                CREATE INDEX IF NOT EXISTS idx_irc_history_created ON irc_history(created_at_utc);
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    actor TEXT,
                    protocol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    outcome TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_created ON audit(created_at_utc);
                CREATE TABLE IF NOT EXISTS ingest_items(
                    source_name TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
                    detail_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY(source_name,source_item_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ingest_items_article ON ingest_items(article_id);
                CREATE TABLE IF NOT EXISTS ingest_state(
                    source_name TEXT PRIMARY KEY,
                    cursor TEXT,
                    updated_at_utc TEXT NOT NULL
                );
                '''
            )
            columns = {str(row['name']) for row in conn.execute('PRAGMA table_info(accounts)').fetchall()}
            if 'password_iterations' not in columns:
                conn.execute('ALTER TABLE accounts ADD COLUMN password_iterations INTEGER NOT NULL DEFAULT 240000')
            now = utc_now()
            for name, description, moderated in DEFAULT_GROUPS:
                conn.execute(
                    'INSERT OR IGNORE INTO newsgroups(name,description,moderated,retention_days,created_at_utc) VALUES(?,?,?,?,?)',
                    (name, description, moderated, self.default_news_days, now),
                )
        if str(self.path) != ':memory:' and self.path.exists():
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def _validate_password(self, password: str) -> None:
        if len(password) < self.min_password_length:
            raise ValueError(f'password must contain at least {self.min_password_length} characters')
        if len(password.encode()) > 1024:
            raise ValueError('password is too long')

    def add_account(self, username: str, password: str, roles: list[str] | tuple[str, ...]) -> None:
        clean = username.strip().lower()
        if not clean or len(clean) > 64 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789._-' for c in clean):
            raise ValueError('username contains unsupported characters')
        self._validate_password(password)
        role_values = sorted({role.strip().lower() for role in roles if role.strip()})
        salt, digest = hash_password(password, iterations=self.password_iterations)
        with self._lock, self.connect() as conn:
            conn.execute(
                'INSERT INTO accounts(username,salt_b64,digest_b64,password_iterations,roles_json,enabled,created_at_utc) VALUES(?,?,?,?,?,1,?)',
                (clean, salt, digest, self.password_iterations, json.dumps(role_values), utc_now()),
            )
        self.audit(clean, 'control', 'account.add', clean, 'ok', {'roles': role_values})

    def set_account_password(self, username: str, password: str) -> bool:
        self._validate_password(password)
        salt, digest = hash_password(password, iterations=self.password_iterations)
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                'UPDATE accounts SET salt_b64=?,digest_b64=?,password_iterations=? WHERE username=? COLLATE NOCASE',
                (salt, digest, self.password_iterations, username),
            )
        ok = cur.rowcount > 0
        self.audit(username, 'control', 'account.password', username, 'ok' if ok else 'missing', {})
        return ok

    def set_account_enabled(self, username: str, enabled: bool) -> bool:
        with self._lock, self.connect() as conn:
            cur = conn.execute('UPDATE accounts SET enabled=? WHERE username=? COLLATE NOCASE', (1 if enabled else 0, username))
        ok = cur.rowcount > 0
        self.audit(username, 'control', 'account.enable' if enabled else 'account.disable', username, 'ok' if ok else 'missing', {})
        return ok

    def get_account(self, username: str) -> Account | None:
        with self.connect() as conn:
            row = conn.execute('SELECT username,roles_json,enabled FROM accounts WHERE username=? COLLATE NOCASE', (username,)).fetchone()
        if not row:
            return None
        try:
            roles = tuple(str(x) for x in json.loads(row['roles_json']))
        except (json.JSONDecodeError, TypeError):
            roles = ()
        return Account(str(row['username']), roles, bool(row['enabled']))

    def authenticate(self, username: str, password: str, *, protocol: str) -> Account | None:
        with self.connect() as conn:
            row = conn.execute(
                'SELECT username,salt_b64,digest_b64,password_iterations,roles_json,enabled FROM accounts WHERE username=? COLLATE NOCASE',
                (username,),
            ).fetchone()
        if not row or not bool(row['enabled']):
            self.audit(username, protocol, 'auth', username, 'denied', {'reason': 'unknown_or_disabled'})
            return None
        ok = verify_password(password, str(row['salt_b64']), str(row['digest_b64']), iterations=int(row['password_iterations']))
        self.audit(username, protocol, 'auth', username, 'ok' if ok else 'denied', {})
        if not ok:
            return None
        try:
            roles = tuple(str(x) for x in json.loads(row['roles_json']))
        except (json.JSONDecodeError, TypeError):
            roles = ()
        return Account(str(row['username']), roles, True)

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute('SELECT username,roles_json,enabled,created_at_utc FROM accounts ORDER BY username COLLATE NOCASE').fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item['roles'] = json.loads(item.pop('roles_json'))
            item['enabled'] = bool(item['enabled'])
            out.append(item)
        return out

    def list_groups(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                'SELECT g.name,g.description,g.moderated,g.retention_days,COALESCE(MIN(a.id),0) AS low,COALESCE(MAX(a.id),0) AS high,COUNT(a.id) AS count FROM newsgroups g LEFT JOIN articles a ON a.group_name=g.name GROUP BY g.name ORDER BY g.name'
            ).fetchall()
        return [dict(row) for row in rows]

    def group_info(self, group_name: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                'SELECT g.name,g.description,g.moderated,g.retention_days,COALESCE(MIN(a.id),0) AS low,COALESCE(MAX(a.id),0) AS high,COUNT(a.id) AS count FROM newsgroups g LEFT JOIN articles a ON a.group_name=g.name WHERE g.name=? GROUP BY g.name',
                (group_name,),
            ).fetchone()
        return dict(row) if row else None

    def add_group(self, name: str, description: str, *, moderated: bool = False, retention_days: int | None = None) -> None:
        clean = name.strip().lower()
        days = self.default_news_days if retention_days is None else retention_days
        if not GROUP_RE.match(clean) or len(clean) > 160:
            raise ValueError('invalid newsgroup name')
        if not 1 <= days <= 36500:
            raise ValueError('retention_days out of range')
        description = _safe_header(description, 'newsgroup description', limit=512)
        with self._lock, self.connect() as conn:
            conn.execute(
                'INSERT INTO newsgroups(name,description,moderated,retention_days,created_at_utc) VALUES(?,?,?,?,?)',
                (clean, description, 1 if moderated else 0, days, utc_now()),
            )
        self.audit(None, 'control', 'group.add', clean, 'ok', {'moderated': moderated, 'retention_days': days})

    def can_post(self, account: Account | None, group_name: str) -> bool:
        info = self.group_info(group_name)
        if not info or account is None or not account.enabled:
            return False
        if not info['moderated']:
            return True
        return account.has_role('moderator') or account.has_role(f'moderator:{group_name}')

    def _prepare_article(self, *, group_name: str, author: str, subject: str, references: str, extra_headers: dict[str, str] | None, message_id: str) -> tuple[str, str, str, dict[str, str], str]:
        if not self.group_info(group_name):
            raise ValueError('unknown newsgroup')
        author = _safe_header(author, 'From')
        subject = _safe_header(subject, 'Subject')
        references = references.strip()
        if '\r' in references or '\n' in references or len(references.encode()) > 4096:
            raise ValueError('invalid References')
        if not MESSAGE_ID_RE.match(message_id):
            raise ValueError('invalid Message-ID')
        date = format_datetime(dt.datetime.now(dt.timezone.utc))
        headers = {'From': author, 'Subject': subject, 'Newsgroups': group_name, 'Message-ID': message_id, 'Date': date}
        if references:
            headers['References'] = references
        for key, value in (extra_headers or {}).items():
            if key.lower() in {'from', 'subject', 'newsgroups', 'message-id', 'date', 'references'} or not key or any(c in key for c in '\r\n:'):
                continue
            headers[key] = _safe_header(str(value), key)
        return author, subject, references, headers, date

    def post_article(self, *, group_name: str, author: str, account: str | None, subject: str, body: str, references: str = '', extra_headers: dict[str, str] | None = None, message_id: str | None = None, server_name: str = 'edge1.ww.cx') -> dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc)
        msg_id = message_id or f'<{uuid.uuid4().hex}.{int(now.timestamp())}@{server_name}>'
        author, subject, references, headers, date = self._prepare_article(group_name=group_name, author=author, subject=subject, references=references, extra_headers=extra_headers, message_id=msg_id)
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                'INSERT INTO articles(group_name,message_id,author,account,subject,date_rfc5322,references_text,headers_json,body,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (group_name, msg_id, author, account, subject, date, references, json.dumps(headers, sort_keys=True), body, utc_now()),
            )
            article_id = int(cur.lastrowid)
        self.audit(account, 'nntp', 'post', group_name, 'ok', {'message_id': msg_id, 'article_id': article_id})
        return self.get_article(group_name=group_name, article_id=article_id) or {}

    def post_ingested_article(self, *, source_name: str, source_item_id: str, group_name: str, subject: str, body: str, server_name: str, author: str = 'WW.CX Relay <relay@edge1.ww.cx>', extra_headers: dict[str, str] | None = None, detail: dict[str, Any] | None = None) -> dict[str, Any]:
        source_name = _safe_ingest_token(source_name, 'source_name', limit=128)
        source_item_id = _safe_ingest_token(source_item_id, 'source_item_id', limit=512)
        digest = hashlib.sha256(f'{source_name}\0{source_item_id}'.encode()).hexdigest()
        message_id = f'<ingest.{digest}@{server_name}>'
        headers_in = dict(extra_headers or {})
        headers_in.setdefault('X-WWCX-Automated', 'yes')
        headers_in.setdefault('X-WWCX-Source', source_name)
        headers_in.setdefault('X-WWCX-Source-ID', source_item_id)
        author, subject, references, headers, date = self._prepare_article(group_name=group_name, author=author, subject=subject, references='', extra_headers=headers_in, message_id=message_id)
        safe_detail = {k: v for k, v in (detail or {}).items() if k.lower() not in {'password', 'credential', 'body', 'content', 'secret', 'token'}}
        with self._lock, self.connect() as conn:
            existing = conn.execute(
                'SELECT i.article_id,a.message_id FROM ingest_items i LEFT JOIN articles a ON a.id=i.article_id WHERE i.source_name=? AND i.source_item_id=?',
                (source_name, source_item_id),
            ).fetchone()
            if existing:
                return {'created': False, 'article_id': existing['article_id'], 'message_id': existing['message_id']}
            cur = conn.execute(
                'INSERT INTO articles(group_name,message_id,author,account,subject,date_rfc5322,references_text,headers_json,body,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (group_name, message_id, author, None, subject, date, references, json.dumps(headers, sort_keys=True), body, utc_now()),
            )
            article_id = int(cur.lastrowid)
            conn.execute(
                'INSERT INTO ingest_items(source_name,source_item_id,article_id,detail_json,created_at_utc) VALUES(?,?,?,?,?)',
                (source_name, source_item_id, article_id, json.dumps(safe_detail, sort_keys=True), utc_now()),
            )
        self.audit(None, 'ingest', 'article.ingest', group_name, 'ok', {'source': source_name, 'source_item_id': source_item_id, 'article_id': article_id})
        return {'created': True, 'article_id': article_id, 'message_id': message_id}

    def ingest_seen(self, source_name: str, source_item_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute('SELECT 1 FROM ingest_items WHERE source_name=? AND source_item_id=?', (source_name, source_item_id)).fetchone()
        return row is not None

    def ingest_count(self, source_name: str | None = None) -> int:
        with self.connect() as conn:
            row = conn.execute('SELECT COUNT(*) FROM ingest_items').fetchone() if source_name is None else conn.execute('SELECT COUNT(*) FROM ingest_items WHERE source_name=?', (source_name,)).fetchone()
        return int(row[0])

    def get_ingest_cursor(self, source_name: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute('SELECT cursor FROM ingest_state WHERE source_name=?', (source_name,)).fetchone()
        return str(row['cursor']) if row and row['cursor'] is not None else None

    def set_ingest_cursor(self, source_name: str, cursor: str | None) -> None:
        source_name = _safe_ingest_token(source_name, 'source_name', limit=128)
        if cursor is not None:
            cursor = _safe_ingest_token(cursor, 'cursor', limit=512)
        with self._lock, self.connect() as conn:
            conn.execute(
                'INSERT INTO ingest_state(source_name,cursor,updated_at_utc) VALUES(?,?,?) ON CONFLICT(source_name) DO UPDATE SET cursor=excluded.cursor,updated_at_utc=excluded.updated_at_utc',
                (source_name, cursor, utc_now()),
            )

    def list_ingest_state(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                'SELECT s.source_name,s.cursor,s.updated_at_utc,COUNT(i.source_item_id) AS items FROM ingest_state s LEFT JOIN ingest_items i ON i.source_name=s.source_name GROUP BY s.source_name,s.cursor,s.updated_at_utc ORDER BY s.source_name'
            ).fetchall()
        return [dict(row) for row in rows]

    def get_article(self, *, group_name: str | None = None, article_id: int | None = None, message_id: str | None = None) -> dict[str, Any] | None:
        with self.connect() as conn:
            if message_id is not None:
                row = conn.execute('SELECT * FROM articles WHERE message_id=?', (message_id,)).fetchone()
            elif article_id is not None and group_name is not None:
                row = conn.execute('SELECT * FROM articles WHERE id=? AND group_name=?', (article_id, group_name)).fetchone()
            else:
                row = None
        if not row:
            return None
        result = dict(row)
        result['headers'] = json.loads(result.pop('headers_json'))
        return result

    def articles_for_group(self, group_name: str, *, start: int | None = None, end: int | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        query = 'SELECT * FROM articles WHERE group_name=?'
        args: list[Any] = [group_name]
        if start is not None:
            query += ' AND id>=?'
            args.append(start)
        if end is not None:
            query += ' AND id<=?'
            args.append(end)
        query += ' ORDER BY id LIMIT ?'
        args.append(max(1, min(limit, 5000)))
        with self.connect() as conn:
            rows = conn.execute(query, args).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item['headers'] = json.loads(item.pop('headers_json'))
            out.append(item)
        return out

    def record_irc(self, channel: str, account: str | None, nick: str, event: str, body: str | None) -> None:
        with self._lock, self.connect() as conn:
            conn.execute('INSERT INTO irc_history(channel,account,nick,event,body,created_at_utc) VALUES(?,?,?,?,?,?)', (channel, account, nick, event, body, utc_now()))

    def recent_irc(self, channel: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute('SELECT * FROM irc_history WHERE channel=? ORDER BY id DESC LIMIT ?', (channel, max(1, min(limit, 500)))).fetchall()
        return [dict(row) for row in reversed(rows)]

    def audit(self, actor: str | None, protocol: str, action: str, target: str | None, outcome: str, detail: dict[str, Any]) -> None:
        blocked = {'password', 'credential', 'body', 'content', 'secret', 'token'}
        safe = {key: value for key, value in detail.items() if key.lower() not in blocked}
        with self._lock, self.connect() as conn:
            conn.execute('INSERT INTO audit(created_at_utc,actor,protocol,action,target,outcome,detail_json) VALUES(?,?,?,?,?,?,?)', (utc_now(), actor, protocol, action, target, outcome, json.dumps(safe, sort_keys=True)))

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (max(1, min(limit, 1000)),)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item['detail'] = json.loads(item.pop('detail_json'))
            out.append(item)
        return out

    def prune_retention(self) -> dict[str, int]:
        removed = 0
        with self._lock, self.connect() as conn:
            for row in conn.execute('SELECT name,retention_days FROM newsgroups').fetchall():
                removed += conn.execute('DELETE FROM articles WHERE group_name=? AND created_at_utc<?', (row['name'], _cutoff(int(row['retention_days'])))).rowcount
            irc = conn.execute('DELETE FROM irc_history WHERE created_at_utc<?', (_cutoff(self.irc_history_days),)).rowcount
            audit = conn.execute('DELETE FROM audit WHERE created_at_utc<?', (_cutoff(self.audit_days),)).rowcount
        return {'articles': removed, 'irc_history': irc, 'audit': audit}

    def checkpoint(self) -> None:
        if str(self.path) == ':memory:':
            return
        with self.connect() as conn:
            conn.execute('PRAGMA wal_checkpoint(PASSIVE)')

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            return {
                'enabled_accounts': int(conn.execute('SELECT COUNT(*) FROM accounts WHERE enabled=1').fetchone()[0]),
                'newsgroups': int(conn.execute('SELECT COUNT(*) FROM newsgroups').fetchone()[0]),
                'articles': int(conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]),
                'irc_history_events': int(conn.execute('SELECT COUNT(*) FROM irc_history').fetchone()[0]),
                'ingested_items': int(conn.execute('SELECT COUNT(*) FROM ingest_items').fetchone()[0]),
                'ingestion_sources': int(conn.execute('SELECT COUNT(*) FROM ingest_state').fetchone()[0]),
            }
