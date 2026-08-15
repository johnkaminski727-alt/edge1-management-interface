"""Bounded outbound-only NNTP reader for controlled relay ingestion."""

from __future__ import annotations

import json
import re
import socket
import ssl
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Callable

from .config import IngestSourceConfig

MESSAGE_ID_RE = re.compile(r'^<[^<>\s@]+@[^<>\s@]+>$')


class UpstreamNNTPError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpstreamArticle:
    article_number: int
    message_id: str
    subject: str
    author: str
    date: str
    references: str
    body: str
    content_type: str


@dataclass(frozen=True)
class PullResult:
    articles: tuple[UpstreamArticle, ...]
    cursor: str | None
    history_rewritten: bool
    scanned: int
    skipped: int


def _load_credentials(path_value: str | None) -> tuple[str, str] | None:
    if path_value is None:
        return None
    path = Path(path_value)
    if not path.is_file():
        raise UpstreamNNTPError('configured upstream credential file is unavailable')
    if path.stat().st_size > 16_384:
        raise UpstreamNNTPError('configured upstream credential file is unexpectedly large')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpstreamNNTPError('configured upstream credential file is invalid') from exc
    if not isinstance(payload, dict):
        raise UpstreamNNTPError('configured upstream credential file must contain a JSON object')
    username = payload.get('username')
    password = payload.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        raise UpstreamNNTPError('configured upstream credential file is missing username or password')
    if any(char in username for char in '\r\n') or any(char in password for char in '\r\n'):
        raise UpstreamNNTPError('configured upstream credential contains invalid line characters')
    if len(username.encode()) > 512 or len(password.encode()) > 4096:
        raise UpstreamNNTPError('configured upstream credential is too large')
    return username, password


class NNTPReader:
    def __init__(self, source: IngestSourceConfig, *, timeout: float = 10.0) -> None:
        if source.host is None or source.port is None or source.tls is not True:
            raise UpstreamNNTPError('upstream source is missing validated TLS connection settings')
        self.source = source
        self.timeout = timeout
        self.sock: socket.socket | ssl.SSLSocket | None = None
        self.reader = None
        self.writer = None

    def __enter__(self) -> 'NNTPReader':
        raw = socket.create_connection((self.source.host, self.source.port), timeout=self.timeout)
        raw.settimeout(self.timeout)
        context = ssl.create_default_context()
        try:
            wrapped = context.wrap_socket(raw, server_hostname=self.source.host)
        except Exception:
            raw.close()
            raise
        self.sock = wrapped
        self.reader = wrapped.makefile('rb')
        self.writer = wrapped.makefile('wb')
        code, _ = self._read_status()
        if code not in {200, 201}:
            self.close()
            raise UpstreamNNTPError(f'upstream greeting rejected with status {code}')
        credentials = _load_credentials(self.source.credential_file)
        if credentials is not None:
            username, password = credentials
            code, _ = self.command(f'AUTHINFO USER {username}')
            if code == 381:
                code, _ = self.command(f'AUTHINFO PASS {password}')
            if code != 281:
                self.close()
                raise UpstreamNNTPError(f'upstream authentication rejected with status {code}')
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.writer is not None:
                try:
                    self.command('QUIT')
                except Exception:
                    pass
        finally:
            self.close()

    def close(self) -> None:
        for handle_name in ('reader', 'writer'):
            handle = getattr(self, handle_name)
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
                setattr(self, handle_name, None)
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _readline(self) -> bytes:
        if self.reader is None:
            raise UpstreamNNTPError('upstream connection is not open')
        line = self.reader.readline(65_537)
        if not line:
            raise UpstreamNNTPError('upstream connection closed unexpectedly')
        if len(line) > 65_536:
            raise UpstreamNNTPError('upstream response line exceeds limit')
        return line.rstrip(b'\r\n')

    def _read_status(self) -> tuple[int, str]:
        line = self._readline()
        text = line.decode('utf-8', errors='replace')
        if len(text) < 3 or not text[:3].isdigit():
            raise UpstreamNNTPError('upstream returned malformed status line')
        return int(text[:3]), text[4:] if len(text) > 4 else ''

    def command(self, command: str) -> tuple[int, str]:
        if self.writer is None:
            raise UpstreamNNTPError('upstream connection is not open')
        if '\r' in command or '\n' in command or len(command.encode()) > 8192:
            raise UpstreamNNTPError('unsafe upstream command')
        self.writer.write(command.encode('utf-8') + b'\r\n')
        self.writer.flush()
        return self._read_status()

    def group(self, name: str) -> tuple[int, int, int]:
        code, text = self.command(f'GROUP {name}')
        if code != 211:
            raise UpstreamNNTPError(f'upstream group selection rejected with status {code}')
        parts = text.split()
        if len(parts) < 4:
            raise UpstreamNNTPError('upstream GROUP response is malformed')
        try:
            count = int(parts[0])
            low = int(parts[1])
            high = int(parts[2])
        except ValueError as exc:
            raise UpstreamNNTPError('upstream GROUP response contains invalid article numbers') from exc
        if min(count, low, high) < 0:
            raise UpstreamNNTPError('upstream GROUP response contains negative values')
        return count, low, high

    def article(self, article_number: int, *, max_article_bytes: int) -> UpstreamArticle | None:
        code, _ = self.command(f'ARTICLE {article_number}')
        if code in {423, 430}:
            return None
        if code != 220:
            raise UpstreamNNTPError(f'upstream ARTICLE rejected with status {code}')
        wire_limit = max_article_bytes + 65_536
        total = 0
        lines: list[bytes] = []
        while True:
            line = self._readline()
            if line == b'.':
                break
            if line.startswith(b'..'):
                line = line[1:]
            total += len(line) + 2
            if total > wire_limit:
                while line != b'.':
                    line = self._readline()
                return None
            lines.append(line)
        raw = b'\r\n'.join(lines) + b'\r\n'
        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception:
            return None
        if message.is_multipart():
            return None
        content_type = message.get_content_type().lower()
        if not content_type.startswith('text/'):
            return None
        payload = message.get_payload(decode=True)
        if payload is None:
            raw_payload = message.get_payload()
            payload = str(raw_payload).encode('utf-8', errors='replace')
        if len(payload) > max_article_bytes:
            return None
        charset = message.get_content_charset() or 'utf-8'
        try:
            body = payload.decode(charset, errors='replace')
        except LookupError:
            body = payload.decode('utf-8', errors='replace')
        message_id = str(message.get('Message-ID') or '').strip()
        if not MESSAGE_ID_RE.fullmatch(message_id):
            return None
        subject = str(message.get('Subject') or '(no subject)').strip()
        author = str(message.get('From') or 'Unknown upstream author').strip()
        date = str(message.get('Date') or '').strip()
        references = str(message.get('References') or '').strip()
        if not subject or '\r' in subject or '\n' in subject:
            return None
        if not author or '\r' in author or '\n' in author:
            return None
        return UpstreamArticle(
            article_number=article_number,
            message_id=message_id,
            subject=subject[:998],
            author=author[:998],
            date=date[:998],
            references=references[:4096],
            body=body,
            content_type=content_type,
        )


def pull_articles(
    source: IngestSourceConfig,
    cursor: str | None,
    *,
    limit: int,
    seen: Callable[[str], bool],
) -> PullResult:
    if source.upstream_group is None or source.max_article_bytes is None:
        raise UpstreamNNTPError('upstream source is missing validated group or article limits')
    if limit <= 0:
        return PullResult((), cursor, False, 0, 0)
    prior: int | None = None
    if cursor:
        try:
            prior = int(cursor)
        except ValueError:
            prior = None
    articles: list[UpstreamArticle] = []
    scanned = 0
    skipped = 0
    history_rewritten = False
    with NNTPReader(source) as client:
        _, low, high = client.group(source.upstream_group)
        if high == 0:
            return PullResult((), '0', False, 0, 0)
        if prior is None:
            start = max(low, high - source.initial_items + 1)
        elif prior > high:
            history_rewritten = True
            start = max(low, high - source.initial_items + 1)
        else:
            start = max(low, prior + 1)
        if start > high:
            return PullResult((), str(high), history_rewritten, 0, 0)
        end = min(high, start + source.scan_limit - 1)
        last_scanned = start - 1
        for number in range(start, end + 1):
            last_scanned = number
            scanned += 1
            article = client.article(number, max_article_bytes=source.max_article_bytes)
            if article is None:
                skipped += 1
                continue
            if seen(article.message_id):
                skipped += 1
                continue
            articles.append(article)
            if len(articles) >= limit:
                break
    return PullResult(tuple(articles), str(last_scanned), history_rewritten, scanned, skipped)
