#!/usr/bin/env python3
"""Static safety validation for the Edge1 Secure MCP Tunnel doctor compatibility gate."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh"

text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "EXPECTED_CLIENT_SHA=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100",
    "EXPECTED_CLIENT_VERSION='0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144'",
    "EXPECTED_LAUNCHER_SHA=c0b7788bc40c3668b75b6f6410885bd9ce89a39e08c962b80a2e86f4497868f4",
    "EXPECTED_CONFIG_SHA=370c00ebb6a7a82d27137feb7a30beb6b881d8482c6ec950faf73cf42187b566",
    "EXPECTED_SERVICE_SHA=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd",
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
