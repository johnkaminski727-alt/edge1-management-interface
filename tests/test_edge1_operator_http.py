import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "server" / "edge1_operator_http.py"
SPEC = importlib.util.spec_from_file_location("edge1_operator_http", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeOperator:
    def handle(self, request):
        if request.method == "tools/list":
            return type("Resp", (), {"result": {"tools": [{"name": "edge1.health", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}]}})()
        if request.method == "tools/call":
            if request.payload["name"] == "edge1.health" and request.payload["arguments"] == {}:
                result = {"tool": "edge1.health", "status": "ok", "payload": {"status": "ok"}}
            else:
                result = {"tool": request.payload["name"], "status": "error", "payload": {"message": "unknown_tool"}}
            return type("Resp", (), {"result": result})()
        raise AssertionError(request.method)


def request(method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    return payload


def test_loopback_only():
    assert MODULE._is_loopback_host("127.0.0.1")
    assert MODULE._is_loopback_host("::1")
    assert not MODULE._is_loopback_host("0.0.0.0")
    with pytest.raises(MODULE.TransportConfigError):
        MODULE.serve(FakeOperator(), host="0.0.0.0", port=8098, token="x" * 32, allowed_origins=frozenset())


def test_token_file_requires_private_permissions(tmp_path):
    token = tmp_path / "token"
    token.write_text("x" * 40, encoding="utf-8")
    token.chmod(0o600)
    assert MODULE.load_bearer_token(token) == "x" * 40
    token.chmod(0o640)
    with pytest.raises(MODULE.TransportConfigError, match="group/other"):
        MODULE.load_bearer_token(token)


def test_allowed_origins_fail_closed_and_reject_insecure_remote_http():
    assert MODULE.allowed_origins_from_env(None) == frozenset()
    assert MODULE.allowed_origins_from_env("https://chatgpt.com") == frozenset({"https://chatgpt.com"})
    with pytest.raises(MODULE.TransportConfigError):
        MODULE.allowed_origins_from_env("http://example.com")


def test_initialize_declares_tools_and_stable_protocol():
    status, body = MODULE.dispatch_mcp(FakeOperator(), request("initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}
    }))
    assert status == 200
    assert body["result"]["protocolVersion"] == "2025-11-25"
    assert body["result"]["capabilities"] == {"tools": {"listChanged": False}}


def test_tools_list_and_call_are_typed_only():
    status, listed = MODULE.dispatch_mcp(FakeOperator(), request("tools/list", {}))
    assert status == 200
    assert listed["result"]["tools"][0]["name"] == "edge1.health"
    status, called = MODULE.dispatch_mcp(FakeOperator(), request("tools/call", {"name": "edge1.health", "arguments": {}}))
    assert status == 200
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["payload"]["status"] == "ok"


def test_unknown_method_and_bad_params_fail_closed():
    status, body = MODULE.dispatch_mcp(FakeOperator(), request("edge1.exec", {}))
    assert body["error"]["code"] == -32601
    status, body = MODULE.dispatch_mcp(FakeOperator(), request("tools/call", {"name": "edge1.health", "arguments": {}, "command": "id"}))
    assert body["error"]["code"] == -32602


def test_initialized_notification_is_accepted_without_body():
    status, body = MODULE.dispatch_mcp(FakeOperator(), request("notifications/initialized", {}, request_id=None))
    assert status == 202
    assert body is None


def test_source_has_no_generic_execution_or_public_default():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'DEFAULT_HOST = "127.0.0.1"' in source
    forbidden = ("subprocess", "os.system", "shell=True", "edge1.exec", "0.0.0.0\"", "eval(", "exec(")
    for token in forbidden:
        assert token not in source


def test_http_boundary_requires_bearer_and_rejects_unapproved_origin():
    import http.client
    import threading

    token = "t" * 40
    server = MODULE.ThreadingHTTPServer(("127.0.0.1", 0), MODULE.make_handler(FakeOperator(), token, frozenset({"https://chatgpt.com"})))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    body = json.dumps(request("ping", {}))
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("POST", "/mcp", body=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
        assert conn.getresponse().status == 401
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("POST", "/mcp", body=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "Origin": "https://evil.example",
        })
        assert conn.getresponse().status == 403
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("POST", "/mcp", body=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "Origin": "https://chatgpt.com",
        })
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["result"] == {}
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
