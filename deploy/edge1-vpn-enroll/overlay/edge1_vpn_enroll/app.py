from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import threading
import time
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from .config import load_config
from .core import create_invite, enroll_device, escape, get_invite_by_token, invite_is_redeemable, list_owned_devices, list_rows, rename_owned_device, revoke_device, revoke_invite, revoke_owned_device, svg_data_uri


_INTERNAL_NONCES: dict[str, int] = {}
_INTERNAL_NONCE_LOCK = threading.Lock()
_INTERNAL_SECRET_FILE = "/etc/edge1-operations-api.secret"

def verify_internal_signature(headers, method: str, path: str, body: bytes) -> str | None:
    actor = headers.get("X-WWCX-Actor", "")
    timestamp = headers.get("X-WWCX-Timestamp", "")
    nonce = headers.get("X-WWCX-Nonce", "")
    signature = headers.get("X-WWCX-Signature", "")
    if not actor.startswith("edge1-vpn-account:wwcx-user-") or not timestamp.isdigit() or len(nonce) < 24:
        return None
    now = int(time.time())
    when = int(timestamp)
    if abs(now - when) > 120:
        return None
    try:
        secret = Path(_INTERNAL_SECRET_FILE).read_bytes().strip()
    except OSError:
        return None
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method.upper(), path, timestamp, nonce, actor, body_hash)).encode("utf-8")
    expected = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    with _INTERNAL_NONCE_LOCK:
        stale = [key for key, expiry in _INTERNAL_NONCES.items() if expiry < now]
        for key in stale:
            _INTERNAL_NONCES.pop(key, None)
        if nonce in _INTERNAL_NONCES:
            return None
        _INTERNAL_NONCES[nonce] = now + 180
    return actor.removeprefix("edge1-vpn-account:")


def page(title: str, body: str, path: str = "") -> bytes:
    admin = path.startswith("/admin")
    safe_title = escape(title)
    if admin:
        active = "dashboard"
        if path.startswith("/admin/invites"):
            active = "invites"
        elif path.startswith("/admin/devices"):
            active = "devices"
        shell_title = {
            "VPN Admin": "VPN & Devices",
            "VPN Invites": "VPN Invites",
            "VPN Devices": "VPN Devices",
        }.get(title, title)
        dashboard_class = "is-active" if active == "dashboard" else ""
        invites_class = "is-active" if active == "invites" else ""
        devices_class = "is-active" if active == "devices" else ""
        layout = f"""
<div class="admin-app" data-admin-app>
  <button class="admin-mobile-menu" type="button" aria-label="Open navigation" aria-controls="admin-sidebar" aria-expanded="false" data-admin-menu-toggle>☰</button>
  <aside class="admin-sidebar" id="admin-sidebar" data-admin-sidebar>
    <a class="admin-brand" href="https://ww.cx/admin/" aria-label="WW.CX Admin home">
      <img class="admin-brand-art" src="https://ww.cx/assets/icons/ciww-badge.svg" alt="Christmas Island Worldwide" referrerpolicy="no-referrer">
      <span class="admin-brand-copy"><span class="admin-brand-mark">WW.CX</span><span class="admin-brand-sub">Admin</span></span>
    </a>
    <nav class="admin-side-nav" aria-label="WW.CX Admin">
      <details class="admin-nav-group">
        <summary><span>Store</span></summary>
        <div class="admin-nav-items"><a href="https://ww.cx/admin/">Dashboard</a><a href="https://ww.cx/admin/?page=orders">Orders</a><a href="https://ww.cx/admin/?page=catalog">Catalog</a></div>
      </details>
      <details class="admin-nav-group">
        <summary><span>Operations</span></summary>
        <div class="admin-nav-items"><a href="https://ww.cx/admin/?page=carriers">Carriers</a><a href="https://ww.cx/admin/?page=carrier-import">Carrier Import</a></div>
      </details>
      <details class="admin-nav-group" open>
        <summary><span>Network</span></summary>
        <div class="admin-nav-items">
          <a class="{dashboard_class}" href="/admin/vpn/">VPN &amp; Devices</a>
          <a class="{invites_class}" href="/admin/vpn/invites">Invites</a>
          <a class="{devices_class}" href="/admin/vpn/devices">Devices</a>
        </div>
      </details>
      <details class="admin-nav-group">
        <summary><span>Security &amp; Identity</span></summary>
        <div class="admin-nav-items"><a href="https://ww.cx/admin/auth-identities.php">Sign-in Methods</a></div>
      </details>
      <details class="admin-nav-group">
        <summary><span>System</span></summary>
        <div class="admin-nav-items"><a href="https://ww.cx/admin/?page=settings">Settings</a></div>
      </details>
    </nav>
    <div class="admin-sidebar-session">
      <a class="admin-sidebar-footer" href="https://ww.cx/admin/?page=account" aria-label="WW.CX account settings">
        <span>WW.CX account</span><strong>Account settings</strong><small>Open account settings →</small>
      </a>
    </div>
  </aside>
  <button class="admin-sidebar-scrim" type="button" aria-label="Close navigation" data-admin-menu-close></button>
  <div class="admin-main-column">
    <header class="admin-topbar">
      <div><div class="admin-breadcrumb">Network</div><div class="admin-page-title">{escape(shell_title)}</div></div>
      <div class="admin-topbar-actions"><span class="status-pill"><span class="status-dot"></span>Edge1 VPN</span><a class="admin-account-chip" href="https://ww.cx/admin/?page=account">Account</a></div>
    </header>
    <main class="admin-content"><div class="wrap">{body}</div></main>
  </div>
</div>"""
        body_class = "admin-v2"
    else:
        layout = f"""
<main class="public-shell">
  <a class="public-brand" href="https://ww.cx/" aria-label="Christmas Island Worldwide">
    <img src="https://ww.cx/assets/icons/ciww-badge.svg" alt="Christmas Island Worldwide" referrerpolicy="no-referrer">
    <span><strong>WW.CX</strong><small>Secure VPN Enrollment</small></span>
  </a>
  <section class="public-card">{body}</section>
  <p class="public-foot">Protected enrollment service · Edge1</p>
</main>"""
        body_class = "public-vpn"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <meta name="referrer" content="no-referrer">
  <meta name="theme-color" content="#0b2f49">
  <title>{safe_title} · WW.CX</title>
  <style>
    :root{{--admin-navy:#123f60;--admin-navy-deep:#0b2f49;--admin-blue:#1b6fa8;--admin-bg:#f7f4ee;--admin-panel:#fff;--admin-line:#e5dfd4;--admin-text:#173f5b;--admin-muted:#667784;--admin-hover:#edf5fa;--admin-active:#dceefa;--admin-shadow:0 10px 30px rgba(18,63,96,.10);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:light}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--admin-bg);color:var(--admin-text)}}a{{color:var(--admin-blue)}}
    body.admin-v2{{overflow-x:hidden}}.admin-app{{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}}.admin-sidebar{{position:sticky;top:0;height:100vh;overflow-y:auto;scrollbar-width:none;background:linear-gradient(180deg,var(--admin-navy-deep),var(--admin-navy));color:#fff;border-right:1px solid rgba(255,255,255,.08);padding:22px 14px 18px;z-index:40}}.admin-sidebar::-webkit-scrollbar{{display:none}}.admin-brand{{display:flex;align-items:center;gap:11px;padding:0 8px 18px;color:#fff;text-decoration:none}}.admin-brand-art{{width:48px;height:48px;flex:0 0 48px;border-radius:50%;filter:drop-shadow(0 5px 12px rgba(0,0,0,.18))}}.admin-brand-copy{{display:grid;gap:2px;min-width:0}}.admin-brand-mark{{font-size:22px;font-weight:900;letter-spacing:-.03em;line-height:1}}.admin-brand-sub{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.16em;opacity:.72}}.admin-side-nav{{display:grid;gap:6px}}.admin-nav-group{{border-radius:12px}}.admin-nav-group summary{{list-style:none;cursor:pointer;padding:10px 11px;color:rgba(255,255,255,.74);font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.09em;border-radius:10px}}.admin-nav-group summary::-webkit-details-marker{{display:none}}.admin-nav-group summary::after{{content:'›';float:right;transform:rotate(90deg);transition:transform .15s ease}}.admin-nav-group:not([open]) summary::after{{transform:rotate(0)}}.admin-nav-group summary:hover,.admin-nav-group summary:focus-visible{{background:rgba(255,255,255,.08);color:#fff;outline:none}}.admin-nav-items{{display:grid;gap:3px;padding:2px 0 7px}}.admin-nav-items a{{display:block;color:rgba(255,255,255,.82);text-decoration:none;font-size:13px;font-weight:700;padding:9px 11px;border-radius:9px}}.admin-nav-items a:hover,.admin-nav-items a:focus-visible{{background:rgba(255,255,255,.10);color:#fff;outline:none}}.admin-nav-items a.is-active{{background:#fff;color:var(--admin-navy-deep);box-shadow:0 4px 14px rgba(0,0,0,.12)}}.admin-sidebar-session{{margin-top:18px;padding-top:12px;border-top:1px solid rgba(255,255,255,.12)}}.admin-sidebar-footer{{padding:10px 11px;display:grid;gap:3px;font-size:12px;color:rgba(255,255,255,.66);text-decoration:none;border-radius:10px;transition:background .15s ease,color .15s ease}}.admin-sidebar-footer strong{{color:#fff;overflow-wrap:anywhere}}.admin-sidebar-footer small{{margin-top:3px;color:rgba(255,255,255,.52);font-size:11px}}.admin-sidebar-footer:hover,.admin-sidebar-footer:focus-visible{{background:rgba(255,255,255,.08);color:#fff;outline:none}}.admin-main-column{{min-width:0}}.admin-topbar{{position:sticky;top:0;z-index:30;min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:12px 26px;background:rgba(255,255,255,.94);backdrop-filter:blur(12px);border-bottom:1px solid var(--admin-line)}}.admin-breadcrumb{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:var(--admin-muted);margin-bottom:4px}}.admin-page-title{{font-size:20px;font-weight:850;letter-spacing:-.02em}}.admin-topbar-actions{{display:flex;align-items:center;gap:10px}}.admin-account-chip{{display:inline-flex;align-items:center;min-height:38px;padding:7px 11px;border:1px solid var(--admin-line);border-radius:999px;background:#fff;font-size:13px;font-weight:700;color:var(--admin-text);text-decoration:none}}.admin-account-chip:hover,.admin-account-chip:focus-visible{{border-color:#c7dbe8;background:var(--admin-hover);outline:none;box-shadow:0 0 0 3px rgba(27,111,168,.10)}}.status-pill{{display:inline-flex;align-items:center;gap:7px;padding:7px 11px;border-radius:999px;background:#eef8f2;border:1px solid #d3eadb;color:#24633d;font-size:12px;font-weight:800}}.status-dot{{width:7px;height:7px;border-radius:50%;background:#41a566;box-shadow:0 0 0 3px rgba(65,165,102,.12)}}.admin-content{{width:min(1420px,100%);padding:28px;margin:0 auto}}.wrap{{width:100%}}.admin-mobile-menu{{display:none;position:fixed;top:14px;left:14px;z-index:60;width:42px;height:42px;min-height:42px;padding:0;border:0;border-radius:10px;background:#fff;color:var(--admin-navy-deep);box-shadow:var(--admin-shadow);font-size:20px}}.admin-sidebar-scrim{{display:none;border:0;padding:0}}
    h1{{font-size:30px;line-height:1.15;letter-spacing:-.03em;margin:0 0 8px}}h2{{font-size:18px;margin:0 0 14px}}p{{line-height:1.55}}.lead{{margin:0;color:var(--admin-muted);font-size:15px}}.page-heading{{margin-bottom:22px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-bottom:18px}}.card{{background:#fff;border:1px solid var(--admin-line);border-radius:16px;padding:20px;box-shadow:var(--admin-shadow);margin-bottom:18px}}.metric{{font-size:28px;font-weight:850;letter-spacing:-.03em;margin-bottom:2px}}.metric-label{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:var(--admin-muted)}}.metric-note{{font-size:12px;color:var(--admin-muted);margin-top:5px}}.form-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}label{{display:block;margin:0 0 6px;color:var(--admin-text);font-size:12px;font-weight:800}}input,select{{width:100%;min-height:42px;padding:10px 11px;border-radius:10px;border:1px solid #d7d3ca;background:#fff;color:var(--admin-text);font:inherit}}input:focus,select:focus{{outline:none;border-color:#7fb2d2;box-shadow:0 0 0 3px rgba(27,111,168,.12)}}button,.button{{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:9px 14px;border:0;border-radius:10px;background:var(--admin-blue);color:#fff;font:inherit;font-size:13px;font-weight:800;cursor:pointer;text-decoration:none}}button:hover,.button:hover{{filter:brightness(.96)}}button.danger{{background:#fff1f2;color:#a12838;border:1px solid #f0c8cf;min-height:34px;padding:6px 9px;margin:0}}.actions{{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:16px}}.muted{{color:var(--admin-muted)}}.error{{color:#a12838}}.notice{{padding:12px 14px;border-radius:10px;background:#edf5fa;border:1px solid #d5e5ef;margin:0 0 16px}}pre{{overflow:auto;padding:14px;border-radius:10px;background:#f7f9fa;border:1px solid var(--admin-line);color:#294b61;font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}}.table-wrap{{overflow:auto;border:1px solid var(--admin-line);border-radius:12px}}table{{width:100%;border-collapse:collapse;background:#fff;min-width:720px}}th,td{{text-align:left;padding:11px 12px;border-bottom:1px solid #ece8e0;vertical-align:top;font-size:13px}}th{{background:#faf8f4;color:var(--admin-muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:850}}tr:last-child td{{border-bottom:0}}td form{{margin:0}}.pill{{display:inline-flex;padding:3px 8px;border-radius:999px;background:#edf5fa;color:#315f7d;font-size:11px;font-weight:800}}.pill.off{{background:#f3f0ea;color:#776f64}}.qr{{display:grid;place-items:center;background:#fff;padding:16px;border-radius:14px;width:fit-content;margin:18px 0;border:1px solid var(--admin-line);box-shadow:var(--admin-shadow)}}.qr img{{width:min(360px,calc(100vw - 96px));height:auto}}details.config{{margin-top:14px}}details.config summary{{cursor:pointer;font-weight:800;color:var(--admin-blue)}}
    .public-vpn{{min-height:100vh;display:grid;place-items:center;padding:28px;background:radial-gradient(circle at 20% 0,#eef6fb 0,transparent 35%),var(--admin-bg)}}.public-shell{{width:min(660px,100%);margin:auto}}.public-brand{{display:flex;align-items:center;gap:12px;width:fit-content;margin:0 auto 18px;color:var(--admin-text);text-decoration:none}}.public-brand img{{width:54px;height:54px;border-radius:50%;filter:drop-shadow(0 5px 12px rgba(18,63,96,.16))}}.public-brand span{{display:grid;gap:1px}}.public-brand strong{{font-size:22px;letter-spacing:-.03em}}.public-brand small{{color:var(--admin-muted);font-weight:700}}.public-card{{background:#fff;border:1px solid var(--admin-line);border-radius:20px;padding:28px;box-shadow:0 18px 55px rgba(18,63,96,.12)}}.public-card h1{{font-size:28px}}.public-foot{{text-align:center;color:var(--admin-muted);font-size:12px;margin:14px 0 0}}
    @media(max-width:900px){{.admin-app{{display:block}}.admin-mobile-menu{{display:block}}.admin-sidebar{{position:fixed;left:0;top:0;width:min(310px,86vw);transform:translateX(-104%);transition:transform .18s ease;box-shadow:0 20px 60px rgba(0,0,0,.28)}}.admin-app.menu-open .admin-sidebar{{transform:translateX(0)}}.admin-sidebar-scrim{{position:fixed;inset:0;z-index:35;background:rgba(8,30,46,.38)}}.admin-app.menu-open .admin-sidebar-scrim{{display:block}}.admin-topbar{{padding-left:68px}}.admin-account-chip{{display:none}}.admin-content{{padding:20px 16px}}}}
    @media(max-width:640px){{.form-grid{{grid-template-columns:1fr}}.admin-topbar{{min-height:64px;padding-right:12px}}.admin-page-title{{font-size:17px}}.admin-breadcrumb{{display:none}}.admin-content{{padding:14px 12px}}.status-pill{{display:none}}.public-vpn{{padding:18px}}.public-card{{padding:22px}}}}
  </style>
</head>
<body class="{body_class}">{layout}
<script>
(()=>{{
  const app=document.querySelector('[data-admin-app]'); if(!app)return;
  const toggle=document.querySelector('[data-admin-menu-toggle]'); const close=document.querySelector('[data-admin-menu-close]');
  const setOpen=(open)=>{{app.classList.toggle('menu-open',open);if(toggle)toggle.setAttribute('aria-expanded',open?'true':'false')}};
  if(toggle)toggle.addEventListener('click',()=>setOpen(!app.classList.contains('menu-open'))); if(close)close.addEventListener('click',()=>setOpen(false));
  document.addEventListener('keydown',e=>{{if(e.key==='Escape')setOpen(false)}});
}})();
</script>
</body>
</html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "Edge1VPNEnroll/0.1"

    def send_html(self, status: int, title: str, body: str) -> None:
        payload = page(title, body, urlparse(self.path).path)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_text(self, status: int, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def token_from_path(self) -> str | None:
        parsed = urlparse(self.path)
        parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
        if len(parts) == 2 and parts[0] == "i":
            return parts[1]
        return None

    def admin_nav(self) -> str:
        # Navigation is rendered by the shared Admin v2 application shell.
        return ""

    def enroll_base_url(self) -> str:
        return (self.server.config.get("enroll_base_url") or self.server.config.get("base_url") or "").rstrip("/")

    def admin_public_prefix(self) -> str:
        configured = self.server.config.get("admin_base_url") or "/admin"
        parsed = urlparse(configured)
        path = parsed.path if parsed.scheme else configured
        path = "/" + path.strip("/")
        return path.rstrip("/")

    def admin_url(self, admin_path: str) -> str:
        suffix = admin_path.removeprefix("/admin")
        if suffix in ("", "/"):
            return self.admin_public_prefix() + "/"
        return self.admin_public_prefix() + "/" + suffix.strip("/")

    def cookie_value(self, name: str) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        try:
            jar = SimpleCookie()
            jar.load(raw)
            morsel = jar.get(name)
            return morsel.value if morsel is not None else ""
        except Exception:
            return ""

    def admin_session_identity(self) -> dict | None:
        raw_cookie = self.headers.get("Cookie", "")
        if "__Secure-wwcx_edge1_ops_session=" not in raw_cookie:
            return None
        request = Request(
            "http://127.0.0.1:8108/edge1-ops/session",
            headers={
                "Accept": "application/json",
                "Cookie": raw_cookie,
                "Host": "edge1.ww.cx",
                "X-Forwarded-Proto": "https",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=4) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read(8192).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return None
        if payload.get("authenticated") is not True or payload.get("source_role") != "admin":
            return None
        if "edge1.security.read" not in payload.get("scopes", []):
            return None
        return payload

    def require_admin_session(self) -> bool:
        identity = self.admin_session_identity()
        if identity is not None:
            self._admin_identity = identity
            return True
        self.send_response(303)
        self.send_header("Location", "https://ww.cx/admin/edge1-vpn-login.php")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def admin_csrf_field(self) -> str:
        token = self.cookie_value("__Secure-wwcx_edge1_ops_csrf")
        return f"<input type='hidden' name='_csrf' value='{escape(token)}'>" if token else ""

    def verify_admin_csrf(self, fields: dict) -> bool:
        cookie_token = self.cookie_value("__Secure-wwcx_edge1_ops_csrf")
        form_token = fields.get("_csrf", [""])[0]
        return bool(cookie_token and form_token and secrets.compare_digest(cookie_token, form_token))

    def admin_logout(self) -> None:
        csrf = self.cookie_value("__Secure-wwcx_edge1_ops_csrf")
        raw_cookie = self.headers.get("Cookie", "")
        if csrf and raw_cookie:
            request = Request(
                "http://127.0.0.1:8108/edge1-ops/session/logout",
                data=b"",
                headers={
                    "Cookie": raw_cookie,
                    "Host": "edge1.ww.cx",
                    "Origin": "https://edge1.ww.cx",
                    "X-Forwarded-Proto": "https",
                    "X-WWCX-CSRF": csrf,
                },
                method="POST",
            )
            try:
                urlopen(request, timeout=4).close()
            except (HTTPError, URLError, TimeoutError):
                pass
        self.send_response(303)
        self.send_header("Location", "https://ww.cx/admin/")
        self.send_header("Set-Cookie", "__Secure-wwcx_edge1_ops_session=; Path=/edge1-ops/; Max-Age=0; Secure; HttpOnly; SameSite=Strict")
        self.send_header("Set-Cookie", "__Secure-wwcx_edge1_ops_csrf=; Path=/edge1-ops/; Max-Age=0; Secure; SameSite=Strict")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def admin_dashboard(self, message: str = "") -> None:
        all_invites = list_rows(self.server.config, "invites")
        all_devices = list_rows(self.server.config, "devices")
        rows = all_invites[:8]
        latest = self.invites_table(rows)
        notice = f"<div class='notice'>{escape(message)}</div>" if message else ""
        open_invites = sum(1 for row in all_invites if not row["revoked_at"] and row["uses"] < row["max_uses"])
        active_devices = sum(1 for row in all_devices if not row["revoked_at"])
        profiles = "".join(
            f"<option value='{escape(name)}'>{escape(name)} - {escape(value)}</option>"
            for name, value in self.server.config["profiles"].items()
        )
        body = f"""
<div class="page-heading"><h1>VPN &amp; Devices</h1><p class="lead">Invite devices onto the Edge1 WireGuard network and manage enrollment from one place.</p></div>
{notice}
<div class="grid">
  <div class="card"><div class="metric">{active_devices}</div><div class="metric-label">Active devices</div><div class="metric-note">Current enrollment records</div></div>
  <div class="card"><div class="metric">{open_invites}</div><div class="metric-label">Open invites</div><div class="metric-note">Available to redeem</div></div>
  <div class="card"><div class="metric">{len(self.server.config["profiles"])}</div><div class="metric-label">Tunnel profiles</div><div class="metric-note">Split and full tunnel options</div></div>
  <div class="card"><div class="metric">10.77.0.1</div><div class="metric-label">Edge1 gateway</div><div class="metric-note">Private VPN DNS and gateway</div></div>
</div>
<div class="card"><h2>Create invite</h2><form method="post" action="{escape(self.admin_url('/admin/create-invite'))}">{self.admin_csrf_field()}<div class="form-grid">
  <div><label for="label">Invite label</label><input id="label" name="label" required maxlength="120" placeholder="Example: Alice Pixel"></div>
  <div><label for="profile">Tunnel profile</label><select id="profile" name="profile">{profiles}</select></div>
  <div><label for="expires_hours">Expires after hours</label><input id="expires_hours" name="expires_hours" type="number" min="1" max="720" value="72"></div>
  <div><label for="max_uses">Maximum uses</label><input id="max_uses" name="max_uses" type="number" min="1" max="20" value="1"></div>
</div><div class="actions"><button type="submit">Create Invite</button></div></form></div>
<div class="card"><h2>Recent invites</h2>{latest}</div>
"""
        self.send_html(200, "VPN Admin", body)

    def invites_table(self, rows) -> str:
        if not rows:
            return "<p class='muted'>No invites yet.</p>"
        body = [
            "<table><thead><tr><th>ID</th><th>Label</th><th>Profile</th><th>Uses</th><th>Expires</th><th>Revoked</th><th>Action</th></tr></thead><tbody>"
        ]
        for row in rows:
            action = ""
            if not row["revoked_at"]:
                action = f"""
<form method="post" action="{escape(self.admin_url('/admin/revoke-invite'))}" style="margin:0">
  {self.admin_csrf_field()}
  <input type="hidden" name="invite_id" value="{escape(row['id'])}">
  <button class="danger" type="submit">Revoke</button>
</form>"""
            body.append(
                "<tr>"
                f"<td>{escape(row['id'])}</td>"
                f"<td>{escape(row['label'])}</td>"
                f"<td>{escape(row['profile'])}</td>"
                f"<td>{escape(row['uses'])}/{escape(row['max_uses'])}</td>"
                f"<td>{escape(row['expires_at'])}</td>"
                f"<td>{escape(row['revoked_at'] or '')}</td>"
                f"<td>{action}</td>"
                "</tr>"
            )
        body.append("</tbody></table></div>")
        body.insert(0, "<div class='table-wrap'>")
        return "".join(body)

    def devices_table(self, rows) -> str:
        if not rows:
            return "<p class='muted'>No devices yet.</p>"
        body = [
            "<table><thead><tr><th>ID</th><th>Label</th><th>Address</th><th>Profile</th><th>Created</th><th>Revoked</th><th>Action</th></tr></thead><tbody>"
        ]
        for row in rows:
            action = ""
            if not row["revoked_at"]:
                action = f"""
<form method="post" action="{escape(self.admin_url('/admin/revoke-device'))}" style="margin:0">
  {self.admin_csrf_field()}
  <input type="hidden" name="device_id" value="{escape(row['id'])}">
  <button class="danger" type="submit">Revoke</button>
</form>"""
            body.append(
                "<tr>"
                f"<td>{escape(row['id'])}</td>"
                f"<td>{escape(row['label'])}</td>"
                f"<td>{escape(row['address'])}</td>"
                f"<td>{escape(row['profile'])}</td>"
                f"<td>{escape(row['created_at'])}</td>"
                f"<td>{escape(row['revoked_at'] or '')}</td>"
                f"<td>{action}</td>"
                "</tr>"
            )
        body.append("</tbody></table></div>")
        body.insert(0, "<div class='table-wrap'>")
        return "".join(body)


    def handle_internal_account(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_text(400, "bad request\n")
            return
        if length < 2 or length > 16384:
            self.send_text(400, "bad request\n")
            return
        body = self.rfile.read(length)
        owner_subject = verify_internal_signature(self.headers, "POST", "/internal/account", body)
        if owner_subject is None:
            self.send_text(401, "authentication required\n")
            return
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict) or set(payload) != {"action", "parameters"}:
                raise ValueError("invalid request")
            action = payload["action"]
            parameters = payload["parameters"]
            if not isinstance(action, str) or not isinstance(parameters, dict):
                raise ValueError("invalid request")
            if action == "list":
                result = {"devices": list_owned_devices(self.server.config, owner_subject)}
            elif action in {"enroll", "reregister"}:
                label = str(parameters.get("label", "")).strip()[:80]
                profile = str(parameters.get("profile", "split"))
                display_name = str(parameters.get("owner_display_name", "")).strip()[:256]
                if not label:
                    raise ValueError("device name is required")
                invite_id, token = create_invite(
                    self.server.config, label, profile, 24, 1,
                    "account-self-service", owner_subject, display_name,
                )
                result = {
                    "invite_id": invite_id,
                    "enroll_url": f"{self.enroll_base_url()}/i/{token}",
                }
            elif action == "rename":
                result = rename_owned_device(
                    self.server.config, int(parameters.get("device_id", 0)),
                    owner_subject, str(parameters.get("label", "")),
                )
            elif action == "revoke":
                revoke_owned_device(
                    self.server.config, int(parameters.get("device_id", 0)), owner_subject
                )
                result = {"revoked": True}
            else:
                raise ValueError("unsupported action")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            encoded = json.dumps({"error": str(exc)}, separators=(",", ":")).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)
            return
        encoded = json.dumps({"result": result}, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path == "/health":
            self.send_text(200, "ok\n")
            return

        if parsed_path.startswith("/admin") and not self.require_admin_session():
            return

        if parsed_path in ("/admin", "/admin/"):
            self.admin_dashboard()
            return

        if parsed_path == "/admin/invites":
            rows = list_rows(self.server.config, "invites")
            self.send_html(200, "VPN Invites", f"<div class='page-heading'><h1>VPN Invites</h1><p class='lead'>Create, track, and revoke one-time enrollment links.</p></div><div class='card'>{self.invites_table(rows)}</div>")
            return

        if parsed_path == "/admin/devices":
            rows = list_rows(self.server.config, "devices")
            self.send_html(200, "VPN Devices", f"<div class='page-heading'><h1>VPN Devices</h1><p class='lead'>Devices enrolled on the Edge1 WireGuard network.</p></div><div class='card'>{self.devices_table(rows)}</div>")
            return

        token = self.token_from_path()
        if not token:
            self.send_html(404, "Not Found", "<h1>Not found</h1>")
            return

        invite = get_invite_by_token(self.server.config, token)
        ok, reason = invite_is_redeemable(invite)
        if not ok:
            self.send_html(410, "Invite unavailable", f"<h1>Invite unavailable</h1><p class='error'>{escape(reason)}</p>")
            return

        body = f"""
<div class="page-heading"><h1>Enroll this device</h1><p class="lead">Securely add a device to the WW.CX Edge1 VPN.</p></div>
<div class="notice"><strong>Invite:</strong> {escape(invite["label"])} &nbsp;·&nbsp; <strong>Profile:</strong> {escape(invite["profile"])}</div>
<form method="post"><label for="device_label">Device name</label><input id="device_label" name="device_label" required maxlength="80" placeholder="Example: John's Pixel"><div class="actions"><button type="submit">Generate VPN QR Code</button></div></form>
"""
        self.send_html(200, "Enroll Device", body)

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path == "/internal/account":
            self.handle_internal_account()
            return
        if parsed_path.startswith("/admin") and not self.require_admin_session():
            return
        if parsed_path == "/admin/logout":
            self.admin_logout()
            return
        if parsed_path == "/admin/create-invite":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 4096)).decode("utf-8", errors="replace")
            fields = parse_qs(raw)
            if not self.verify_admin_csrf(fields):
                self.send_html(403, "Forbidden", "<h1>Request expired</h1><p class='error'>Reload the VPN admin page and try again.</p>")
                return
            label = fields.get("label", [""])[0].strip()
            profile = fields.get("profile", ["split"])[0]
            try:
                expires_hours = max(1, min(720, int(fields.get("expires_hours", ["72"])[0])))
                max_uses = max(1, min(20, int(fields.get("max_uses", ["1"])[0])))
                invite_id, token = create_invite(self.server.config, label, profile, expires_hours, max_uses, "web-admin")
                invite_url = f"{self.enroll_base_url()}/i/{token}"
            except Exception as exc:
                self.send_html(400, "Invite Failed", f"{self.admin_nav()}<h1>Invite Failed</h1><p class='error'>{escape(exc)}</p>")
                return
            body = f"""
<div class="page-heading"><h1>Invite Created</h1><p class="lead">The enrollment link is ready to share.</p></div><div class="card"><span class="pill">Invite #{escape(invite_id)}</span><p>Send this link to the invitee:</p><pre>{escape(invite_url)}</pre><p class="muted">The full token is shown only now. It is stored as a hash after creation.</p><div class="actions"><a class="button" href="{escape(self.admin_url('/admin/invites'))}">View invites</a><a class="button" style="background:#eef4f7;color:#173f5b" href="{escape(self.admin_url('/'))}">Back to VPN dashboard</a></div></div>
"""
            self.send_html(200, "Invite Created", body)
            return

        if parsed_path == "/admin/revoke-device":
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(min(length, 1024)).decode("utf-8", errors="replace"))
            if not self.verify_admin_csrf(fields):
                self.send_html(403, "Forbidden", "<h1>Request expired</h1><p class='error'>Reload the VPN admin page and try again.</p>")
                return
            try:
                revoke_device(self.server.config, int(fields.get("device_id", ["0"])[0]))
            except Exception as exc:
                self.send_html(400, "Revoke Failed", f"{self.admin_nav()}<h1>Revoke Failed</h1><p class='error'>{escape(exc)}</p>")
                return
            self.send_html(200, "Device Revoked", f"{self.admin_nav()}<h1>Device Revoked</h1><p>The device was revoked.</p>")
            return

        if parsed_path == "/admin/revoke-invite":
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(min(length, 1024)).decode("utf-8", errors="replace"))
            if not self.verify_admin_csrf(fields):
                self.send_html(403, "Forbidden", "<h1>Request expired</h1><p class='error'>Reload the VPN admin page and try again.</p>")
                return
            try:
                revoke_invite(self.server.config, int(fields.get("invite_id", ["0"])[0]))
            except Exception as exc:
                self.send_html(400, "Revoke Failed", f"{self.admin_nav()}<h1>Revoke Failed</h1><p class='error'>{escape(exc)}</p>")
                return
            self.send_html(200, "Invite Revoked", f"{self.admin_nav()}<h1>Invite Revoked</h1><p>The invite was revoked.</p>")
            return

        token = self.token_from_path()
        if not token:
            self.send_html(404, "Not Found", "<h1>Not found</h1>")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(min(length, 4096)).decode("utf-8", errors="replace")
        fields = parse_qs(raw)
        device_label = fields.get("device_label", [""])[0]

        try:
            result = enroll_device(self.server.config, token, device_label)
        except Exception as exc:
            if self.server.config.get("debug"):
                detail = f"<pre>{escape(traceback.format_exc())}</pre>"
            else:
                detail = f"<p class='error'>{escape(exc)}</p>"
            self.send_html(400, "Enrollment failed", f"<h1>Enrollment failed</h1>{detail}")
            return

        qr = ""
        if result.qr_svg:
            qr = f"<div class='qr'><img alt='WireGuard QR code' src='{svg_data_uri(result.qr_svg)}'></div>"
        else:
            qr = "<p class='error'>QR rendering is unavailable because qrencode is missing on the server.</p>"

        body = f"""
<div class="page-heading"><h1>VPN Profile Ready</h1><p class="lead">Your WireGuard profile is ready for one-time setup.</p></div><div class="notice"><strong>Device:</strong> {escape(result.label)} &nbsp;·&nbsp; <strong>Address:</strong> {escape(result.address)} &nbsp;·&nbsp; <strong>Profile:</strong> {escape(result.profile)}</div>{qr}<p>Scan this once with the WireGuard app. This page will not be available again after you leave.</p><details class="config"><summary>Show manual configuration</summary><pre>{escape(result.config_text)}</pre></details>
"""
        self.send_html(200, "VPN Profile Ready", body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Edge1 VPN enrollment portal.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    server = ThreadingHTTPServer((config["listen_host"], int(config["listen_port"])), Handler)
    server.config = config
    print(f"Listening on http://{config['listen_host']}:{config['listen_port']}")
    server.serve_forever()


if __name__ == "__main__":
    main()
