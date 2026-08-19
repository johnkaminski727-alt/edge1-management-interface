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
    "FAILED_CHECKS",
    '"$FAILED_CHECKS" = "oauth_metadata"',
    "unauthenticated_mcp_http",
    "oauth_path_candidate_http",
    "oauth_root_candidate_http",
    "EDGE1_TUNNEL_COMPAT_DOCTOR=PASS",
    "Authorization: env:EDGE1_MCP_AUTHORIZATION",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required compatibility behavior: {token}")

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
