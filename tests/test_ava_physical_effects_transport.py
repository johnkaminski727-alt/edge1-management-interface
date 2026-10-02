#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))


def load(name: str):
    path = SERVER / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


broker = load("ava_physical_effects_broker")
protocol_mod = load("ava_physical_effects_protocol")
transport = load("ava_physical_effects_transport")


def payload(
    request_id: str = "request-transport-test-0001",
    effect: str = "donkey_braying",
) -> bytes:
    return (
        json.dumps(
            {
                "version": 1,
                "request_id": request_id,
                "catalogue_effect": effect,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class AvaPhysicalEffectsTransportTests(unittest.TestCase):
    def make_protocol(self, *, enabled: bool = False):
        return protocol_mod.PhysicalEffectsProtocol(
            broker.BrokerPolicy(enabled=enabled),
            allowed_uid=os.getuid(),
            allowed_gid=os.getgid(),
        )

    def test_socketpair_peer_credentials_are_kernel_derived(self) -> None:
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            peer = transport.peer_identity(left)
            self.assertEqual(peer.uid, os.getuid())
            self.assertEqual(peer.gid, os.getgid())
            self.assertGreater(peer.pid, 0)
        finally:
            left.close()
            right.close()

    def test_real_unix_socket_round_trip_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "effects.sock")
            ready = threading.Event()
            errors = []

            def server():
                try:
                    transport.serve_once(
                        path,
                        self.make_protocol(enabled=False),
                        ready=ready.set,
                    )
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=server)
            thread.start()

            self.assertTrue(ready.wait(timeout=2))

            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                client.connect(path)
                client.sendall(payload())
                response = client.recv(2048)
            finally:
                client.close()

            thread.join(timeout=2)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])

            decoded = json.loads(response)
            self.assertEqual(decoded["disposition"], "disabled")
            self.assertEqual(decoded["catalogue_effect"], "donkey_braying")
            self.assertFalse(Path(path).exists())

    def test_real_unix_socket_round_trip_enabled_policy_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "effects.sock")
            ready = threading.Event()
            errors = []

            def server():
                try:
                    transport.serve_once(
                        path,
                        self.make_protocol(enabled=True),
                        ready=ready.set,
                    )
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=server)
            thread.start()

            self.assertTrue(ready.wait(timeout=2))

            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                client.connect(path)
                client.sendall(
                    payload(
                        "request-transport-enabled-0001",
                        "cat_meow",
                    )
                )
                response = client.recv(2048)
            finally:
                client.close()

            thread.join(timeout=2)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(
                json.loads(response)["disposition"],
                "approved",
            )

    def test_wrong_kernel_peer_identity_is_rejected(self) -> None:
        service = protocol_mod.PhysicalEffectsProtocol(
            broker.BrokerPolicy(),
            allowed_uid=os.getuid() + 1,
            allowed_gid=os.getgid(),
        )

        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            right.sendall(payload())

            with self.assertRaises(transport.TransportError):
                transport.handle_connection(left, service)
        finally:
            left.close()
            right.close()

    def test_multiple_requests_in_one_connection_are_rejected(self) -> None:
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            right.sendall(payload() + payload("request-transport-test-0002"))

            with self.assertRaises(transport.TransportError):
                transport.receive_request(left)
        finally:
            left.close()
            right.close()

    def test_missing_newline_is_rejected(self) -> None:
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            right.sendall(payload()[:-1])
            right.shutdown(socket.SHUT_WR)

            with self.assertRaises(transport.TransportError):
                transport.receive_request(left)
        finally:
            left.close()
            right.close()

    def test_silent_client_times_out(self) -> None:
        service = protocol_mod.PhysicalEffectsProtocol(
            broker.BrokerPolicy(enabled=False),
            allowed_uid=os.getuid(),
            allowed_gid=os.getgid(),
        )

        left, right = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )

        original_timeout = transport.CONNECTION_TIMEOUT_SECONDS
        transport.CONNECTION_TIMEOUT_SECONDS = 0.05

        try:
            with self.assertRaises(transport.TransportError):
                transport.handle_connection(left, service)
        finally:
            transport.CONNECTION_TIMEOUT_SECONDS = original_timeout
            left.close()
            right.close()

    def test_transport_contains_no_hardware_executor(self) -> None:
        source = (SERVER / "ava_physical_effects_transport.py").read_text(
            encoding="utf-8"
        )

        forbidden = (
            "/dev/input",
            "event4",
            "SND_TONE",
            "EV_SND",
            "os.system",
            "shell=True",
            "systemctl",
        )

        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
