"""Server-side, allowlisted HMAC client for the loopback Edge1 SNMP API."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import stat
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen

ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SAFE_POST_PATHS = frozenset({
    "/api/snmp/ai/query",
    "/api/snmp/ai/incidents",
})
MUTATING_POST_PATHS = frozenset({
    "/api/snmp/devices",
    "/api/snmp/discovery",
    "/api/snmp/mibs/import",
    "/api/snmp/alerts/evaluate",
    "/api/snmp/actions",
})
SIMPLE_GET_PATHS = frozenset({
    "/api/snmp/health",
    "/api/snmp/devices",
    "/api/snmp/topology",
    "/api/snmp/mibs",
    "/api/snmp/alerts",
    "/api/snmp/audit",
})
FORBIDDEN_KEY_MARKERS = (
    "password", "passphrase", "community", "secret", "credential_value",
    "private_key", "api_key", "relay_key", "relay_secret", "auth_key",
    "priv_key", "token_value", "hmac_key",
)
_SECRET_TEXT_RE = re.compile(
    r"(?i)\b(community|password|passphrase|authpass|privpass|secret|token|"
    r"api[_-]?key|relay[_-]?(?:key|secret)|hmac[_-]?key)\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_PRIVATE_PATH_RE = re.compile(
    r"/(?:etc/(?:edge1-snmp|edge1-operator|bigbird[^/\s]*|wwcx[^/\s]*)|"
    r"run/(?:credentials|edge1-snmp-ai-identity))(?:/[^\s'\";,]*)?"
)


class SnmpUiClientError(RuntimeError):
    pass


class SnmpUiClientTimeout(SnmpUiClientError):
    pass


def _bounded_int(text: str, minimum: int, maximum: int) -> int:
    try:
        value = int(text)
    except (TypeError, ValueError) as exc:
        raise SnmpUiClientError("invalid numeric query parameter") from exc
    if value < minimum or value > maximum:
        raise SnmpUiClientError("numeric query parameter outside allowed range")
    return value


def _validate_get_path(path: str) -> str:
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/api/snmp/"):
        raise SnmpUiClientError("SNMP API path is invalid")
    if parsed.path in SIMPLE_GET_PATHS:
        if parsed.query:
            raise SnmpUiClientError("query string is not allowed for this resource")
        return path
    if parsed.path in {"/api/snmp/events"}:
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"limit"} or any(len(v) != 1 for v in query.values()):
            raise SnmpUiClientError("event query is invalid")
        limit = _bounded_int(query.get("limit", ["100"])[0], 1, 500)
        return f"{parsed.path}?limit={limit}"
    if parsed.path in {"/api/snmp/oids", "/api/snmp/search"}:
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"q"} or any(len(v) != 1 for v in query.values()):
            raise SnmpUiClientError("search query is invalid")
        value = query.get("q", [""])[0][:200]
        return f"{parsed.path}?q={quote(value, safe='')}"
    parts = parsed.path.split("/")
    if len(parts) >= 5 and parts[:4] == ["", "api", "snmp", "devices"]:
        device_id = parts[4]
        if not DEVICE_ID_RE.fullmatch(device_id):
            raise SnmpUiClientError("device identifier is invalid")
        if len(parts) == 5 and not parsed.query:
            return parsed.path
        if len(parts) == 6 and parts[5] == "interfaces" and not parsed.query:
            return parsed.path
        if len(parts) == 6 and parts[5] == "metrics":
            query = parse_qs(parsed.query, keep_blank_values=True)
            if set(query) - {"limit"} or any(len(v) != 1 for v in query.values()):
                raise SnmpUiClientError("metrics query is invalid")
            limit = _bounded_int(query.get("limit", ["500"])[0], 1, 5000)
            return f"{parsed.path}?limit={limit}"
    raise SnmpUiClientError("SNMP API resource is not allowlisted")


def _validate_post_path(path: str) -> str:
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise SnmpUiClientError("SNMP API mutation path is invalid")
    if parsed.path not in SAFE_POST_PATHS | MUTATING_POST_PATHS:
        raise SnmpUiClientError("SNMP API operation is not allowlisted")
    return parsed.path


def _sanitize_text(value: str) -> str:
    text = _SECRET_TEXT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    text = _PRIVATE_PATH_RE.sub("[PRIVATE_PATH]", text)
    return text[:12000]


def sanitize_for_browser(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            text = str(key)
            lowered = text.lower()
            if any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS):
                continue
            result[text] = sanitize_for_browser(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_browser(item) for item in value[:5000]]
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(str(value)[:2000])


class Edge1SnmpUiClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8112",
        secret_path: Path = Path("/etc/edge1-snmp/api.secret"),
        timeout_seconds: int = 30,
        now: Any = time.time,
        opener: Any = urlopen,
    ):
        if base_url != "http://127.0.0.1:8112":
            raise ValueError("SNMP API origin must remain loopback and exact")
        if timeout_seconds < 1 or timeout_seconds > 90:
            raise ValueError("SNMP API timeout is outside the accepted range")
        self.base_url = base_url
        self.secret_path = secret_path
        self.timeout_seconds = timeout_seconds
        self.now = now
        self.opener = opener

    def _read_secret(self) -> bytes:
        try:
            info = self.secret_path.stat()
            if self.secret_path.is_symlink() or not stat.S_ISREG(info.st_mode):
                raise SnmpUiClientError("SNMP API secret path must be a regular file")
            if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise SnmpUiClientError("SNMP API secret permissions are too broad")
            secret = self.secret_path.read_bytes().strip()
        except OSError as exc:
            raise SnmpUiClientError("SNMP API secret is unavailable") from exc
        if len(secret) < 32:
            raise SnmpUiClientError("SNMP API secret is invalid")
        return secret

    def request(self, method: str, path: str, *, actor_subject: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        method = method.upper()
        if method == "GET":
            approved_path = _validate_get_path(path)
            body = b""
        elif method == "POST":
            approved_path = _validate_post_path(path)
            body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(body) > 65536:
                raise SnmpUiClientError("SNMP API request is too large")
        else:
            raise SnmpUiClientError("method is not allowlisted")
        actor = f"edge1-ops-snmp:{actor_subject}"
        if not ACTOR_RE.fullmatch(actor):
            raise SnmpUiClientError("actor identity is invalid")
        timestamp = str(int(self.now()))
        nonce = secrets.token_hex(24)
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join((method, approved_path, timestamp, nonce, actor, body_hash)).encode("utf-8")
        signature = hmac.new(self._read_secret(), canonical, hashlib.sha256).hexdigest()
        headers = {
            "Accept": "application/json",
            "X-WWCX-Actor": actor,
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Timestamp": timestamp,
            "X-WWCX-Signature": signature,
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
            request = Request(self.base_url + approved_path, data=body, method=method, headers=headers)
        else:
            request = Request(self.base_url + approved_path, method=method, headers=headers)
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read(2_000_001)
        except HTTPError as exc:
            status = int(exc.code)
            raw = exc.read(2_000_001)
        except TimeoutError as exc:
            raise SnmpUiClientTimeout("SNMP API request timed out") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SnmpUiClientTimeout("SNMP API request timed out") from exc
            raise SnmpUiClientError("SNMP API is unavailable") from exc
        if len(raw) > 2_000_000:
            raise SnmpUiClientError("SNMP API response is too large")
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnmpUiClientError("SNMP API response is unreadable") from exc
        return status, sanitize_for_browser(decoded)


__all__ = [
    "Edge1SnmpUiClient", "SnmpUiClientError", "SnmpUiClientTimeout",
    "SAFE_POST_PATHS", "MUTATING_POST_PATHS", "sanitize_for_browser",
]
