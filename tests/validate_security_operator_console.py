#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
POLICY = ROOT / "config" / "security" / "edge1-security-operator-console.json"
PAGE = ROOT / "src" / "web" / "edge1-ops" / "security" / "index.html"

policy = json.loads(POLICY.read_text(encoding="utf-8"))
page = PAGE.read_text(encoding="utf-8")

assert policy["contract"] == "wwcx.edge1-security-operator-console.v1"
assert policy["status"] == "staged_read_only"
assert policy["enabled"] is False
assert policy["deployment_authorized"] is False
assert policy["authentication_change_authorized"] is False
assert policy["live_route_authorized"] is False
assert policy["route"] == "/edge1-ops/security/"
assert policy["sign_in_url"] == "https://ww.cx/admin/edge1-security-login.php"
assert policy["operations_api"]["browser_direct_access"] is False
assert policy["operations_api"]["server_side_gateway_required"] is True
assert policy["operations_api"]["browser_signing_secret_allowed"] is False
assert policy["acceptance"]["authenticated_console_implemented"] is True
assert policy["acceptance"]["read_only_validation_implemented"] is True
assert policy["acceptance"]["mutations_enabled"] is False
assert policy["acceptance"]["live_authentication_changed"] is False
assert policy["acceptance"]["live_route_changed"] is False
assert policy["acceptance"]["traffic_controls_changed"] is False

browser = policy["required_browser_controls"]
assert "Business159" in browser["authentication"]
assert browser["browser_origin"] == "https://ww.cx"
assert browser["identity_authority"] == "Business159 WW.CX user and role directory"
assert browser["business159_cookie_accepted"] is False
assert browser["business159_database_access"] is False
assert browser["password_material_accepted"] is False
assert browser["operations_event_correlation"] is True
assert browser["nonce_content_security_policy"] is True
assert browser["no_anonymous_fallback"] is True

actions = {item["id"]: item for item in policy["actions"]}
assert set(actions) == {
    "security.validate_config",
    "security.rules.reload",
    "security.logs.rotate",
}
assert actions["security.validate_config"]["mutating"] is False
assert actions["security.validate_config"]["required_scope"] == "edge1.security.validate"
assert actions["security.validate_config"]["available_after_gateway_activation"] is True
assert actions["security.rules.reload"]["mutating"] is True
assert actions["security.rules.reload"]["available_after_gateway_activation"] is False
assert actions["security.logs.rotate"]["mutating"] is True
assert actions["security.logs.rotate"]["available_after_gateway_activation"] is False

required_page_markers = (
    "Edge1 Security Console",
    "Authenticated, read-only validation",
    "Run configuration check",
    "Mutation access",
    "Disabled",
    'const SESSION_URL="/edge1-ops/session"',
    'const VALIDATE_URL="/edge1-ops/api/v1/security/validate"',
    'const LOGOUT_URL="/edge1-ops/session/logout"',
    'const CSRF_COOKIE="__Secure-wwcx_edge1_ops_csrf"',
    "https://ww.cx/admin/edge1-security-login.php",
    'session.scopes.includes("edge1.security.validate")',
    '"X-WWCX-CSRF":csrf',
    "payload.event_id",
)
missing = [marker for marker in required_page_markers if marker not in page]
if missing:
    raise SystemExit(f"security operator console markers missing: {missing}")

forbidden_page_markers = (
    "127.0.0.1:8097",
    "X-WWCX-Signature",
    "X-WWCX-Nonce",
    "X-WWCX-Actor",
    "edge1-operations-api.secret",
    "/v1/actions/",
    "EDGE1_OPS_MUTATIONS_ENABLED",
    "Load rules",
    "Rotate logs",
    "Restart the managed sensor",
    "fetch(\"http://",
    "fetch('http://",
)
present = [marker for marker in forbidden_page_markers if marker in page]
if present:
    raise SystemExit(f"browser page exposes forbidden operations details: {present}")

assert page.count("<style>") == 1
assert page.count("<script>") == 1
assert "unsafe-inline" not in page

print("Security operator console validation passed")
