#!/usr/bin/env python3
"""Security and conflict-resolution tests for Telegraph directory sync."""

from __future__ import annotations

import time
import unittest
from http import HTTPStatus

from reference.telegraph_office_service import build_state


class TelegraphDirectorySyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.alpha = build_state("alpha.telegraph.ww.cx")
        self.bravo = build_state("bravo.telegraph.ww.cx")
        self.charlie = build_state("charlie.telegraph.ww.cx")
        status, _record = self.bravo.register_peer({
            "office_id": self.alpha.office.office_id,
            "identity": self.alpha.office.identity_document(),
            "trust_status": "trusted",
        })
        self.assertEqual(status, HTTPStatus.CREATED)

    def tearDown(self) -> None:
        self.alpha.close()
        self.bravo.close()
        self.charlie.close()

    def manifest(self, peers: list[dict]) -> dict:
        document = {
            "version": "1.0",
            "office_id": self.alpha.office.office_id,
            "generated_at": int(time.time()),
            "peers": peers,
            "count": len(peers),
        }
        document["signature"] = self.alpha.office.sign(document)
        return document

    def charlie_record(self, updated_at: int, trust_status: str = "trusted") -> dict:
        return {
            "office_id": self.charlie.office.office_id,
            "identity": self.charlie.office.identity_document(),
            "trust_status": trust_status,
            "updated_at": updated_at,
            "identity_verified": True,
        }

    def test_signed_manifest_imports_identity_without_remote_trust_elevation(self) -> None:
        status, payload = self.bravo.sync_directory(
            self.manifest([self.charlie_record(int(time.time()) + 10)])
        )
        self.assertEqual(status, HTTPStatus.ACCEPTED)
        self.assertTrue(payload["signature_verified"])
        self.assertEqual(payload["imported"], 1)
        imported = self.bravo.peers[self.charlie.office.office_id]
        self.assertEqual(imported["trust_status"], "observed")
        self.assertEqual(imported["directory_source"], self.alpha.office.office_id)
        self.assertTrue(imported["identity_verified"])

    def test_tampered_manifest_is_rejected_before_import(self) -> None:
        document = self.manifest([self.charlie_record(int(time.time()) + 10)])
        document["count"] = 999
        status, payload = self.bravo.sync_directory(document)
        self.assertEqual(status, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(payload["error"], "invalid_directory_signature")
        self.assertNotIn(self.charlie.office.office_id, self.bravo.peers)

    def test_unknown_source_is_rejected_even_with_valid_self_signature(self) -> None:
        document = {
            "version": "1.0",
            "office_id": self.charlie.office.office_id,
            "generated_at": int(time.time()),
            "peers": [],
            "count": 0,
        }
        document["signature"] = self.charlie.office.sign(document)
        status, payload = self.bravo.sync_directory(document)
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertEqual(payload["error"], "unknown_directory_source")

    def test_stale_record_is_skipped(self) -> None:
        now = int(time.time())
        first_status, _payload = self.bravo.sync_directory(
            self.manifest([self.charlie_record(now + 20)])
        )
        self.assertEqual(first_status, HTTPStatus.ACCEPTED)
        original = dict(self.bravo.peers[self.charlie.office.office_id])

        stale_status, stale = self.bravo.sync_directory(
            self.manifest([self.charlie_record(now + 10)])
        )
        self.assertEqual(stale_status, HTTPStatus.ACCEPTED)
        self.assertEqual(stale["skipped"], 1)
        self.assertEqual(self.bravo.peers[self.charlie.office.office_id], original)

    def test_newer_identity_refresh_preserves_local_restriction(self) -> None:
        register_status, local = self.bravo.register_peer({
            "office_id": self.charlie.office.office_id,
            "identity": self.charlie.office.identity_document(),
            "trust_status": "restricted",
        })
        self.assertEqual(register_status, HTTPStatus.CREATED)

        newer = int(local["updated_at"]) + 10
        status, payload = self.bravo.sync_directory(
            self.manifest([self.charlie_record(newer, trust_status="trusted")])
        )
        self.assertEqual(status, HTTPStatus.ACCEPTED)
        self.assertEqual(payload["updated"], 1)
        self.assertEqual(
            self.bravo.peers[self.charlie.office.office_id]["trust_status"],
            "restricted",
        )

    def test_directory_response_is_signed(self) -> None:
        directory = self.alpha.directory()
        self.assertEqual(directory["office_id"], self.alpha.office.office_id)
        self.assertIn("signature", directory)
        self.assertEqual(directory["count"], len(directory["peers"]))


if __name__ == "__main__":
    unittest.main()
