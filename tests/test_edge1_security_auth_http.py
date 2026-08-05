from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from server.edge1_operations_client import OperationsClientError, OperationsClientTimeout, OperationsResult
from server.edge1_security_auth_core import AssertionIdentity, AuthenticationError, AuthorizationError, SessionContext, hash_secret
from server.edge1_security_auth_http import Edge1SecurityAuthHttpAdapter, HttpAdapterConfig, HttpRequest
from server.edge1_security_auth_store import SQLiteGatewayStore


def config_mapping(**overrides):
    value = {
        "contract": "wwcx.edge1-security-auth-http.v1",
        "status": "staged_disabled",
        "enabled": True,
        "deployment_authorized": True,
        "live_route_authorized": False,
        "allowed_host": "edge1.ww.cx",
        "business159_origin": "https://business159.ww.cx",
        "same_origin": "https://edge1.ww.cx",
        "routes": {
            "health": "/healthz",
            "exchange": "/edge1-ops/session/exchange",
            "session": "/edge1-ops/session",
            "logout": "/edge1-ops/session/logout",
            "validate": "/edge1-ops/api/v1/security/validate",
            "redirect_after_exchange": "/edge1-ops/security/",
        },
        "cookies": {
            "session_name": "__Secure-wwcx_edge1_ops_session",
            "csrf_name": "__Secure-wwcx_edge1_ops_csrf",
            "path": "/edge1-ops/",
            "secure": True,
            "http_only_session": True,
            "same_site": "Strict",
            "persistent": False,
        },
        "request_limits": {
            "maximum_body_bytes": 20000,
            "exchange_requests": 10,
            "exchange_window_seconds": 600,
            "session_requests": 120,
            "session_window_seconds": 60,
            "action_requests": 6,
            "action_window_seconds": 60,
            "logout_requests": 20,
            "logout_window_seconds": 600,
            "action_inflight_timeout_seconds": 60,
            "action_cooldown_seconds": 3,
        },
        "operations_api": {
            "origin": "http://127.0.0.1:8097",
            "secret_path": "/etc/edge1-operations-api.secret",
            "timeout_seconds": 15,
            "allowed_action": "security.validate_config",
        },
        "boundaries": {
            "loopback_only": True,
            "trusted_proxy_required": True,
            "csrf_required_for_authenticated_post": True,
            "raw_assertion_storage": False,
            "raw_session_storage": False,
            "raw_operations_output_to_browser": False,
            "mutation_actions_enabled": False,
        },
    }
    value.update(overrides)
    return value


class Clock:
    def __init__(self, value=1800000000): self.value=value
    def __call__(self): return self.value


class FakeGateway:
    def __init__(self, store, clock):
        self.store=store; self.clock=clock; self.correlations=[]; self.counter=0
    def exchange_assertion(self, assertion, request_id):
        if assertion != "valid-assertion": raise AuthenticationError("denied")
        self.counter += 1
        token=("s" * 42) + str(self.counter)
        now=int(self.clock())
        identity=AssertionIdentity("wwcx-user-42","Test Administrator","admin",frozenset({"edge1.security.read","edge1.security.validate"}),now,now+90,"j"*64)
        session_hash=hash_secret(token)
        self.store.create_session(session_hash=session_hash,identity=identity,issued_at=now,expires_at=now+300,authentication_event_id="edge1-auth-login")
        return token, SessionContext(identity.subject,identity.display_name,identity.source_role,identity.scopes,now,now+300,now,"edge1-auth-login",session_hash)
    def authenticate_session(self, token, request_id):
        context, reason=self.store.resolve_session(hash_secret(token),int(self.clock()),180)
        if context is None: raise AuthenticationError(reason)
        return context
    def authorize_action(self, token, action_id, request_id):
        context=self.authenticate_session(token,request_id)
        if action_id != "security.validate_config": raise AuthorizationError("unknown")
        if "edge1.security.validate" not in context.scopes: raise AuthorizationError("scope")
        return context
    def correlate_operations_event(self, token, *, action_id, operations_event_id, request_id):
        self.authorize_action(token,action_id,request_id)
        self.correlations.append((operations_event_id,request_id))
        return "edge1-auth-correlation"
    def logout(self, token, request_id):
        self.store.revoke_session(hash_secret(token),int(self.clock()))


class FakeOperations:
    def __init__(self): self.mode="success"; self.calls=[]
    def run(self, action_id, subject):
        self.calls.append((action_id,subject))
        if self.mode=="timeout": raise OperationsClientTimeout("timeout")
        if self.mode=="error": raise OperationsClientError("error")
        if self.mode=="failed": return OperationsResult("ops-event-2",action_id,"failed","The configuration needs attention. No running service settings were changed.",12,1)
        return OperationsResult("ops-event-1",action_id,"succeeded","The security configuration passed validation.",11,0)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.clock=Clock()
        self.store=SQLiteGatewayStore(Path(self.temp.name)/"state.sqlite3")
        self.gateway=FakeGateway(self.store,self.clock)
        self.operations=FakeOperations()
        self.config=HttpAdapterConfig.from_mapping(config_mapping())
        self.adapter=Edge1SecurityAuthHttpAdapter(self.config,self.gateway,self.operations,now=self.clock)
    def tearDown(self): self.temp.cleanup()
    def request(self, method, path, *, headers=None, body=b"", remote="127.0.0.1", scheme="https", host="edge1.ww.cx"):
        return self.adapter.handle(HttpRequest(method,path,headers or {},body,remote,scheme,host))
    def exchange(self):
        body=urlencode({"assertion":"valid-assertion","request_id":"b159-0123456789abcdef0123456789abcdef"}).encode()
        response=self.request("POST","/edge1-ops/session/exchange",headers={"Origin":"https://business159.ww.cx","Content-Type":"application/x-www-form-urlencoded"},body=body)
        self.assertEqual(response.status,303)
        cookies=[v for k,v in response.headers if k=="Set-Cookie"]
        self.assertEqual(len(cookies),2)
        session=cookies[0].split(";",1)[0]
        csrf=cookies[1].split(";",1)[0]
        return session,csrf,response
    def test_config_rejects_live_route_or_mutations(self):
        bad=config_mapping(live_route_authorized=True)
        self.assertTrue(HttpAdapterConfig.from_mapping(bad).live_route_authorized)
        bad=config_mapping();bad["boundaries"]["mutation_actions_enabled"]=True
        with self.assertRaises(ValueError): HttpAdapterConfig.from_mapping(bad)
    def test_boundary_and_method_statuses(self):
        self.assertEqual(self.request("GET","/missing").status,404)
        self.assertEqual(self.request("GET","/edge1-ops/session/exchange").status,405)
        self.assertEqual(self.request("GET","/healthz",remote="203.0.113.5").status,403)
        self.assertEqual(self.request("GET","/healthz",scheme="http").status,403)
        self.assertEqual(self.request("GET","/healthz").status,200)
    def test_exchange_requires_business159_origin(self):
        body=urlencode({"assertion":"valid-assertion","request_id":"b159-0123456789abcdef0123456789abcdef"}).encode()
        response=self.request("POST","/edge1-ops/session/exchange",headers={"Origin":"https://evil.example","Content-Type":"application/x-www-form-urlencoded"},body=body)
        self.assertEqual(response.status,403)
    def test_exchange_session_and_cookie_policy(self):
        session,csrf,response=self.exchange()
        text="\n".join(v for k,v in response.headers if k=="Set-Cookie")
        self.assertIn("Secure; HttpOnly; SameSite=Strict",text)
        self.assertNotIn("valid-assertion",response.body.decode())
        status=self.request("GET","/edge1-ops/session",headers={"Cookie":session+"; "+csrf})
        self.assertEqual(status.status,200)
        payload=json.loads(status.body)
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["scopes"],["edge1.security.read","edge1.security.validate"])
        self.assertNotIn("subject",payload)
    def test_session_requires_cookie(self):
        self.assertEqual(self.request("GET","/edge1-ops/session").status,401)
    def test_validate_requires_same_origin_and_csrf(self):
        session,csrf,_=self.exchange()
        headers={"Cookie":session+"; "+csrf,"Content-Type":"application/json"}
        self.assertEqual(self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}").status,403)
        headers["Origin"]="https://edge1.ww.cx"
        self.assertEqual(self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}").status,403)
    def test_validate_success_correlates_event_and_redacts_output(self):
        session,csrf,_=self.exchange();csrf_value=csrf.split("=",1)[1]
        headers={"Cookie":session+"; "+csrf,"Content-Type":"application/json","Origin":"https://edge1.ww.cx","X-WWCX-CSRF":csrf_value}
        response=self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}")
        self.assertEqual(response.status,200)
        payload=json.loads(response.body)
        self.assertEqual(payload["event_id"],"ops-event-1")
        self.assertEqual(payload["status"],"succeeded")
        self.assertNotIn("stdout",payload);self.assertNotIn("stderr",payload)
        self.assertEqual(self.operations.calls,[("security.validate_config","wwcx-user-42")])
        self.assertEqual(self.gateway.correlations[0][0],"ops-event-1")
    def test_validate_failure_and_cooldown_are_conflicts(self):
        session,csrf,_=self.exchange();csrf_value=csrf.split("=",1)[1]
        headers={"Cookie":session+"; "+csrf,"Content-Type":"application/json","Origin":"https://edge1.ww.cx","X-WWCX-CSRF":csrf_value}
        self.operations.mode="failed"
        first=self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}")
        second=self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}")
        self.assertEqual(first.status,409);self.assertEqual(second.status,409)
        self.assertEqual(json.loads(second.body)["error"],"request_already_in_progress")
    def test_validate_timeout_is_gateway_timeout(self):
        session,csrf,_=self.exchange();csrf_value=csrf.split("=",1)[1]
        headers={"Cookie":session+"; "+csrf,"Content-Type":"application/json","Origin":"https://edge1.ww.cx","X-WWCX-CSRF":csrf_value}
        self.operations.mode="timeout"
        self.assertEqual(self.request("POST","/edge1-ops/api/v1/security/validate",headers=headers,body=b"{}").status,504)
    def test_rate_limit_is_persistent_store_backed(self):
        value=config_mapping();value["request_limits"]["exchange_requests"]=1
        adapter=Edge1SecurityAuthHttpAdapter(HttpAdapterConfig.from_mapping(value),self.gateway,self.operations,now=self.clock)
        body=urlencode({"assertion":"valid-assertion","request_id":"b159-0123456789abcdef0123456789abcdef"}).encode()
        request=HttpRequest("POST","/edge1-ops/session/exchange",{"Origin":"https://business159.ww.cx","Content-Type":"application/x-www-form-urlencoded"},body)
        self.assertEqual(adapter.handle(request).status,303)
        self.assertEqual(adapter.handle(request).status,429)
    def test_logout_requires_csrf_and_revokes_session(self):
        session,csrf,_=self.exchange();csrf_value=csrf.split("=",1)[1]
        headers={"Cookie":session+"; "+csrf,"Origin":"https://edge1.ww.cx","X-WWCX-CSRF":csrf_value}
        response=self.request("POST","/edge1-ops/session/logout",headers=headers)
        self.assertEqual(response.status,204)
        self.assertEqual(self.request("GET","/edge1-ops/session",headers={"Cookie":session+"; "+csrf}).status,401)

if __name__=="__main__": unittest.main()
