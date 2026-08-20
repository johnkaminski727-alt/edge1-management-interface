#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy/business159-tunnel'

required = [
    'tunnel-client.yaml', 'business159-live-shell.sh', 'ssh',
    'business159-secure-mcp-tunnel.sh', 'business159-secure-mcp-tunnel.service',
    'install-business159-secure-mcp-tunnel.sh',
    'validate-business159-secure-mcp-tunnel.sh',
    'verify-business159-secure-mcp-tunnel.sh',
    'set-business159-filesystem-smoke-mode.sh',
]
for name in required:
    assert (DEPLOY / name).is_file(), f'missing asset: {name}'

config = (DEPLOY / 'tunnel-client.yaml').read_text(encoding='utf-8')
runtime = (DEPLOY / 'business159-secure-mcp-tunnel.sh').read_text(encoding='utf-8')
unit = (DEPLOY / 'business159-secure-mcp-tunnel.service').read_text(encoding='utf-8')
installer = (DEPLOY / 'install-business159-secure-mcp-tunnel.sh').read_text(encoding='utf-8')
validator = (DEPLOY / 'validate-business159-secure-mcp-tunnel.sh').read_text(encoding='utf-8')
smoke_helper = (DEPLOY / 'set-business159-filesystem-smoke-mode.sh').read_text(encoding='utf-8')
ssh_wrapper = (DEPLOY / 'ssh').read_text(encoding='utf-8')
runbook = (ROOT / 'docs/business159-operator/persistent-secure-mcp-tunnel.md').read_text(encoding='utf-8')

assert 'api_key: file:/etc/business159-tunnel/runtime-api-key' in config
assert 'listen_addr: 127.0.0.1:0' in config
assert 'server_urls:' not in config and 'commands:' not in config
assert '--mcp.command "$MCP_COMMAND"' in runtime
assert 'business159-live-shell.sh' in runtime

assert 'User=business159-operator' in unit
assert 'Restart=on-failure' in unit
assert 'WantedBy=multi-user.target' in unit
assert 'NoNewPrivileges=true' in unit
assert 'CapabilityBoundingSet=' in unit
assert 'AmbientCapabilities=' in unit
assert 'ProtectSystem=strict' in unit
assert 'Environment=BUSINESS159_NODE_BIN=/opt/node-v24.18.0-linux-x64/bin/node' in unit
assert 'Environment=NODE_OPTIONS=--jitless' in unit
assert 'EnvironmentFile=-/etc/business159-operator/runtime-policy' in unit
assert '/opt/node-v24.18.0-linux-x64' in unit

assert 'systemctl enable' not in installer
assert 'systemctl start' not in installer
assert 'edge1-secure-mcp-tunnel.service' in installer
assert 'bigbird-ai-tunnel.service' in installer
assert '--mcp.command' in installer
assert 'useradd --system' in installer
assert 'NODE_BIN=${BUSINESS159_NODE_BIN:-/usr/bin/node}' in installer
assert '"$NODE_BIN" -e' in installer
assert 'set-business159-filesystem-smoke-mode.sh' in installer
assert 'runtime policy may not enable Business159 deployment apply' in installer
assert 'runtime policy may not enable Business159 raw shell' in installer

assert 'StrictHostKeyChecking=yes' in validator
assert 'BatchMode=yes' in validator
assert 'business159.web-hosting.com' in validator
assert 'wwcxjywl' in validator
assert 'doctor' in validator
assert '/etc/business159-operator/runtime-policy' in validator
assert 'runtime policy may not enable Business159 deployment apply' in validator
assert 'runtime policy may not enable Business159 raw shell' in validator

assert 'POLICY_DIR=/etc/business159-operator' in smoke_helper
assert 'BUSINESS159_ALLOW_DEPLOY=0' in smoke_helper
assert 'BUSINESS159_ALLOW_FILESYSTEM=$filesystem_value' in smoke_helper
assert 'BUSINESS159_ENABLE_RAW_SHELL=0' in smoke_helper
assert 'BUSINESS159_ALLOW_DEPLOY=1' not in smoke_helper
assert 'BUSINESS159_ENABLE_RAW_SHELL=1' not in smoke_helper
assert 'write_policy 1' in smoke_helper
assert 'write_policy 0' in smoke_helper
assert 'root:$SERVICE_USER' in smoke_helper
assert 'chmod 0640 "$tmp"' in smoke_helper

assert 'UserKnownHostsFile=/etc/business159-operator/known_hosts' in ssh_wrapper
assert 'StrictHostKeyChecking=no' not in ssh_wrapper
assert 'UserKnownHostsFile=/dev/null' not in ssh_wrapper

assert 'Business159 Operator' in runbook
assert 'systemctl restart business159-secure-mcp-tunnel.service' in runbook
assert 'business159_connection_test' in runbook
assert 'business159_fs_stage' in runbook
assert 'set-business159-filesystem-smoke-mode.sh enable' in runbook
assert 'set-business159-filesystem-smoke-mode.sh disable' in runbook
assert 'Do not change DNS' in runbook

print('Business159 persistent tunnel asset validation passed.')
