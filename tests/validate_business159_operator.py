#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'tools/mcp/business159-live-shell/src/index.js').read_text(encoding='utf-8')
README = (ROOT / 'tools/mcp/business159-live-shell/README.md').read_text(encoding='utf-8')

READ_ONLY = [
    'business159.identity', 'business159.health', 'business159.snapshot',
    'business159.inventory', 'business159.resources', 'business159.php_status',
    'business159.web_status', 'business159.domain_state', 'business159.tls_status',
    'business159.cron_state', 'business159.git_state', 'business159.mail_state',
    'business159.deployment_status', 'business159.edge1_bridge_status',
    'business159.config_digest', 'business159.logs_summary',
]
GUARDED = [
    'business159_connection_test', 'business159_inspect', 'business159_deploy',
    'business159_fs_stage', 'business159_fs_status', 'business159_fs_diff',
    'business159_fs_approve', 'business159_fs_apply', 'business159_fs_rollback',
    'business159_exec',
]

for name in READ_ONLY + GUARDED:
    assert f"registerTool('{name}'" in SOURCE, f'missing tool: {name}'

assert "StrictHostKeyChecking=yes" in SOURCE
assert "BatchMode=yes" in SOURCE
assert "BUSINESS159_ALLOW_DEPLOY === '1'" in SOURCE
assert "BUSINESS159_ALLOW_FILESYSTEM === '1'" in SOURCE
assert "BUSINESS159_ENABLE_RAW_SHELL === '1'" in SOURCE
assert "expected_principal" in SOURCE and "principal_mismatch" in SOURCE
assert "expected_host" in SOURCE and "host_mismatch" in SOURCE
assert "contentLooksSecret" in SOURCE
assert "forbiddenTarget" in SOURCE
assert "expectedCommit is required" in SOURCE
assert "deploy_checkout_dirty" in SOURCE
assert "post_deploy_http=ok" in SOURCE
assert "stage -> status/diff -> approve -> apply -> verify -> rollback -> audit" in README

# Ordinary read-only status tools must remain parameterless.
for name in READ_ONLY:
    match = re.search(rf"registerTool\('{re.escape(name)}',\s*\{{(.*?)\}}\s*,", SOURCE, re.S)
    assert match, f'cannot inspect schema: {name}'
    assert 'inputSchema: z.object({})' in match.group(0), f'{name} is not parameterless'

# Disallow obvious weakening of the SSH and raw-shell boundaries.
assert "StrictHostKeyChecking=no" not in SOURCE
assert "UserKnownHostsFile=/dev/null" not in SOURCE
assert "ENABLE_RAW_SHELL = true" not in SOURCE

print(f'Business159 operator contract validation passed ({len(READ_ONLY)} read-only tools, {len(GUARDED)} guarded tools).')
