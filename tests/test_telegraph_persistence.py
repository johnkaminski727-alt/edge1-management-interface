#!/usr/bin/env python3
"""Restart-persistence tests for the Telegraph Office reference service."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reference.telegraph_federation_demo import encrypt_envelope
from reference.telegraph_office_service import TelegraphOfficeHTTPServer, build_state


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
    def __init__(self, office_id: str, database_path: Path | None = None):
        self.state = build_state(office_id, database_path)
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


class TelegraphPersistenceTests(unittest.TestCase):
    def test_peer_message_receipt_and_replay_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "bravo.sqlite3"
            alpha = RunningOffice("alpha.telegraph.ww.cx")
            bravo = RunningOffice("bravo.telegraph.ww.cx", database)
            alpha.start()
            bravo.start()
            try:
                identity_status, alpha_identity = request_json("GET", alpha.base_url + "/identity")
                self.assertEqual(identity_status, HTTPStatus.OK)
                peer_status, peer = request_json(
                    "POST",
                    bravo.base_url + "/directory/peers",
                    {
                        "office_id": "alpha.telegraph.ww.cx",
                        "identity": alpha_identity,
                        "trust_status": "trusted",
                    },
                )
                self.assertEqual(peer_status, HTTPStatus.CREATED)
                self.assertTrue(peer["identity_verified"])

                envelope, _key = encrypt_envelope(
                    alpha.state.office,
                    bravo.state.office,
                    "Persistent accessible message",
                    "NORTH STAR",
                )
                accepted_status, accepted = request_json("POST", bravo.base_url + "/message", envelope)
                self.assertEqual(accepted_status, HTTPStatus.ACCEPTED)
                first_receipt_id = accepted["receipt"]["receipt_id"]
                message_id = envelope["message_id"]
            finally:
                bravo.stop()

            restarted = RunningOffice("bravo.telegraph.ww.cx", database)
            restarted.start()
            try:
                health_status, health = request_json("GET", restarted.base_url + "/health")
                self.assertEqual(health_status, HTTPStatus.OK)
                self.assertTrue(health["persistent_storage"])

                directory_status, directory_payload = request_json("GET", restarted.base_url + "/directory")
                self.assertEqual(directory_status, HTTPStatus.OK)
                self.assertEqual(directory_payload["count"], 1)
                self.assertEqual(directory_payload["peers"][0]["office_id"], "alpha.telegraph.ww.cx")

                receipt_status, receipt_payload = request_json(
                    "GET", restarted.base_url + "/receipts/" + message_id
                )
                self.assertEqual(receipt_status, HTTPStatus.OK)
                self.assertEqual(receipt_payload["receipts"][0]["receipt_id"], first_receipt_id)

                self.assertIn(message_id, restarted.state.messages)
                self.assertEqual(restarted.state.messages[message_id], envelope)

                replay_status, replay = request_json("POST", restarted.base_url + "/message", envelope)
                self.assertEqual(replay_status, HTTPStatus.CONFLICT)
                self.assertEqual(replay["status"], "duplicate_rejected")

                receipt_status, receipt_payload = request_json(
                    "GET", restarted.base_url + "/receipts/" + message_id
                )
                self.assertEqual(receipt_status, HTTPStatus.OK)
                self.assertEqual(len(receipt_payload["receipts"]), 2)
                self.assertEqual(receipt_payload["receipts"][1]["event"], "duplicate_rejected")
                self.assertGreater(
                    receipt_payload["receipts"][1]["sequence"],
                    receipt_payload["receipts"][0]["sequence"],
                )
            finally:
                restarted.stop()
                alpha.stop()

    def test_ephemeral_service_reports_storage_disabled(self) -> None:
        office = RunningOffice("ephemeral.telegraph.ww.cx")
        office.start()
        try:
            health_status, health = request_json("GET", office.base_url + "/health")
            capabilities_status, capabilities = request_json("GET", office.base_url + "/capabilities")
            self.assertEqual(health_status, HTTPStatus.OK)
            self.assertEqual(capabilities_status, HTTPStatus.OK)
            self.assertFalse(health["persistent_storage"])
            self.assertFalse(capabilities["persistent_storage"])
        finally:
            office.stop()


if __name__ == "__main__":
    unittest.main()
