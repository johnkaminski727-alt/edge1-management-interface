#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"

sys.path.insert(0, str(SERVER))

BROKER_PATH = SERVER / "ava_physical_effects_broker.py"
PROTOCOL_PATH = SERVER / "ava_physical_effects_protocol.py"

broker_spec = importlib.util.spec_from_file_location(
    "ava_physical_effects_broker",
    BROKER_PATH,
)
assert broker_spec is not None and broker_spec.loader is not None
broker = importlib.util.module_from_spec(broker_spec)
sys.modules[broker_spec.name] = broker
broker_spec.loader.exec_module(broker)

protocol_spec = importlib.util.spec_from_file_location(
    "ava_physical_effects_protocol",
    PROTOCOL_PATH,
)
assert protocol_spec is not None and protocol_spec.loader is not None
protocol = importlib.util.module_from_spec(protocol_spec)
sys.modules[protocol_spec.name] = protocol
protocol_spec.loader.exec_module(protocol)


ALLOWED_UID = 1234
ALLOWED_GID = 5678
GOOD_PEER = protocol.PeerIdentity(
    pid=999,
    uid=ALLOWED_UID,
    gid=ALLOWED_GID,
)


def request(
    request_id: str = "request-protocol-test-0001",
    effect: str = "donkey_braying",
    version: int = 1,
) -> bytes:
    return json.dumps(
        {
            "version": version,
            "request_id": request_id,
            "catalogue_effect": effect,
        },
        separators=(",", ":"),
    ).encode("utf-8")


class AvaPhysicalEffectsProtocolTests(unittest.TestCase):
    def make_protocol(self, *, enabled: bool = False):
        policy = broker.BrokerPolicy(enabled=enabled)
        return protocol.PhysicalEffectsProtocol(
            policy,
            allowed_uid=ALLOWED_UID,
            allowed_gid=ALLOWED_GID,
        )

    def test_authorized_peer_disabled_policy(self) -> None:
        service = self.make_protocol()
        response = json.loads(service.handle(request(), GOOD_PEER))
        self.assertEqual(response["version"], 1)
        self.assertEqual(response["disposition"], "disabled")
        self.assertEqual(response["catalogue_effect"], "donkey_braying")

    def test_authorized_peer_enabled_policy(self) -> None:
        service = self.make_protocol(enabled=True)
        response = json.loads(service.handle(request(), GOOD_PEER))
        self.assertEqual(response["disposition"], "approved")

    def test_wrong_uid_is_denied(self) -> None:
        service = self.make_protocol()
        peer = protocol.PeerIdentity(pid=1, uid=9999, gid=ALLOWED_GID)
        with self.assertRaises(protocol.ProtocolError):
            service.handle(request(), peer)

    def test_wrong_gid_is_denied(self) -> None:
        service = self.make_protocol()
        peer = protocol.PeerIdentity(pid=1, uid=ALLOWED_UID, gid=9999)
        with self.assertRaises(protocol.ProtocolError):
            service.handle(request(), peer)

    def test_missing_peer_credentials_are_denied(self) -> None:
        service = self.make_protocol()
        with self.assertRaises(protocol.ProtocolError):
            service.handle(request(), None)  # type: ignore[arg-type]

    def test_extra_request_field_is_denied(self) -> None:
        service = self.make_protocol()
        payload = json.dumps(
            {
                "version": 1,
                "request_id": "request-protocol-test-0002",
                "catalogue_effect": "cat_meow",
                "frequency": 880,
            }
        ).encode("utf-8")

        with self.assertRaises(protocol.ProtocolError):
            service.handle(payload, GOOD_PEER)

    def test_unknown_effect_is_denied(self) -> None:
        service = self.make_protocol()
        with self.assertRaises(protocol.ProtocolError):
            service.handle(
                request(effect="arbitrary_frequency"),
                GOOD_PEER,
            )

    def test_wrong_version_is_denied(self) -> None:
        service = self.make_protocol()
        with self.assertRaises(protocol.ProtocolError):
            service.handle(request(version=2), GOOD_PEER)

    def test_invalid_json_is_denied(self) -> None:
        service = self.make_protocol()
        with self.assertRaises(protocol.ProtocolError):
            service.handle(b"{nope", GOOD_PEER)

    def test_oversized_request_is_denied(self) -> None:
        service = self.make_protocol()
        payload = b"x" * (protocol.MAX_REQUEST_BYTES + 1)
        with self.assertRaises(protocol.ProtocolError):
            service.handle(payload, GOOD_PEER)

    def test_duplicate_flows_through_broker_policy(self) -> None:
        service = self.make_protocol(enabled=True)
        payload = request("request-protocol-duplicate-0001", "cat_meow")

        first = json.loads(service.handle(payload, GOOD_PEER))
        second = json.loads(service.handle(payload, GOOD_PEER))

        self.assertEqual(first["disposition"], "approved")
        self.assertEqual(second["disposition"], "duplicate")

    def test_duplicate_json_field_is_denied(self) -> None:
        service = self.make_protocol()
        payload = (
            b'{"version":1,'
            b'"request_id":"request-duplicate-field-0001",'
            b'"catalogue_effect":"cat_meow",'
            b'"catalogue_effect":"donkey_braying"}'
        )

        with self.assertRaises(protocol.ProtocolError):
            service.handle(payload, GOOD_PEER)

    def test_boolean_protocol_version_is_denied(self) -> None:
        service = self.make_protocol()

        with self.assertRaises(protocol.ProtocolError):
            service.handle(request(version=True), GOOD_PEER)

    def test_allowed_identity_requires_exact_nonnegative_int(self) -> None:
        policy = broker.BrokerPolicy(enabled=False)

        for bad_uid, bad_gid in (
            (True, ALLOWED_GID),
            (ALLOWED_UID, False),
            (-1, ALLOWED_GID),
            (ALLOWED_UID, -1),
            ("1234", ALLOWED_GID),
            (ALLOWED_UID, "5678"),
        ):
            with self.subTest(uid=bad_uid, gid=bad_gid):
                with self.assertRaises(protocol.ProtocolError):
                    protocol.PhysicalEffectsProtocol(
                        policy,
                        allowed_uid=bad_uid,
                        allowed_gid=bad_gid,
                    )

    def test_peer_identity_requires_exact_nonnegative_ints(self) -> None:
        service = self.make_protocol()

        bad_peers = (
            protocol.PeerIdentity(
                pid=True,
                uid=ALLOWED_UID,
                gid=ALLOWED_GID,
            ),
            protocol.PeerIdentity(
                pid=1,
                uid=True,
                gid=ALLOWED_GID,
            ),
            protocol.PeerIdentity(
                pid=1,
                uid=ALLOWED_UID,
                gid=True,
            ),
            protocol.PeerIdentity(
                pid=-1,
                uid=ALLOWED_UID,
                gid=ALLOWED_GID,
            ),
            protocol.PeerIdentity(
                pid=1,
                uid=-1,
                gid=ALLOWED_GID,
            ),
            protocol.PeerIdentity(
                pid=1,
                uid=ALLOWED_UID,
                gid=-1,
            ),
        )

        for peer in bad_peers:
            with self.subTest(peer=peer):
                with self.assertRaises(protocol.ProtocolError):
                    service.handle(request(), peer)

    def test_response_schema_is_exact(self) -> None:
        service = self.make_protocol()
        response = json.loads(service.handle(request(), GOOD_PEER))

        self.assertEqual(
            set(response),
            {
                "version",
                "request_id",
                "catalogue_effect",
                "disposition",
            },
        )
        self.assertEqual(
            response,
            {
                "version": 1,
                "request_id": "request-protocol-test-0001",
                "catalogue_effect": "donkey_braying",
                "disposition": "disabled",
            },
        )

    def test_protocol_has_no_hardware_executor(self) -> None:
        source = PROTOCOL_PATH.read_text(encoding="utf-8")

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
