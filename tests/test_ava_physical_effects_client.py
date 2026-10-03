#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

MODULE = SERVER / "ava_physical_effects_client.py"
SPEC = importlib.util.spec_from_file_location(
    "ava_physical_effects_client",
    MODULE,
)
assert SPEC is not None and SPEC.loader is not None
client = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = client
SPEC.loader.exec_module(client)


class PhysicalEffectsClientTests(unittest.TestCase):
    def test_payload_is_exact_and_bounded(self) -> None:
        raw = client._request_payload(
            "request-client-test-0001",
            "donkey_braying",
        )
        self.assertTrue(raw.endswith(b"\n"))
        parsed = json.loads(raw)
        self.assertEqual(
            set(parsed),
            {"version", "request_id", "catalogue_effect"},
        )
        self.assertEqual(parsed["version"], 1)

    def test_exact_disabled_response_is_accepted(self) -> None:
        raw = (
            b'{"catalogue_effect":"donkey_braying",'
            b'"disposition":"disabled",'
            b'"request_id":"request-client-test-0002",'
            b'"version":1}'
        )
        response = client._validate_response(
            raw,
            "request-client-test-0002",
            "donkey_braying",
        )
        self.assertEqual(response["disposition"], "disabled")

    def test_response_identity_mismatch_fails_closed(self) -> None:
        raw = (
            b'{"catalogue_effect":"cat_meow",'
            b'"disposition":"disabled",'
            b'"request_id":"request-client-test-WRONG",'
            b'"version":1}'
        )
        with self.assertRaises(client.PhysicalEffectsClientError):
            client._validate_response(
                raw,
                "request-client-test-0003",
                "cat_meow",
            )

    def test_duplicate_response_key_fails_closed(self) -> None:
        raw = (
            b'{"version":1,"version":1,'
            b'"request_id":"request-client-test-0004",'
            b'"catalogue_effect":"cat_meow",'
            b'"disposition":"disabled"}'
        )
        with self.assertRaises(client.PhysicalEffectsClientError):
            client._validate_response(
                raw,
                "request-client-test-0004",
                "cat_meow",
            )

    def test_extra_response_field_fails_closed(self) -> None:
        raw = (
            b'{"version":1,'
            b'"request_id":"request-client-test-0005",'
            b'"catalogue_effect":"cat_meow",'
            b'"disposition":"disabled","extra":true}'
        )
        with self.assertRaises(client.PhysicalEffectsClientError):
            client._validate_response(
                raw,
                "request-client-test-0005",
                "cat_meow",
            )

    def test_boolean_version_fails_closed(self) -> None:
        raw = (
            b'{"version":true,'
            b'"request_id":"request-client-test-0006",'
            b'"catalogue_effect":"cat_meow",'
            b'"disposition":"disabled"}'
        )
        with self.assertRaises(client.PhysicalEffectsClientError):
            client._validate_response(
                raw,
                "request-client-test-0006",
                "cat_meow",
            )

    def test_unapproved_disposition_fails_closed(self) -> None:
        raw = (
            b'{"version":1,'
            b'"request_id":"request-client-test-0007",'
            b'"catalogue_effect":"cat_meow",'
            b'"disposition":"execute_arbitrary_command"}'
        )
        with self.assertRaises(client.PhysicalEffectsClientError):
            client._validate_response(
                raw,
                "request-client-test-0007",
                "cat_meow",
            )

    def test_socket_round_trip(self) -> None:
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        original_socket = client.socket.socket

        class FakeSocket:
            def __init__(self, *_args, **_kwargs):
                self.sock = left

            def settimeout(self, value):
                self.sock.settimeout(value)

            def connect(self, _path):
                return None

            def sendall(self, data):
                self.sock.sendall(data)

            def recv(self, size):
                return self.sock.recv(size)

            def close(self):
                self.sock.close()

        def broker():
            request = bytearray()
            while not request.endswith(b"\n"):
                request.extend(right.recv(256))
            parsed = json.loads(bytes(request[:-1]).decode())
            response = {
                "version": 1,
                "request_id": parsed["request_id"],
                "catalogue_effect": parsed["catalogue_effect"],
                "disposition": "disabled",
            }
            right.sendall(
                json.dumps(
                    response,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode() + b"\n"
            )
            right.close()

        thread = threading.Thread(target=broker)
        thread.start()
        client.socket.socket = FakeSocket

        try:
            response = client.submit(
                "request-client-test-0008",
                "donkey_braying",
            )
        finally:
            client.socket.socket = original_socket
            thread.join(timeout=2)

        self.assertEqual(response["disposition"], "disabled")

    def test_nonfinite_timeout_fails_closed(self) -> None:
        for timeout in (
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(timeout=timeout):
                with self.assertRaises(
                    client.PhysicalEffectsClientError
                ):
                    client.submit(
                        "request-client-timeout-0001",
                        "donkey_braying",
                        timeout=timeout,
                    )

    def test_module_contains_no_hardware_or_shell_primitive(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in (
            "/dev/input",
            "event4",
            "subprocess",
            "os.system",
            "shell=True",
            "SND_TONE",
            "EV_SND",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
