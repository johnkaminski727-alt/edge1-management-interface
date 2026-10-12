"""Synthetic Streamable HTTP MCP server standing in for the Edge1 Agent Shell in tests."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = ['edge1_agent_identity', 'edge1_agent_exec', 'edge1_agent_file_read', 'edge1_agent_file_write', 'edge1_agent_service']


def make_server(token: str) -> ThreadingHTTPServer:
    seen: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.headers.get('Authorization') != f'Bearer {token}':
                self.send_response(401)
                self.end_headers()
                return
            if self.headers.get('Origin'):
                self.send_response(403)
                self.end_headers()
                return
            msg = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)))
            seen.append({'msg': msg, 'session': self.headers.get('Mcp-Session-Id')})
            if 'id' not in msg:
                self.send_response(202)
                self.end_headers()
                return
            method = msg.get('method')
            if method == 'initialize':
                result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'wwcx-edge1-agent-shell', 'version': 'test'}}
            elif method == 'tools/list':
                result = {'tools': [{'name': n, 'inputSchema': {'type': 'object'}} for n in TOOLS]}
            elif method == 'tools/call':
                result = {'content': [{'type': 'text', 'text': json.dumps({'called': msg['params']['name'], 'args': msg['params'].get('arguments')})}]}
            else:
                result = {}
            body = json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': result})
            self.send_response(200)
            if method == 'initialize':
                self.send_header('Mcp-Session-Id', 'upstream-session-1')
            if method == 'tools/call':
                # Exercise the SSE path, with a notification before the response.
                note = json.dumps({'jsonrpc': '2.0', 'method': 'notifications/progress', 'params': {}})
                payload = f'event: message\ndata: {note}\n\nevent: message\ndata: {body}\n\n'.encode()
                self.send_header('Content-Type', 'text/event-stream')
            else:
                payload = body.encode()
                self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_DELETE(self):
            seen.append({'delete': self.headers.get('Mcp-Session-Id')})
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.seen = seen  # type: ignore[attr-defined]
    return server
