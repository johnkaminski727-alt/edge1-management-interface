#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
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


load("ava_physical_effects_broker")
load("ava_physical_effects_protocol")
load("ava_physical_effects_transport")
daemon_mod = load("ava_physical_effects_daemon")


class AvaPhysicalEffectsDaemonTests(unittest.TestCase):
    def test_default_policy_is_master_disabled(self) -> None:
        daemon = daemon_mod.BrokerDaemon(
            "/tmp/not-created.sock",
            allowed_user="wwadmin",
            allowed_group="wwadmin",
        )
        self.assertFalse(daemon.policy.enabled)

    def test_identity_is_resolved_by_name(self) -> None:
        uid, gid = daemon_mod.resolve_identity("wwadmin", "wwadmin")
        self.assertEqual(uid, os.getuid())
        self.assertEqual(gid, os.getgid())

    def test_unknown_identity_fails_closed(self) -> None:
        with self.assertRaises(daemon_mod.DaemonError):
            daemon_mod.resolve_identity(
                "definitely-no-such-ava-user",
                "definitely-no-such-ava-group",
            )

    def test_existing_socket_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effects.sock"
            path.write_text("occupied", encoding="utf-8")

            with self.assertRaises(daemon_mod.DaemonError):
                daemon_mod.prepare_socket_path(path)

    def test_socket_mode_and_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effects.sock"

            listener = daemon_mod.create_listener(
                path,
                socket_gid=os.getgid(),
            )

            try:
                socket_stat = path.stat()

                self.assertEqual(
                    socket_stat.st_uid,
                    os.getuid(),
                )
                self.assertEqual(
                    socket_stat.st_gid,
                    os.getgid(),
                )
                self.assertEqual(
                    socket_stat.st_mode & 0o777,
                    0o660,
                )
            finally:
                listener.close()
                path.unlink()

    def test_non_root_daemon_fails_closed(self) -> None:
        daemon = daemon_mod.BrokerDaemon(
            "/tmp/not-created.sock",
            allowed_user="wwadmin",
            allowed_group="wwadmin",
        )

        original_geteuid = daemon_mod.os.geteuid
        daemon_mod.os.geteuid = lambda: 1000

        try:
            with self.assertRaises(daemon_mod.DaemonError):
                daemon.serve()
        finally:
            daemon_mod.os.geteuid = original_geteuid

    def test_malformed_client_does_not_kill_connection_handler(self) -> None:
        service = daemon_mod.PhysicalEffectsProtocol(
            daemon_mod.BrokerPolicy(enabled=False),
            allowed_uid=os.getuid(),
            allowed_gid=os.getgid(),
        )

        left, right = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )

        try:
            right.sendall(b"garbage\\n")
            right.shutdown(socket.SHUT_WR)

            with self.assertRaises(Exception):
                daemon_mod.handle_connection(left, service)
        finally:
            left.close()
            right.close()

    def test_daemon_wires_durable_ledger_but_remains_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "broker-state.json"

            instance = daemon_mod.BrokerDaemon(
                "/tmp/ava-physical-effects-test.sock",
                state_path=str(state_path),
            )

            self.assertFalse(instance.policy.enabled)
            self.assertIs(
                instance.policy._durable_ledger,
                instance.ledger,
            )
            self.assertEqual(
                instance.state_path,
                state_path,
            )
            self.assertFalse(state_path.exists())

    def test_disabled_decision_creates_no_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "broker-state.json"

            instance = daemon_mod.BrokerDaemon(
                "/tmp/ava-physical-effects-test.sock",
                state_path=str(state_path),
            )

            result = instance.policy.decide(
                "request-daemon-disabled-state-0001",
                "donkey_braying",
            )

            self.assertEqual(
                result.disposition,
                "disabled",
            )
            self.assertFalse(state_path.exists())


    def test_daemon_source_contains_no_hardware_executor(self) -> None:
        source = (
            SERVER / "ava_physical_effects_daemon.py"
        ).read_text(encoding="utf-8")

        forbidden = (
            "/dev/input",
            "event4",
            "SND_TONE",
            "EV_SND",
            "DeviceAllow",
            "os.system",
            "shell=True",
            "systemctl",
        )

        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
