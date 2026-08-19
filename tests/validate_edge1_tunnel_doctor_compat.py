#!/usr/bin/env python3
"""Static safety validation for the Edge1 Secure MCP Tunnel doctor compatibility gate."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh"
LAUNCHER = ROOT / "deploy/edge1-tunnel/edge1-secure-mcp-tunnel.sh"
CONFIG = ROOT / "deploy/edge1-tunnel/tunnel-client.yaml"
SERVICE = ROOT / "deploy/edge1-tunnel/edge1-secure-mcp-tunnel.service"

text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "EXPECTED_CLIENT_SHA=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100",
    "EXPECTED_CLIENT_VERSION='0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144'",
    "require_metadata",
    "FAILED_CHECKS",
    '"$FAILED_CHECKS" = "oauth_metadata"',
    '"unauthenticated_mcp"',
    '"authenticated_mcp"',
    'checks["authenticated_mcp"] != 405',
    '"oauth_path_candidate"',
    '"oauth_root_candidate"',
    'print(f"{name}_http={code}")',
    "pinned raw doctor result changed; re-review required",
    "EDGE1_TUNNEL_COMPAT_DOCTOR=PASS",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required compatibility behavior: {token}")

# Keep the runtime integrity pins mechanically tied to the repository assets.
# A future launcher/config/unit edit must deliberately update the validator pin
# in the same change or CI fails.
asset_pins = {
    "EXPECTED_LAUNCHER_SHA": LAUNCHER,
    "EXPECTED_CONFIG_SHA": CONFIG,
    "EXPECTED_SERVICE_SHA": SERVICE,
}
for name, path in asset_pins.items():
    match = re.search(rf"^{name}=([0-9a-f]{{64}})$", text, re.MULTILINE)
    if match is None:
        raise SystemExit(f"missing or malformed runtime integrity pin: {name}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if match.group(1) != actual:
        raise SystemExit(
            f"stale runtime integrity pin: {name} expected {actual}, found {match.group(1)}"
        )

# The exact pinned old client is expected to keep returning the one reviewed
# OAuth-metadata false negative. A raw success must not bypass the independent
# bearer/config/service-integrity checks.
if re.search(r'if\s+\[\s+"\$DOCTOR_RC"\s+-eq\s+0\s+\]', text):
    raise SystemExit("raw doctor success bypass must not be present")

prohibited_patterns = (
    r"\bsystemctl[ \t]+(start|stop|restart|enable|disable|mask|unmask)\b",
    r"\bservice[ \t]+\S+[ \t]+(start|stop|restart)\b",
    r"\bnft[ \t]+(add|delete|insert|replace|flush)\b",
    r"\biptables\b",
    r"\bufw\b",
    r"\bapt(-get)?[ \t]+(install|upgrade|full-upgrade|dist-upgrade)\b",
    r"\bcurl\b.*Authorization",
    r"\becho\b.*(MCP_TOKEN|API_KEY|TUNNEL_ID)",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text, re.IGNORECASE):
        raise SystemExit(f"prohibited compatibility-gate behavior present: {pattern}")

print("Edge1 tunnel doctor compatibility gate safety validation passed")
