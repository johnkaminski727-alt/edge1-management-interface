#!/usr/bin/env python3
"""Business159 Claude connector gateway.

Publishes the bounded business159-live-shell MCP server to claude.ai custom
connectors over Streamable HTTP, behind a single-operator OAuth 2.1
authorization server whose sign-in step is an authenticator-app (TOTP) code.

Boundaries enforced here, independent of the client:

* Each MCP session gets its own stdio child running the bounded
  business159-live-shell wrapper. The Edge1 Agent Shell (root, 127.0.0.1:8114)
  is never contacted.
* Only allow-listed tools are listed or callable. business159_deploy is forced
  to dry-run. The child environment pins every Business159 mutation gate to 0.
* /mcp and /token only accept Anthropic's published outbound range (also
  enforced by the nginx site). The browser-facing /authorize page is open but
  requires a fresh TOTP code, with replay protection and a failure lockout.
* Secrets are read from root-owned files; only SHA-256 digests of the client
  secret and of issued tokens are stored.

Standard library only. Listens on loopback; nginx terminates TLS.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import ipaddress
import json
import os
import secrets
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROTOCOL_VERSIONS = ('2025-06-18', '2025-03-26', '2024-11-05')

# Stage 1: read-only tools plus deploy dry-run. Mail mutations, staged
# filesystem writes and raw shell are intentionally absent.
STAGE1_TOOLS = frozenset({
    'business159.identity',
    'business159.health',
    'business159.snapshot',
    'business159.inventory',
    'business159.resources',
    'business159.php_status',
    'business159.web_status',
    'business159.domain_state',
    'business159.tls_status',
    'business159.cron_state',
    'business159.git_state',
    'business159.mail_state',
    'business159.mail_domain_list',
    'business159.mailbox_list',
    'business159.forwarder_list',
    'business159.deployment_status',
    'business159.edge1_bridge_status',
    'business159.config_digest',
    'business159.logs_summary',
    'business159_connection_test',
    'business159_inspect',
    'business159_deploy',
    'business159_fs_status',
    'business159_fs_diff',
})
DRY_RUN_ONLY_TOOLS = frozenset({'business159_deploy'})
NEVER_TOOLS = frozenset({'business159_exec'})

CHILD_POLICY_ENV = {
    'BUSINESS159_ALLOW_DEPLOY': '0',
    'BUSINESS159_ALLOW_FILESYSTEM': '0',
    'BUSINESS159_ENABLE_RAW_SHELL': '0',
}

DEFAULT_REDIRECT_URIS = (
    'https://claude.ai/api/mcp/auth_callback',
    'https://claude.com/api/mcp/auth_callback',
)
ANTHROPIC_OUTBOUND = ('160.79.104.0/21',)


@dataclass
class Config:
    issuer: str = 'https://mcp-b159.ww.cx'
    host: str = '127.0.0.1'
    port: int = 8150
    etc_dir: Path = Path('/etc/business159-claude-gateway')
    state_dir: Path = Path('/var/lib/business159-claude-gateway')
    audit_log: Path = Path('/var/log/business159-claude-gateway/audit.jsonl')
    child_command: tuple[str, ...] = ('/usr/local/libexec/business159-tunnel/business159-live-shell.sh',)
    allowed_cidrs: tuple[str, ...] = ANTHROPIC_OUTBOUND
    redirect_uris: tuple[str, ...] = DEFAULT_REDIRECT_URIS
    tools: frozenset[str] = STAGE1_TOOLS
    access_ttl: int = 3600
    refresh_ttl: int = 30 * 86400
    code_ttl: int = 120
    pending_ttl: int = 600
    max_sessions: int = 4
    session_idle: int = 900
    call_timeout: float = 180.0
    max_body: int = 1 << 20
    totp_lockout_failures: int = 5
    totp_lockout_seconds: int = 900

    @property
    def resource(self) -> str:
        return self.issuer + '/mcp'

    @classmethod
    def from_env(cls) -> 'Config':
        env = os.environ
        cfg = cls()
        cfg.issuer = env.get('B159_GATEWAY_ISSUER', cfg.issuer).rstrip('/')
        cfg.host = env.get('B159_GATEWAY_HOST', cfg.host)
        cfg.port = int(env.get('B159_GATEWAY_PORT', cfg.port))
        cfg.etc_dir = Path(env.get('B159_GATEWAY_ETC', cfg.etc_dir))
        cfg.state_dir = Path(env.get('B159_GATEWAY_STATE', cfg.state_dir))
        cfg.audit_log = Path(env.get('B159_GATEWAY_AUDIT_LOG', cfg.audit_log))
        if env.get('B159_GATEWAY_CHILD'):
            cfg.child_command = tuple(json.loads(env['B159_GATEWAY_CHILD']))
        if env.get('B159_GATEWAY_ALLOWED_CIDRS') is not None:
            cfg.allowed_cidrs = tuple(c for c in env['B159_GATEWAY_ALLOWED_CIDRS'].split(',') if c.strip())
        return cfg


def _now() -> int:
    return int(time.time())


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_secret(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip()


# ---------------------------------------------------------------- TOTP ------

def totp_code(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32.upper() + '=' * (-len(secret_b32) % 8))
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


class TotpGuard:
    """Verifies codes with a +/-1 step window, refuses reuse and locks out."""

    def __init__(self, cfg: Config, secret_b32: str, store: 'StateStore'):
        self.cfg = cfg
        self.secret = secret_b32
        self.store = store
        self.lock = threading.Lock()

    def locked_until(self) -> int:
        return int(self.store.data.get('totp_locked_until', 0))

    def verify(self, code: str, now: float | None = None) -> tuple[bool, str]:
        now = time.time() if now is None else now
        code = ''.join(ch for ch in code if ch.isdigit())
        with self.lock:
            if self.locked_until() > now:
                return False, 'locked'
            if len(code) != 6:
                return self._fail(now)
            current = int(now // 30)
            last = int(self.store.data.get('totp_last_counter', -1))
            for counter in (current - 1, current, current + 1):
                if counter <= last:
                    continue
                if hmac.compare_digest(totp_code(self.secret, counter), code):
                    self.store.update(totp_last_counter=counter, totp_failures=0)
                    return True, 'ok'
            return self._fail(now)

    def _fail(self, now: float) -> tuple[bool, str]:
        failures = int(self.store.data.get('totp_failures', 0)) + 1
        if failures >= self.cfg.totp_lockout_failures:
            self.store.update(totp_failures=0, totp_locked_until=int(now) + self.cfg.totp_lockout_seconds)
            return False, 'locked'
        self.store.update(totp_failures=failures)
        return False, 'invalid'


# --------------------------------------------------------------- State ------

class StateStore:
    """Small JSON file holding token digests and TOTP replay/lockout state."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {'access': {}, 'refresh': {}}
        if path.exists():
            loaded = json.loads(path.read_text(encoding='utf-8'))
            self.data.update(loaded)

    def update(self, **values: Any) -> None:
        with self.lock:
            self.data.update(values)
            self._flush()

    def mutate(self, fn) -> Any:
        with self.lock:
            result = fn(self.data)
            self._flush()
            return result

    def _flush(self) -> None:
        now = _now()
        for kind in ('access', 'refresh'):
            self.data[kind] = {k: v for k, v in self.data.get(kind, {}).items() if v.get('exp', 0) > now}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(self.data, handle, separators=(',', ':'))
        os.replace(tmp, self.path)


# ---------------------------------------------------------------- Audit -----

class Audit:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def write(self, event: str, **fields: Any) -> None:
        record = {'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'event': event, **fields}
        line = json.dumps(record, separators=(',', ':'), default=str)
        with self.lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open('a', encoding='utf-8') as handle:
                    handle.write(line + '\n')
            except OSError:
                print(line, file=sys.stderr, flush=True)


# ------------------------------------------------------------ MCP child -----

class ChildSession:
    """One stdio business159-live-shell process bound to one MCP session."""

    def __init__(self, cfg: Config, session_id: str):
        self.id = session_id
        self.cfg = cfg
        env = {k: v for k, v in os.environ.items() if not k.startswith('B159_GATEWAY_')}
        env.update(CHILD_POLICY_ENV)
        self.proc = subprocess.Popen(
            list(cfg.child_command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, bufsize=0,
        )
        self.write_lock = threading.Lock()
        self.cond = threading.Condition()
        self.responses: dict[str, dict] = {}
        self.last_used = time.monotonic()
        self.closed = False
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if isinstance(message, dict) and 'id' in message and 'method' not in message:
                with self.cond:
                    self.responses[json.dumps(message['id'])] = message
                    self.cond.notify_all()
        with self.cond:
            self.closed = True
            self.cond.notify_all()

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for raw in self.proc.stderr:
            line = raw.decode('utf-8', 'replace').rstrip()[:500]
            if line:
                print(f'[session {self.id[:8]}] {line}', file=sys.stderr, flush=True)

    def send(self, message: dict) -> None:
        assert self.proc.stdin is not None
        data = (json.dumps(message, separators=(',', ':')) + '\n').encode('utf-8')
        with self.write_lock:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        self.last_used = time.monotonic()

    def request(self, message: dict, timeout: float) -> dict:
        key = json.dumps(message['id'])
        self.send(message)
        deadline = time.monotonic() + timeout
        with self.cond:
            while key not in self.responses:
                remaining = deadline - time.monotonic()
                if self.closed or remaining <= 0:
                    raise TimeoutError('business159-live-shell did not answer')
                self.cond.wait(remaining)
            self.last_used = time.monotonic()
            return self.responses.pop(key)

    def close(self) -> None:
        self.closed = True
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                if pipe:
                    pipe.close()
            except OSError:
                pass


class SessionPool:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.sessions: dict[str, ChildSession] = {}

    def create(self) -> ChildSession:
        self.reap()
        with self.lock:
            if len(self.sessions) >= self.cfg.max_sessions:
                oldest = min(self.sessions.values(), key=lambda s: s.last_used)
                self.sessions.pop(oldest.id).close()
            session = ChildSession(self.cfg, secrets.token_urlsafe(24))
            self.sessions[session.id] = session
            return session

    def get(self, session_id: str) -> ChildSession | None:
        with self.lock:
            session = self.sessions.get(session_id)
        if session and session.proc.poll() is not None:
            self.drop(session_id)
            return None
        return session

    def drop(self, session_id: str) -> None:
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session:
            session.close()

    def reap(self) -> None:
        cutoff = time.monotonic() - self.cfg.session_idle
        with self.lock:
            stale = [sid for sid, s in self.sessions.items() if s.last_used < cutoff or s.proc.poll() is not None]
        for sid in stale:
            self.drop(sid)

    def close_all(self) -> None:
        for sid in list(self.sessions):
            self.drop(sid)


# ------------------------------------------------------------- Policy -------

def tool_policy(cfg: Config, params: dict) -> str | None:
    """Return a refusal reason, or None when the call may proceed."""
    name = params.get('name')
    if not isinstance(name, str) or name in NEVER_TOOLS or name not in cfg.tools:
        return f'Tool {name!r} is not enabled on the Claude connector (stage 1: read-only and deploy dry-run).'
    if name in DRY_RUN_ONLY_TOOLS:
        arguments = params.get('arguments') or {}
        if not isinstance(arguments, dict) or arguments.get('dryRun', True) is not True:
            return 'business159_deploy is limited to dryRun=true on the Claude connector.'
    return None


def filter_tools_list(cfg: Config, response: dict) -> dict:
    result = response.get('result')
    if isinstance(result, dict) and isinstance(result.get('tools'), list):
        result['tools'] = [t for t in result['tools'] if isinstance(t, dict) and t.get('name') in cfg.tools and t.get('name') not in NEVER_TOOLS]
    return response


# ------------------------------------------------------------ Gateway -------

class Gateway:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client_id = read_secret(cfg.etc_dir / 'client-id')
        self.client_secret_sha256 = read_secret(cfg.etc_dir / 'client-secret.sha256')
        self.store = StateStore(cfg.state_dir / 'state.json')
        self.totp = TotpGuard(cfg, read_secret(cfg.etc_dir / 'totp-secret'), self.store)
        self.audit = Audit(cfg.audit_log)
        self.pool = SessionPool(cfg)
        self.networks = [ipaddress.ip_network(c.strip()) for c in cfg.allowed_cidrs]
        self.pending: dict[str, dict] = {}
        self.codes: dict[str, dict] = {}
        self.lock = threading.Lock()

    @property
    def disabled(self) -> bool:
        return (self.cfg.etc_dir / 'disabled').exists()

    def ip_allowed(self, ip: str) -> bool:
        if not self.networks:
            return True
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self.networks)

    # -- OAuth metadata --
    def protected_resource_metadata(self) -> dict:
        return {
            'resource': self.cfg.resource,
            'authorization_servers': [self.cfg.issuer],
            'bearer_methods_supported': ['header'],
            'resource_name': 'Business159 bounded operator (WW.CX)',
        }

    def authorization_server_metadata(self) -> dict:
        iss = self.cfg.issuer
        return {
            'issuer': iss,
            'authorization_endpoint': iss + '/authorize',
            'token_endpoint': iss + '/token',
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['client_secret_post', 'client_secret_basic'],
            'scopes_supported': ['business159'],
        }

    # -- authorize --
    def start_authorization(self, query: dict[str, str]) -> tuple[str | None, str]:
        """Validate an /authorize request. Returns (pending_id, error)."""
        if query.get('response_type') != 'code':
            return None, 'unsupported response_type'
        if query.get('client_id') != self.client_id:
            return None, 'unknown client_id'
        if query.get('redirect_uri') not in self.cfg.redirect_uris:
            return None, 'redirect_uri is not registered'
        if query.get('code_challenge_method') != 'S256' or len(query.get('code_challenge', '')) < 43:
            return None, 'PKCE S256 code_challenge is required'
        resource = query.get('resource')
        if resource and resource.rstrip('/') != self.cfg.resource:
            return None, 'resource does not match this server'
        pending_id = secrets.token_urlsafe(24)
        with self.lock:
            self._expire()
            self.pending[pending_id] = {**query, 'exp': _now() + self.cfg.pending_ttl}
        return pending_id, ''

    def complete_authorization(self, pending_id: str, code: str, ip: str) -> tuple[str | None, str]:
        with self.lock:
            self._expire()
            pending = self.pending.get(pending_id)
        if not pending:
            return None, 'This sign-in request expired. Start again from Claude.'
        ok, reason = self.totp.verify(code)
        if not ok:
            self.audit.write('authorize_failed', ip=ip, reason=reason)
            if reason == 'locked':
                return None, 'Too many incorrect codes. Sign-in is locked for 15 minutes.'
            return None, 'That code was not accepted. Wait for a fresh code and try again.'
        with self.lock:
            self.pending.pop(pending_id, None)
            auth_code = secrets.token_urlsafe(32)
            self.codes[auth_code] = {
                'client_id': pending['client_id'],
                'redirect_uri': pending['redirect_uri'],
                'code_challenge': pending['code_challenge'],
                'exp': _now() + self.cfg.code_ttl,
            }
        self.audit.write('authorize_ok', ip=ip)
        params = {'code': auth_code}
        if pending.get('state'):
            params['state'] = pending['state']
        return pending['redirect_uri'] + '?' + urllib.parse.urlencode(params), ''

    def _expire(self) -> None:
        now = _now()
        self.pending = {k: v for k, v in self.pending.items() if v['exp'] > now}
        self.codes = {k: v for k, v in self.codes.items() if v['exp'] > now}

    # -- token --
    def client_authenticated(self, client_id: str | None, client_secret: str | None) -> bool:
        if client_id != self.client_id or not client_secret:
            return False
        return hmac.compare_digest(sha256_hex(client_secret), self.client_secret_sha256)

    def issue_tokens(self) -> dict:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        now = _now()

        def add(data: dict) -> None:
            data.setdefault('access', {})[sha256_hex(access)] = {'exp': now + self.cfg.access_ttl}
            data.setdefault('refresh', {})[sha256_hex(refresh)] = {'exp': now + self.cfg.refresh_ttl}

        self.store.mutate(add)
        return {
            'access_token': access, 'token_type': 'Bearer', 'expires_in': self.cfg.access_ttl,
            'refresh_token': refresh, 'scope': 'business159',
        }

    def exchange(self, form: dict[str, str]) -> tuple[int, dict]:
        grant = form.get('grant_type')
        if grant == 'authorization_code':
            with self.lock:
                self._expire()
                entry = self.codes.pop(form.get('code', ''), None)
            if not entry or entry['redirect_uri'] != form.get('redirect_uri') or entry['client_id'] != form.get('client_id'):
                return 400, {'error': 'invalid_grant'}
            verifier = form.get('code_verifier', '')
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            if not verifier or not hmac.compare_digest(challenge, entry['code_challenge']):
                return 400, {'error': 'invalid_grant', 'error_description': 'PKCE verification failed'}
            return 200, self.issue_tokens()
        if grant == 'refresh_token':
            digest = sha256_hex(form.get('refresh_token', ''))
            found = self.store.mutate(lambda d: d.setdefault('refresh', {}).pop(digest, None))
            if not found or found.get('exp', 0) <= _now():
                return 400, {'error': 'invalid_grant'}
            return 200, self.issue_tokens()
        return 400, {'error': 'unsupported_grant_type'}

    def bearer_valid(self, token: str) -> bool:
        entry = self.store.data.get('access', {}).get(sha256_hex(token))
        return bool(entry and entry.get('exp', 0) > _now())

    def revoke_all(self) -> None:
        self.store.update(access={}, refresh={})

    # -- MCP --
    def handle_mcp_message(self, message: dict, session: ChildSession, ip: str) -> dict | None:
        method = message.get('method')
        if 'id' not in message:
            session.send(message)
            return None
        if method == 'tools/call':
            params = message.get('params') or {}
            refusal = tool_policy(self.cfg, params)
            name = params.get('name')
            arg_keys = sorted((params.get('arguments') or {}).keys()) if isinstance(params.get('arguments'), dict) else []
            if refusal:
                self.audit.write('tool_blocked', ip=ip, session=session.id[:8], tool=name, args=arg_keys)
                return {'jsonrpc': '2.0', 'id': message['id'], 'result': {'content': [{'type': 'text', 'text': refusal}], 'isError': True}}
            started = time.monotonic()
            response = session.request(message, self.cfg.call_timeout)
            result = response.get('result') or {}
            self.audit.write('tool_call', ip=ip, session=session.id[:8], tool=name, args=arg_keys,
                             ms=int((time.monotonic() - started) * 1000), is_error=bool(result.get('isError') or response.get('error')))
            return response
        response = session.request(message, self.cfg.call_timeout)
        if method == 'tools/list':
            response = filter_tools_list(self.cfg, response)
        return response


# ------------------------------------------------------------- HTTP ---------

AUTHORIZE_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Business159 connector sign-in</title>
<style>body{{font:16px system-ui,sans-serif;max-width:26rem;margin:3rem auto;padding:0 1rem;color:#1b1b1b}}
input{{font:inherit;font-size:1.6rem;letter-spacing:.3em;width:100%;padding:.4rem;box-sizing:border-box}}
button{{font:inherit;margin-top:1rem;padding:.6rem 1.2rem;background:#01453a;color:#fff;border:0;border-radius:6px}}
.err{{color:#a40000}} small{{color:#555}}</style></head><body>
<h1>Business159 connector</h1>
<p>Claude is asking to use the <strong>Business159 bounded operator</strong> (read-only tools and deploy dry-run).</p>
{error}
<form method="post" action="/authorize">
<input type="hidden" name="pending" value="{pending}">
<label for="code">Authenticator code</label>
<input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]{{6,7}}" required autofocus>
<button type="submit">Allow</button>
</form>
<p><small>Close this page to deny. Codes come from your authenticator (e.g. Yubico Authenticator).</small></p>
</body></html>"""

SECURITY_HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
}


def make_handler(gw: Gateway):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'business159-claude-gateway'
        sys_version = ''

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f'{self.client_ip()} {fmt % args}', file=sys.stderr, flush=True)

        def client_ip(self) -> str:
            forwarded = self.headers.get('X-Forwarded-For', '')
            if forwarded:
                return forwarded.split(',')[-1].strip()
            return self.client_address[0]

        # -- responses --
        def send(self, status: int, body: bytes = b'', content_type: str = 'application/json',
                 headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            for key, value in {**SECURITY_HEADERS, **(headers or {})}.items():
                self.send_header(key, value)
            if body or status not in (202, 204):
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def send_json(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
            self.send(status, json.dumps(payload).encode(), headers=headers)

        def unauthorized(self) -> None:
            meta = gw.cfg.issuer + '/.well-known/oauth-protected-resource'
            self.send_json(401, {'error': 'invalid_token'},
                           headers={'WWW-Authenticate': f'Bearer resource_metadata="{meta}"'})

        def read_body(self) -> bytes | None:
            length = int(self.headers.get('Content-Length') or 0)
            if length > gw.cfg.max_body:
                self.send_json(413, {'error': 'request too large'})
                return None
            return self.rfile.read(length) if length else b''

        def path_only(self) -> str:
            return urllib.parse.urlsplit(self.path).path

        # -- routing --
        def do_GET(self) -> None:
            path = self.path_only()
            if path in ('/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'):
                return self.send_json(200, gw.protected_resource_metadata())
            if path == '/.well-known/oauth-authorization-server':
                return self.send_json(200, gw.authorization_server_metadata())
            if path == '/healthz':
                return self.send_json(200, {'ok': True, 'enabled': not gw.disabled, 'sessions': len(gw.pool.sessions)})
            if gw.disabled:
                return self.send_json(503, {'error': 'connector disabled'})
            if path == '/authorize':
                query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
                pending, error = gw.start_authorization(query)
                if not pending:
                    gw.audit.write('authorize_rejected', ip=self.client_ip(), reason=error)
                    return self.send(400, html.escape(error).encode(), 'text/plain; charset=utf-8')
                return self.authorize_page(pending)
            if path == '/mcp':
                if not self.mcp_guard():
                    return
                return self.send(405, b'', headers={'Allow': 'POST, DELETE'})
            self.send_json(404, {'error': 'not found'})

        def authorize_page(self, pending: str, error: str = '') -> None:
            error_html = f'<p class="err">{html.escape(error)}</p>' if error else ''
            body = AUTHORIZE_PAGE.format(pending=html.escape(pending), error=error_html).encode()
            self.send(200, body, 'text/html; charset=utf-8', headers={
                'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https://claude.ai https://claude.com; frame-ancestors 'none'",
                'X-Frame-Options': 'DENY',
            })

        def do_POST(self) -> None:
            path = self.path_only()
            if gw.disabled:
                return self.send_json(503, {'error': 'connector disabled'})
            if path == '/authorize':
                body = self.read_body()
                if body is None:
                    return
                form = dict(urllib.parse.parse_qsl(body.decode('utf-8', 'replace')))
                target, error = gw.complete_authorization(form.get('pending', ''), form.get('code', ''), self.client_ip())
                if target:
                    return self.send(302, b'', headers={'Location': target})
                if 'expired' in error:
                    return self.send(400, error.encode(), 'text/plain; charset=utf-8')
                return self.authorize_page(form.get('pending', ''), error)
            if path == '/token':
                return self.token()
            if path == '/mcp':
                return self.mcp_post()
            self.send_json(404, {'error': 'not found'})

        def do_DELETE(self) -> None:
            if self.path_only() != '/mcp' or gw.disabled:
                return self.send_json(404, {'error': 'not found'})
            if not self.mcp_guard():
                return
            sid = self.headers.get('Mcp-Session-Id', '')
            gw.pool.drop(sid)
            self.send(204)

        def token(self) -> None:
            ip = self.client_ip()
            if not gw.ip_allowed(ip):
                gw.audit.write('token_ip_denied', ip=ip)
                return self.send_json(403, {'error': 'forbidden'})
            body = self.read_body()
            if body is None:
                return
            form = dict(urllib.parse.parse_qsl(body.decode('utf-8', 'replace')))
            client_id, client_secret = form.get('client_id'), form.get('client_secret')
            auth = self.headers.get('Authorization', '')
            if auth.startswith('Basic '):
                try:
                    decoded = base64.b64decode(auth[6:]).decode()
                    client_id, client_secret = (urllib.parse.unquote(p) for p in decoded.split(':', 1))
                except Exception:
                    client_id = client_secret = None
            if not gw.client_authenticated(client_id, client_secret):
                gw.audit.write('token_client_denied', ip=ip)
                return self.send_json(401, {'error': 'invalid_client'})
            form['client_id'] = client_id or ''
            status, payload = gw.exchange(form)
            gw.audit.write('token_' + ('issued' if status == 200 else 'rejected'), ip=ip, grant=form.get('grant_type'))
            self.send_json(status, payload)

        def mcp_guard(self) -> bool:
            ip = self.client_ip()
            if not gw.ip_allowed(ip):
                gw.audit.write('mcp_ip_denied', ip=ip)
                self.send_json(403, {'error': 'forbidden'})
                return False
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer ') or not gw.bearer_valid(auth[7:].strip()):
                self.unauthorized()
                return False
            return True

        def mcp_post(self) -> None:
            if not self.mcp_guard():
                return
            body = self.read_body()
            if body is None:
                return
            try:
                message = json.loads(body)
            except ValueError:
                return self.send_json(400, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
            if not isinstance(message, dict):
                return self.send_json(400, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Batches are not supported'}})
            ip = self.client_ip()
            sid = self.headers.get('Mcp-Session-Id', '')
            headers: dict[str, str] = {}
            if message.get('method') == 'initialize':
                session = gw.pool.create()
                headers['Mcp-Session-Id'] = session.id
                gw.audit.write('session_start', ip=ip, session=session.id[:8])
            else:
                session = gw.pool.get(sid) if sid else None
                if not session:
                    return self.send_json(404, {'jsonrpc': '2.0', 'id': message.get('id'), 'error': {'code': -32001, 'message': 'Session not found'}})
            try:
                response = gw.handle_mcp_message(message, session, ip)
            except TimeoutError:
                gw.pool.drop(session.id)
                return self.send_json(504, {'jsonrpc': '2.0', 'id': message.get('id'), 'error': {'code': -32603, 'message': 'Business159 operator timed out'}})
            if response is None:
                return self.send(202, headers=headers)
            self.send_json(200, response, headers=headers)

    return Handler


def main() -> int:
    cfg = Config.from_env()
    gateway = Gateway(cfg)
    server = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(gateway))
    server.daemon_threads = True

    def reaper() -> None:
        while True:
            time.sleep(60)
            gateway.pool.reap()

    threading.Thread(target=reaper, daemon=True).start()
    print(f'business159-claude-gateway listening on {cfg.host}:{cfg.port} for {cfg.issuer}', file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        gateway.pool.close_all()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
