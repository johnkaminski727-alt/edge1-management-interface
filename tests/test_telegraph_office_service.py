#!/usr/bin/env python3
"""Integration tests for two independent Telegraph Office HTTP services."""

from __future__ import annotations

import json
import threading
import unittest
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reference.telegraph_federation_demo import encrypt_envelope
from reference.telegraph_office_service import (
    TelegraphOfficeHTTPServer,
    build_state,
)


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


class RunningOffice:
    def __init__(self, office_id: str):
        self.state = build_state(office_id)
        self.server = TelegraphOfficeHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class TelegraphOfficeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.alpha = RunningOffice("alpha.telegraph.ww.cx")
        self.bravo = RunningOffice("bravo.telegraph.ww.cx")
        self.alpha.start()
        self.bravo.start()

    def tearDown(self) -> None:
        self.alpha.stop()
        self.bravo.stop()

    def test_two_office_exchange_and_replay_rejection(self) -> None:
        alpha_identity_status, alpha_identity = request_json("GET", self.alpha.base_url + "/identity")
        bravo_identity_status, bravo_identity = request_json("GET", self.bravo.base_url + "/identity")
        self.assertEqual(alpha_identity_status, HTTPStatus.OK)
        self.assertEqual(bravo_identity_status, HTTPStatus.OK)

        status, peer_record = request_json(
            "POST",
            self.alpha.base_url + "/directory/peers",
            {
                "office_id": self.bravo.state.office.office_id,
                "identity": bravo_identity,
                "trust_status": "trusted",
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(peer_record["trust_status"], "trusted")

        status, _ = request_json(
            "POST",
            self.bravo.base_url + "/directory/peers",
            {
                "office_id": self.alpha.state.office.office_id,
                "identity": alpha_identity,
                "trust_status": "trusted",
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)

        envelope, _key = encrypt_envelope(
            self.alpha.state.office,
            self.bravo.state.office,
            "Networked accessible test message",
            "NORTHERN LIGHT",
        )

        status, accepted = request_json("POST", self.bravo.base_url + "/message", envelope)
        self.assertEqual(status, HTTPStatus.ACCEPTED)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["receipt"]["event"], "accepted")

        duplicate_status, duplicate = request_json("POST", self.bravo.base_url + "/message", envelope)
        self.assertEqual(duplicate_status, HTTPStatus.CONFLICT)
        self.assertEqual(duplicate["status"], "duplicate_rejected")
        self.assertEqual(duplicate["receipt"]["event"], "duplicate_rejected")

        receipt_status, receipt_chain = request_json(
            "GET",
            self.bravo.base_url + "/receipts/" + envelope["message_id"],
        )
        self.assertEqual(receipt_status, HTTPStatus.OK)
        self.assertEqual(len(receipt_chain["receipts"]), 2)
        self.assertEqual(
            receipt_chain["receipts"][1]["previous_receipt_digest"],
            accepted["receipt"] and duplicate["receipt"]["previous_receipt_digest"],
        )

    def test_wrong_destination_is_rejected(self) -> None:
        envelope, _key = encrypt_envelope(
            self.alpha.state.office,
            self.bravo.state.office,
            "Wrong destination test",
            "CHECKPOINT",
        )
        envelope["destination"] = "charlie.telegraph.ww.cx"
        status, response = request_json("POST", self.bravo.base_url + "/message", envelope)
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(response["error"], "wrong_destination")

    def test_health_capabilities_and_directory(self) -> None:
        health_status, health = request_json("GET", self.alpha.base_url + "/health")
        capabilities_status, capabilities = request_json("GET", self.alpha.base_url + "/capabilities")
        directory_status, directory = request_json("GET", self.alpha.base_url + "/directory")

        self.assertEqual(health_status, HTTPStatus.OK)
        self.assertEqual(health["status"], "ok")
        self.assertFalse(health["production_ready"])
        self.assertEqual(capabilities_status, HTTPStatus.OK)
        self.assertIn("rtt_t140", capabilities["media"])
        self.assertEqual(directory_status, HTTPStatus.OK)
        self.assertEqual(directory["count"], 0)


if __name__ == "__main__":
    unittest.main()
