#!/usr/bin/env python3
"""Static checks for the Edge1 Agent Shell Claude connector deployment assets."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy/edge1-claude-gateway'

installer = (DEPLOY / 'install-edge1-claude-gateway.sh').read_text(encoding='utf-8')
unit = (DEPLOY / 'edge1-claude-gateway.service').read_text(encoding='utf-8')
site = (DEPLOY / 'mcp-edge1.ww.cx.nginx.conf').read_text(encoding='utf-8')
subprocess.run(['sh', '-n', str(DEPLOY / 'install-edge1-claude-gateway.sh')], check=True)

# Upstream is the loopback Agent Shell; the gateway itself stays on loopback.
assert 'Environment=B159_GATEWAY_UPSTREAM_URL=http://127.0.0.1:8114/mcp' in unit
assert 'Environment=B159_GATEWAY_HOST=127.0.0.1' in unit
assert 'Environment=B159_GATEWAY_PORT=8151' in unit
# Operator-approved full access, with a shorter sign-in lifetime.
assert 'Environment=B159_GATEWAY_TOOLS=*' in unit
assert 'Environment=B159_GATEWAY_REFRESH_TTL=604800' in unit
assert 'FULL ROOT ACCESS' in unit
# The gateway does not run as root.
assert 'User=edge1-claude-gw' in unit and 'User=root' not in unit
for directive in ('NoNewPrivileges=true', 'ProtectSystem=strict', 'ProtectHome=true', 'CapabilityBoundingSet=', 'MemoryDenyWriteExecute=true'):
    assert directive in unit, directive

# Public front: Anthropic-only /mcp and /token, everything else 404, no wildcard listener.
assert site.count('allow 160.79.104.0/21;') == 2 and site.count('deny all;') == 2
assert 'proxy_pass http://127.0.0.1:8151;' in site
assert 'listen __EDGE1_PUBLIC_IP__:443 ssl;' in site and 'listen 443' not in site
assert 'return 404;' in site
assert 'proxy_set_header X-Forwarded-For $remote_addr;' in site

# Installer: separate identity and paths, dry run by default, never touches the shared checkout.
assert 'MODE=dry-run' in installer
assert 'HOSTNAME_PUBLIC=mcp-edge1.ww.cx' in installer and 'PORT=8151' in installer
assert 'ETC_DIR=/etc/edge1-claude-gateway' in installer
assert '"$DEPLOY/edge1-claude-gateway.service"' in installer
assert 'edge1-claude-' in installer and 'b159-claude-' not in installer
assert 'Agent Shell must be loopback-only' in installer
assert 'Needs approval' in installer
assert '89.126.' not in installer + unit + site
print('Edge1 Claude connector asset validation passed.')
