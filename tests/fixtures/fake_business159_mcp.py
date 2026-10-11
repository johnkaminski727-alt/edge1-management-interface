#!/usr/bin/env python3
"""Synthetic stdio MCP server standing in for business159-live-shell in tests."""
import json
import os
import sys

TOOLS = [
    'business159.identity', 'business159.health', 'business159_inspect', 'business159_deploy',
    'business159.mailbox_create', 'business159_fs_stage', 'business159_fs_apply', 'business159_exec',
]

for line in sys.stdin:
    msg = json.loads(line)
    if 'id' not in msg:
        continue
    method = msg.get('method')
    if method == 'initialize':
        result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'business159-live-shell', 'version': 'test'}}
    elif method == 'tools/list':
        result = {'tools': [{'name': n, 'inputSchema': {'type': 'object'}} for n in TOOLS]}
    elif method == 'tools/call':
        policy = {k: os.environ.get(k) for k in ('BUSINESS159_ALLOW_DEPLOY', 'BUSINESS159_ALLOW_FILESYSTEM', 'BUSINESS159_ENABLE_RAW_SHELL')}
        result = {'content': [{'type': 'text', 'text': json.dumps({'called': msg['params']['name'], 'policy': policy})}]}
    else:
        result = {}
    # Interleave a notification to prove the gateway ignores it.
    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/message', 'params': {'level': 'info'}}) + '\n')
    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': result}) + '\n')
    sys.stdout.flush()
