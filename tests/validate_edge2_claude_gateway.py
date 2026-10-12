#!/usr/bin/env python3
"""Static checks for the Edge2 Agent Shell Claude connector deployment assets (Caddy)."""
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy/edge2-claude-gateway'

installer = (DEPLOY / 'install-edge2-claude-gateway.sh').read_text(encoding='utf-8')
unit = (DEPLOY / 'edge2-claude-gateway.service').read_text(encoding='utf-8')
site = (DEPLOY / 'mcp-edge2.ww.cx.caddy').read_text(encoding='utf-8')
subprocess.run(['sh', '-n', str(DEPLOY / 'install-edge2-claude-gateway.sh')], check=True)

# Upstream is the loopback Edge2 Agent Shell; the gateway itself stays on loopback and unprivileged.
assert 'Environment=B159_GATEWAY_UPSTREAM_URL=http://127.0.0.1:8114/mcp' in unit
assert 'Environment=B159_GATEWAY_ISSUER=https://mcp-edge2.ww.cx' in unit
assert 'Environment=B159_GATEWAY_HOST=127.0.0.1' in unit and 'Environment=B159_GATEWAY_PORT=8151' in unit
assert 'Environment=B159_GATEWAY_TOOLS=*' in unit and 'Environment=B159_GATEWAY_REFRESH_TTL=604800' in unit
assert 'User=edge2-claude-gw' in unit and 'User=root' not in unit
assert 'edge1' not in unit.lower()
for directive in ('NoNewPrivileges=true', 'ProtectSystem=strict', 'ProtectHome=true', 'CapabilityBoundingSet=', 'MemoryDenyWriteExecute=true'):
    assert directive in unit, directive

# Caddy block: managed markers, Anthropic-only /mcp and /token, real client address, 404 elsewhere.
assert site.startswith('# BEGIN edge2-claude-gateway') and site.rstrip().endswith('# END edge2-claude-gateway')
assert '@not_anthropic not remote_ip 160.79.104.0/21' in site
assert site.count('respond @not_anthropic 403') == 2
assert site.count('reverse_proxy 127.0.0.1:8151') == 4
assert site.count('header_up X-Forwarded-For {remote_host}') == 4
assert 'respond 404' in site and 'mcp-edge2.ww.cx {' in site

# Installer: dry run default, validates before writing, backs up, restores on failure, own identity.
assert 'MODE=dry-run' in installer
assert 'caddy validate --config' in installer and 'pre-edge2-claude-' in installer
assert 'previous Caddyfile restored' in installer
assert 'UPSTREAM_TOKEN_SRC=/etc/edge2-agent-shell/mcp-token' in installer
assert 'edge2-claude-' in installer and 'b159-claude-' not in installer and 'edge1-claude-' not in installer
assert 'Agent Shell must be loopback-only' in installer and 'Needs approval' in installer
assert '172.105.' not in installer + unit + site

# When Caddy is available, the block must validate inside a Caddyfile shaped like Edge2's.
if shutil.which('caddy'):
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / 'Caddyfile'
        cfg.write_text('edge2.ww.cx {\n\trespond "ok"\n}\n\n' + site.replace('/var/log/caddy/', tmp + '/'), encoding='utf-8')
        subprocess.run(['caddy', 'validate', '--config', str(cfg), '--adapter', 'caddyfile'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('Edge2 Claude connector asset validation passed.')
