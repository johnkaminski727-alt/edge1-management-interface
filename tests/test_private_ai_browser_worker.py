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
SERVER_DIR = ROOT / "server"
MODULE_PATH = SERVER_DIR / "private_ai_browser_worker.py"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
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

    def test_mail_room_read_injects_bounded_evidence(self) -> None:
        original_urlopen = worker.urllib.request.urlopen
        original_env = dict(worker.os.environ)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, _limit):
                return json.dumps({
                    "contract": "wwcx.ava-mail-room-read.v1", "folder": "inbox", "messages": [{
                        "message_id": "<m@test>", "thread_id": "t", "sender": "sender@example.test",
                        "recipients": ["john@ww.cx"], "subject": "Please review", "occurred_at": "2026-10-07T10:00:00Z",
                        "direction": "inbound", "is_read": False, "archived": False, "body_excerpt": "Action item text",
                    }]
                }).encode()
        captured = []
        def fake_urlopen(req, timeout=0):
            captured.append(req)
            return Response()
        worker.urllib.request.urlopen = fake_urlopen
        worker.os.environ[worker.MAIL_READ_KEY_ENV] = "r" * 48
        try:
            context, sources, warning = worker.mail_room_read({"include_mail": True, "routing_message": "Triage the inbox"})
        finally:
            worker.urllib.request.urlopen = original_urlopen
            worker.os.environ.clear(); worker.os.environ.update(original_env)
        self.assertIn("Action item text", context)
        self.assertEqual(sources[0]["system"], "Mail Room")
        self.assertIsNone(warning)
        self.assertEqual(captured[0].headers.get("X-ava-mail-read-key"), "r" * 48)

    def test_progress_is_optional_for_old_queue(self) -> None:
        original = worker.queue_call
        worker.queue_call = lambda *args, **kwargs: (_ for _ in ()).throw(worker.WorkerError("queue returned HTTP 400"))
        try:
            self.assertFalse(worker.publish_progress("a" * 32, {"phase": "planning"}, "q" * 32, "worker-key"))
        finally:
            worker.queue_call = original


    def test_worker_uses_controller_ui_effect_sanitizer(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("sanitize_gateway_result", source)
        self.assertIn(
            "result = sanitize_gateway_result(result)",
            source,
        )



    def test_physical_dispatch_uses_sanitized_fixed_catalogue(self) -> None:
        original = worker.submit_physical_effect
        calls = []

        def fake_submit(request_id, catalogue_effect):
            calls.append((request_id, catalogue_effect))
            return {
                "version": 1,
                "request_id": request_id,
                "catalogue_effect": catalogue_effect,
                "disposition": "disabled",
            }

        worker.submit_physical_effect = fake_submit
        try:
            result = {
                "ui_effects": [
                    "donkey_easter_egg",
                    "cat_easter_egg",
                ]
            }
            outcomes = worker.dispatch_physical_effects(
                "request-worker-effect-0001",
                result,
            )
        finally:
            worker.submit_physical_effect = original

        self.assertEqual(
            calls,
            [
                ("request-worker-effect-0001", "donkey_braying"),
                ("request-worker-effect-0001", "cat_meow"),
            ],
        )
        self.assertEqual(
            [item["disposition"] for item in outcomes],
            ["disabled", "disabled"],
        )

    def test_physical_dispatch_failure_does_not_raise(self) -> None:
        original = worker.submit_physical_effect

        def fail_submit(*_args, **_kwargs):
            raise worker.PhysicalEffectsClientError("broker unavailable")

        worker.submit_physical_effect = fail_submit
        try:
            outcomes = worker.dispatch_physical_effects(
                "request-worker-effect-0002",
                {"ui_effects": ["blue_tit_easter_egg"]},
            )
        finally:
            worker.submit_physical_effect = original

        self.assertEqual(outcomes, [])

    def test_physical_dispatch_ignores_unapproved_effect(self) -> None:
        original = worker.submit_physical_effect
        calls = []

        def fake_submit(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("unapproved effect reached broker client")

        worker.submit_physical_effect = fake_submit
        try:
            outcomes = worker.dispatch_physical_effects(
                "request-worker-effect-0003",
                {"ui_effects": ["run_arbitrary_command"]},
            )
        finally:
            worker.submit_physical_effect = original

        self.assertEqual(outcomes, [])
        self.assertEqual(calls, [])

    def test_dispatch_hook_occurs_after_sanitization_and_verification(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        sanitized = source.index("result = sanitize_gateway_result(result)")
        verified = source.index("trace = verify_gateway_result(request_id, result, plan)")
        dispatched = source.index("dispatch_physical_effects(request_id, result)")
        completed = source.index(
            'complete(request_id, "completed", queue_secret, queue_key_id, result=result)'
        )

        self.assertLess(sanitized, verified)
        self.assertLess(verified, dispatched)
        self.assertLess(dispatched, completed)


if __name__ == "__main__":
    unittest.main()
