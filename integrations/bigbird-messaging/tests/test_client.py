from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from integrations.bigbird_messaging.client import MessagingGatewayClient, MessagingGatewayError


class Handler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def do_GET(self) -> None:
        self.requests.append(
            {
                "method": "GET",
                "path": self.path,
                "management_token": self.headers.get("X-WWCX-Management-Token"),
                "control_token": self.headers.get("X-WWCX-Control-Token"),
            }
        )
        self._json(200, {"status": "ready", "paused": False})

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.requests.append(
            {
                "method": "POST",
                "path": self.path,
                "management_token": self.headers.get("X-WWCX-Management-Token"),
                "control_token": self.headers.get("X-WWCX-Control-Token"),
                "payload": payload,
            }
        )
        self._json(200, {"status": "ok", **payload})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        Handler.requests.clear()

    def test_status_uses_read_credential(self) -> None:
        result = MessagingGatewayClient(self.base_url, "read-secret").status()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(Handler.requests[0]["management_token"], "read-secret")
        self.assertIsNone(Handler.requests[0]["control_token"])

    def test_control_requires_separate_credential(self) -> None:
        client = MessagingGatewayClient(self.base_url, "read-secret")
        with self.assertRaises(MessagingGatewayError):
            client.pause(actor="bigbird", reason="maintenance")

    def test_pause_includes_actor_and_reason(self) -> None:
        client = MessagingGatewayClient(self.base_url, "read-secret", "control-secret")
        result = client.pause(actor="bigbird:user-7", reason="maintenance window")
        self.assertEqual(result["action"], "pause")
        self.assertEqual(Handler.requests[0]["control_token"], "control-secret")
        self.assertIsNone(Handler.requests[0]["management_token"])
        self.assertEqual(Handler.requests[0]["payload"]["actor"], "bigbird:user-7")


if __name__ == "__main__":
    unittest.main()
