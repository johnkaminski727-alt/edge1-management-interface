#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
POLICY = ROOT / "config" / "security" / "edge1-security-operator-console.json"
PAGE = ROOT / "src" / "web" / "edge1-ops" / "security" / "index.html"

policy = json.loads(POLICY.read_text(encoding="utf-8"))
page = PAGE.read_text(encoding="utf-8")

assert policy["contract"] == "wwcx.edge1-security-operator-console.v1"
assert policy["status"] == "design_only"
assert policy["enabled"] is False
assert policy["deployment_authorized"] is False
assert policy["authentication_change_authorized"] is False
assert policy["live_route_authorized"] is False
assert policy["route"] == "/edge1-ops/security/"
assert policy["operations_api"]["browser_direct_access"] is False
assert policy["operations_api"]["server_side_gateway_required"] is True
assert policy["operations_api"]["browser_signing_secret_allowed"] is False
assert policy["acceptance"]["mutations_enabled"] is False
assert policy["acceptance"]["live_authentication_changed"] is False
assert policy["acceptance"]["live_route_changed"] is False
assert policy["acceptance"]["traffic_controls_changed"] is False

browser = policy["required_browser_controls"]
assert "Business159" in browser["authentication"]
assert browser["identity_authority"] == "Business159 WW.CX user and role directory"
assert browser["business159_cookie_accepted"] is False
assert browser["business159_database_access"] is False
assert browser["password_material_accepted"] is False
assert browser["operations_event_correlation"] is True
assert browser["no_anonymous_fallback"] is True

actions = {item["id"]: item for item in policy["actions"]}
assert set(actions) == {
    "security.validate_config",
    "security.rules.reload",
    "security.logs.rotate",
}
assert actions["security.validate_config"]["mutating"] is False
assert actions["security.validate_config"]["required_scope"] == "edge1.security.validate"
assert actions["security.rules.reload"]["mutating"] is True
assert actions["security.rules.reload"]["required_scope"] == "edge1.security.rules.reload"
assert actions["security.logs.rotate"]["mutating"] is True
assert actions["security.logs.rotate"]["required_scope"] == "edge1.security.logs.rotate"
assert actions["security.rules.reload"]["confirmation_phrase"] == "LOAD RULES"
assert actions["security.logs.rotate"]["confirmation_phrase"] == "ROTATE LOGS"

required_page_markers = (
    "Edge1 Security Service Console",
    "You should not need to know service names, command-line switches, or API calls.",
    "Check the security configuration",
    "Load updated detection rules",
    "Rotate security logs now",
    "Restart the managed sensor",
    "Actions locked",
    "secure browser sign-in",
    "append-only audit records",
    'const TELEMETRY="/edge1-status/security-operations.json"',
    "No action was attempted.",
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
    "fetch(\"http://",
    "fetch('http://",
)
present = [marker for marker in forbidden_page_markers if marker in page]
if present:
    raise SystemExit(f"browser page exposes forbidden operations details: {present}")

for action_label in ("Run check", "Load rules", "Rotate logs", "Not yet available"):
    marker = f">{action_label}</button>"
    index = page.find(marker)
    if index < 0:
        raise SystemExit(f"button not found: {action_label}")
    opening = page.rfind("<button", 0, index)
    button = page[opening:index]
    if "disabled" not in button:
        raise SystemExit(f"production action button is not locked: {action_label}")

print("Security operator console validation passed")
