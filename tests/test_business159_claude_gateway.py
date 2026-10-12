#!/usr/bin/env python3
"""End-to-end tests for the Business159 Claude connector gateway (synthetic secrets only)."""
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))

import business159_claude_gateway as gwmod  # noqa: E402

FAKE_CHILD = ROOT / 'tests/fixtures/fake_business159_mcp.py'
ANTHROPIC_IP = '160.79.105.10'
OTHER_IP = '203.0.113.9'
REDIRECT = 'https://claude.ai/api/mcp/auth_callback'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class TotpTests(unittest.TestCase):
    def test_rfc6238_vector(self):
        secret = base64.b32encode(b'12345678901234567890').decode()
        self.assertEqual(gwmod.totp_code(secret, 59 // 30), '287082')
        self.assertEqual(gwmod.totp_code(secret, 1111111109 // 30), '081804')

    def test_policy(self):
        cfg = gwmod.Config()
        self.assertIsNone(gwmod.tool_policy(cfg, {'name': 'business159.health'}))
        self.assertIsNone(gwmod.tool_policy(cfg, {'name': 'business159_deploy', 'arguments': {}}))
        self.assertIsNotNone(gwmod.tool_policy(cfg, {'name': 'business159_deploy', 'arguments': {'dryRun': False}}))
        self.assertIsNotNone(gwmod.tool_policy(cfg, {'name': 'business159_exec'}))
        self.assertIsNotNone(gwmod.tool_policy(cfg, {'name': 'business159.mailbox_create'}))
        self.assertIsNotNone(gwmod.tool_policy(cfg, {'name': 'business159_fs_apply'}))

    def test_access_modes(self):
        from unittest import mock
        def load(access=None):
            env = {k: v for k, v in os.environ.items() if not k.startswith('B159_GATEWAY_')}
            if access is not None:
                env['B159_GATEWAY_ACCESS'] = access
            with mock.patch.dict(os.environ, env, clear=True):
                return gwmod.Config.from_env()
        self.assertFalse(load().full_access)
        with self.assertRaises(ValueError):
            load('root')
        cfg = load('full')
        self.assertTrue(cfg.full_access)
        self.assertIsNone(cfg.tools)
        self.assertIsNone(gwmod.tool_policy(cfg, {'name': 'business159_exec'}))
        self.assertIsNone(gwmod.tool_policy(cfg, {'name': 'business159_deploy', 'arguments': {'dryRun': False}}))
        self.assertEqual(set(gwmod.FULL_ACCESS_CHILD_POLICY_ENV.values()), {'1'})
        self.assertEqual(set(gwmod.FULL_ACCESS_CHILD_POLICY_ENV), set(gwmod.CHILD_POLICY_ENV))

    def test_stage1_allowlist_matches_live_shell_source(self):
        source = (ROOT / 'tools/mcp/business159-live-shell/src/index.js').read_text(encoding='utf-8')
        for name in gwmod.STAGE1_TOOLS:
            self.assertIn(f"registerTool('{name}'", source, name)
        for name in ('business159_exec', 'business159_fs_apply', 'business159.mailbox_create'):
            self.assertNotIn(name, gwmod.STAGE1_TOOLS)


class GatewayFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.totp_secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        self.client_id = 'b159-test-client'
        self.client_secret = secrets.token_urlsafe(24)
        etc = base / 'etc'
        etc.mkdir()
        (etc / 'client-id').write_text(self.client_id)
        (etc / 'client-secret.sha256').write_text(gwmod.sha256_hex(self.client_secret))
        (etc / 'totp-secret').write_text(self.totp_secret)
        cfg = gwmod.Config(
            issuer='https://mcp-b159.example.test', port=0, etc_dir=etc, state_dir=base / 'state',
            audit_log=base / 'audit.jsonl', child_command=(sys.executable, str(FAKE_CHILD)),
        )
        self.cfg = cfg
        self.gw = gwmod.Gateway(cfg)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), gwmod.make_handler(self.gw))
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.gw.pool.close_all()
        self.tmp.cleanup()

    # -- helpers --
    def call(self, method, path, body=None, headers=None, ip=ANTHROPIC_IP):
        data = body if isinstance(body, (bytes, type(None))) else body.encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'X-Forwarded-For': ip, **(headers or {})})
        try:
            with OPENER.open(req, timeout=20) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()

    def code_now(self, offset=0):
        return gwmod.totp_code(self.totp_secret, int(time.time() // 30) + offset)

    def authorize(self, code=None):
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        query = urllib.parse.urlencode({
            'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': REDIRECT,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'state': 'st-1',
            'resource': self.cfg.resource,
        })
        status, _, page = self.call('GET', '/authorize?' + query, ip=OTHER_IP)
        self.assertEqual(status, 200)
        pending = page.decode().split('name="pending" value="')[1].split('"')[0]
        form = urllib.parse.urlencode({'pending': pending, 'code': code or self.code_now()})
        status, headers, body = self.call('POST', '/authorize', form, {'Content-Type': 'application/x-www-form-urlencoded'}, ip=OTHER_IP)
        return status, headers, body, verifier, pending

    def tokens(self):
        status, headers, _, verifier, _ = self.authorize()
        self.assertEqual(status, 302, 'TOTP sign-in should redirect to Claude')
        location = urllib.parse.urlsplit(headers['Location'])
        self.assertEqual(f'{location.scheme}://{location.netloc}{location.path}', REDIRECT)
        params = dict(urllib.parse.parse_qsl(location.query))
        self.assertEqual(params['state'], 'st-1')
        form = urllib.parse.urlencode({
            'grant_type': 'authorization_code', 'code': params['code'], 'redirect_uri': REDIRECT,
            'client_id': self.client_id, 'client_secret': self.client_secret, 'code_verifier': verifier,
        })
        status, _, body = self.call('POST', '/token', form, {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def rpc(self, token, message, session=None, ip=ANTHROPIC_IP):
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        if session:
            headers['Mcp-Session-Id'] = session
        return self.call('POST', '/mcp', json.dumps(message), headers, ip=ip)

    # -- tests --
    def test_discovery_and_unauthenticated_mcp(self):
        status, _, body = self.call('GET', '/.well-known/oauth-authorization-server')
        meta = json.loads(body)
        self.assertEqual(meta['code_challenge_methods_supported'], ['S256'])
        self.assertNotIn('registration_endpoint', meta)
        status, headers, _ = self.rpc('nope', {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        self.assertEqual(status, 401)
        self.assertIn('resource_metadata=', headers['WWW-Authenticate'])

    def test_full_flow_allowlist_and_policy(self):
        token = self.tokens()['access_token']
        status, headers, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
        self.assertEqual(status, 200)
        session = headers['Mcp-Session-Id']
        status, _, _ = self.rpc(token, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session)
        self.assertEqual(status, 202)

        status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, session)
        names = {t['name'] for t in json.loads(body)['result']['tools']}
        self.assertEqual(names, {'business159.identity', 'business159.health', 'business159_inspect', 'business159_deploy'})

        status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'business159.health', 'arguments': {}}}, session)
        text = json.loads(json.loads(body)['result']['content'][0]['text'])
        self.assertEqual(text['called'], 'business159.health')
        self.assertEqual(set(text['policy'].values()), {'0'}, 'child mutation gates must be pinned to 0')

        for blocked in ({'name': 'business159_exec', 'arguments': {'command': 'id'}},
                        {'name': 'business159_fs_apply', 'arguments': {}},
                        {'name': 'business159_deploy', 'arguments': {'dryRun': False, 'expectedCommit': 'a' * 40}}):
            status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': blocked}, session)
            result = json.loads(body)['result']
            self.assertTrue(result['isError'], blocked)
            self.assertNotIn('called', result['content'][0]['text'])

        audit = [json.loads(l) for l in self.cfg.audit_log.read_text().splitlines()]
        events = [a['event'] for a in audit]
        self.assertIn('tool_call', events)
        self.assertEqual(events.count('tool_blocked'), 3)
        self.assertNotIn('id', json.dumps([a.get('args') for a in audit if a['event'] == 'tool_blocked' and a.get('tool') == 'business159_exec']).replace('"command"', ''))

        status, _, _ = self.call('DELETE', '/mcp', headers={'Authorization': f'Bearer {token}', 'Mcp-Session-Id': session})
        self.assertEqual(status, 204)
        status, _, _ = self.rpc(token, {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/list'}, session)
        self.assertEqual(status, 404)

    def test_ip_allowlist(self):
        token = self.tokens()['access_token']
        status, _, _ = self.rpc(token, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}, ip=OTHER_IP)
        self.assertEqual(status, 403)
        form = urllib.parse.urlencode({'grant_type': 'refresh_token', 'refresh_token': 'x', 'client_id': self.client_id, 'client_secret': self.client_secret})
        status, _, _ = self.call('POST', '/token', form, ip=OTHER_IP)
        self.assertEqual(status, 403)

    def test_totp_replay_wrong_code_and_lockout(self):
        code = self.code_now()
        status, *_ = self.authorize(code)
        self.assertEqual(status, 302)
        status, _, body, *_ = self.authorize(code)
        self.assertEqual(status, 200, 'a reused code must not be accepted')
        self.assertIn(b'not accepted', body)
        for _ in range(self.cfg.totp_lockout_failures):
            status, _, body, *_ = self.authorize('000000' if self.code_now() != '000000' else '111111')
        self.assertIn(b'locked', body)
        status, *_ = self.authorize(self.code_now(1))
        self.assertEqual(status, 200, 'valid code must be refused while locked out')

    def test_bad_client_secret_pkce_and_redirect(self):
        status, headers, _, verifier, _ = self.authorize()
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(headers['Location']).query))
        base = {'grant_type': 'authorization_code', 'code': params['code'], 'redirect_uri': REDIRECT, 'client_id': self.client_id}
        status, _, _ = self.call('POST', '/token', urllib.parse.urlencode({**base, 'client_secret': 'wrong', 'code_verifier': verifier}))
        self.assertEqual(status, 401)
        status, _, _ = self.call('POST', '/token', urllib.parse.urlencode({**base, 'client_secret': self.client_secret, 'code_verifier': 'wrong' * 10}))
        self.assertEqual(status, 400)
        query = urllib.parse.urlencode({'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': 'https://evil.example/cb',
                                        'code_challenge': 'x' * 43, 'code_challenge_method': 'S256'})
        status, _, _ = self.call('GET', '/authorize?' + query)
        self.assertEqual(status, 400)

    def test_refresh_rotation_and_kill_switch(self):
        tokens = self.tokens()
        form = {'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token'], 'client_id': self.client_id, 'client_secret': self.client_secret}
        status, _, body = self.call('POST', '/token', urllib.parse.urlencode(form))
        self.assertEqual(status, 200)
        self.assertNotEqual(json.loads(body)['refresh_token'], tokens['refresh_token'])
        status, _, _ = self.call('POST', '/token', urllib.parse.urlencode(form))
        self.assertEqual(status, 400, 'a rotated refresh token must not be reusable')
        (self.cfg.etc_dir / 'disabled').write_text('')
        status, _, _ = self.rpc(tokens['access_token'], {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        self.assertEqual(status, 503)
        state = json.loads((self.cfg.state_dir / 'state.json').read_text())
        self.assertNotIn(tokens['access_token'], json.dumps(state), 'tokens must be stored as digests only')


class HttpUpstreamTests(GatewayFlowTests):
    """Full Agent Shell connector mode: HTTP upstream, every tool allowed."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / 'tests/fixtures'))
        import fake_agent_shell_http
        self.upstream_token = secrets.token_urlsafe(16)
        self.upstream = fake_agent_shell_http.make_server(self.upstream_token)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        super().setUp()
        token_file = Path(self.tmp.name) / 'upstream-token'
        token_file.write_text(self.upstream_token)
        self.server.shutdown()
        self.server.server_close()
        self.cfg.upstream_url = f'http://127.0.0.1:{self.upstream.server_address[1]}/mcp'
        self.cfg.upstream_token_file = token_file
        self.cfg.tools = None
        self.cfg.resource_name = 'Edge1 Agent Shell (root)'
        self.cfg.refresh_ttl = 7 * 86400
        self.gw = gwmod.Gateway(self.cfg)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), gwmod.make_handler(self.gw))
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        super().tearDown()
        self.upstream.shutdown()
        self.upstream.server_close()

    def test_full_flow_allowlist_and_policy(self):
        token = self.tokens()['access_token']
        status, headers, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Mcp-Session-Id'], 'upstream-session-1')
        session = headers['Mcp-Session-Id']
        status, _, _ = self.rpc(token, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session)
        self.assertEqual(status, 202)
        status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, session)
        names = {t['name'] for t in json.loads(body)['result']['tools']}
        self.assertIn('edge1_agent_exec', names, 'full mode must list every upstream tool')
        status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                                           'params': {'name': 'edge1_agent_exec', 'arguments': {'command': 'cat /etc/secret-marker'}}}, session)
        self.assertEqual(status, 200)
        result = json.loads(json.loads(body)['result']['content'][0]['text'])
        self.assertEqual(result['called'], 'edge1_agent_exec')
        # Upstream received the gateway's bearer and the client's session, never the Claude token.
        forwarded = [s for s in self.upstream.seen if 'msg' in s]
        self.assertTrue(all(s['session'] in (None, 'upstream-session-1') for s in forwarded))
        audit = [json.loads(l) for l in self.cfg.audit_log.read_text().splitlines()]
        call = [a for a in audit if a['event'] == 'tool_call'][0]
        self.assertEqual(call['tool'], 'edge1_agent_exec')
        self.assertEqual(call['args'], ['command'])
        self.assertNotIn('secret-marker', self.cfg.audit_log.read_text(), 'command values must not be audited')
        status, _, _ = self.call('DELETE', '/mcp', headers={'Authorization': f'Bearer {token}', 'Mcp-Session-Id': session})
        self.assertEqual(status, 204)
        self.assertIn({'delete': 'upstream-session-1'}, self.upstream.seen)

    def test_stale_upstream_token_is_502_not_401(self):
        token = self.tokens()['access_token']
        self.gw.upstream_token = 'stale-token'
        status, _, body = self.rpc(token, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        self.assertEqual(status, 502)
        self.assertIn('re-run the installer', json.loads(body)['error']['message'])

    def test_upstream_must_be_loopback(self):
        self.cfg.upstream_url = 'http://203.0.113.9:8114/mcp'
        with self.assertRaises(SystemExit):
            gwmod.Gateway(self.cfg)

    def test_refresh_ttl_is_configurable(self):
        tokens = self.tokens()
        state = json.loads((self.cfg.state_dir / 'state.json').read_text())
        exp = list(state['refresh'].values())[0]['exp']
        self.assertLessEqual(exp - time.time(), 7 * 86400 + 5)

    def test_consent_page_names_the_connector(self):
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        query = urllib.parse.urlencode({'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': REDIRECT,
                                        'code_challenge': challenge, 'code_challenge_method': 'S256'})
        status, _, page = self.call('GET', '/authorize?' + query, ip=OTHER_IP)
        self.assertIn(b'Edge1 Agent Shell (root)', page)


if __name__ == '__main__':
    unittest.main()
