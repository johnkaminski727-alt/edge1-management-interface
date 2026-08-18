#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "private_ai_browser_worker.py"
SPEC = importlib.util.spec_from_file_location("private_ai_browser_worker", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)


class BrowserWorkerTests(unittest.TestCase):
    def test_queue_url_is_exact_https_wwcx_route(self) -> None:
        headers, nonce = worker.queue_headers(b"{}", "q" * 32, "worker-key", "https://ww.cx/api/bigbird-ai-worker.php")
        self.assertEqual(len(nonce), 32)
        self.assertEqual(headers["X-BB-Worker-Key-ID"], "worker-key")
        for bad in (
            "http://ww.cx/api/bigbird-ai-worker.php",
            "https://ww.cx:443/api/bigbird-ai-worker.php",
            "https://edge1.ww.cx/api/bigbird-ai-worker.php",
            "https://ww.cx/api/bigbird-ai-worker.php?next=x",
        ):
            with self.assertRaises(worker.WorkerError):
                worker.queue_headers(b"{}", "q" * 32, "worker-key", bad)

    def test_gateway_is_loopback_only(self) -> None:
        headers = worker.gateway_headers(b"{}", "g" * 32, "gateway-key", "http://127.0.0.1:8787/v1/chat")
        self.assertEqual(headers["X-BB-Key-Id"], "gateway-key")
        for bad in (
            "http://0.0.0.0:8787/v1/chat",
            "http://127.0.0.1:8788/v1/chat",
            "https://127.0.0.1:8787/v1/chat",
            "http://127.0.0.1:8787/v1/tools",
        ):
            with self.assertRaises(worker.WorkerError):
                worker.gateway_headers(b"{}", "g" * 32, "gateway-key", bad)

    def test_queue_response_signature_verification(self) -> None:
        secret = "s" * 32
        request_nonce = "a" * 32
        body = json.dumps({"status": "idle", "poll_after_ms": 2000}, separators=(",", ":")).encode()
        body_hash = hashlib.sha256(body).hexdigest()
        timestamp = "1800000000"
        canonical = f"200\n{timestamp}\n{request_nonce}\n{body_hash}"
        signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        result = worker.HttpResult(200, {
            "x-bb-response-timestamp": timestamp,
            "x-bb-response-body-sha256": body_hash,
            "x-bb-response-signature": signature,
        }, body)
        self.assertEqual(worker.verify_queue_response(result, request_nonce, secret)["status"], "idle")
        tampered = worker.HttpResult(200, result.headers, body + b" ")
        with self.assertRaises(worker.WorkerError):
            worker.verify_queue_response(tampered, request_nonce, secret)

    def test_secret_environment_names_are_fixed(self) -> None:
        self.assertEqual(worker.QUEUE_SECRET_ENV, "BB_BROWSER_WORKER_SECRET")
        self.assertEqual(worker.GATEWAY_SECRET_ENV, "BB_RELAY_SECRET")
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("argparse", source)
        self.assertNotIn("print(queue_secret", source)
        self.assertNotIn("print(gateway_secret", source)


if __name__ == "__main__":
    unittest.main()
