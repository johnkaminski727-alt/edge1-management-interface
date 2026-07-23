#!/usr/bin/env python3
"""Tests for bounded Telegraph federation directory synchronization."""

from __future__ import annotations

import time
import unittest
from urllib.error import URLError

from reference.telegraph_directory_sync import (
    TelegraphDirectorySynchronizer,
    directory_endpoint,
)
from reference.telegraph_office_service import build_state


class TelegraphDirectorySchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.alpha = build_state("alpha.telegraph.ww.cx")
        self.bravo = build_state("bravo.telegraph.ww.cx")
        self.charlie = build_state("charlie.telegraph.ww.cx")
        status, _record = self.bravo.register_peer({
            "office_id": self.alpha.office.office_id,
            "identity": self.alpha.office.identity_document(),
            "trust_status": "trusted",
        })
        self.assertEqual(status.value, 201)

    def tearDown(self) -> None:
        self.alpha.close()
        self.bravo.close()
        self.charlie.close()

    def test_directory_endpoint_uses_signed_federation_service(self) -> None:
        endpoint = directory_endpoint(self.alpha.office.identity_document())
        self.assertEqual(endpoint, "https://alpha.telegraph.ww.cx/telegraph/directory")

    def test_restricted_peer_is_never_contacted(self) -> None:
        record = dict(self.bravo.peers[self.alpha.office.office_id])
        record["trust_status"] = "restricted"
        calls: list[tuple[str, float]] = []

        def fetcher(url: str, timeout: float) -> dict:
            calls.append((url, timeout))
            raise AssertionError("restricted peer must not be contacted")

        scheduler = TelegraphDirectorySynchronizer(self.bravo, fetcher=fetcher)
        result = scheduler.sync_peer(self.alpha.office.office_id, record)
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.detail, "restricted_peer")
        self.assertEqual(calls, [])

    def test_valid_manifest_is_synchronized(self) -> None:
        now = int(time.time())
        directory = {
            "version": "1.0",
            "office_id": self.alpha.office.office_id,
            "generated_at": now,
            "peers": [{
                "office_id": self.charlie.office.office_id,
                "identity": self.charlie.office.identity_document(),
                "trust_status": "trusted",
                "updated_at": now + 1,
                "identity_verified": True,
            }],
            "count": 1,
        }
        directory["signature"] = self.alpha.office.sign(directory)

        scheduler = TelegraphDirectorySynchronizer(
            self.bravo,
            fetcher=lambda _url, _timeout: directory,
        )
        result = scheduler.sync_peer(
            self.alpha.office.office_id,
            self.bravo.peers[self.alpha.office.office_id],
        )
        self.assertEqual(result.status, "synchronized")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.response["imported"], 1)
        self.assertEqual(
            self.bravo.peers[self.charlie.office.office_id]["trust_status"],
            "observed",
        )

    def test_source_mismatch_is_rejected_before_state_change(self) -> None:
        directory = self.charlie.directory()
        scheduler = TelegraphDirectorySynchronizer(
            self.bravo,
            fetcher=lambda _url, _timeout: directory,
        )
        result = scheduler.sync_peer(
            self.alpha.office.office_id,
            self.bravo.peers[self.alpha.office.office_id],
        )
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.detail, "directory_source_mismatch")
        self.assertEqual(result.attempts, 1)

    def test_transient_failures_use_bounded_exponential_backoff(self) -> None:
        attempts = 0
        delays: list[float] = []
        directory = self.alpha.directory()

        def fetcher(_url: str, _timeout: float) -> dict:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise URLError("temporary outage")
            return directory

        scheduler = TelegraphDirectorySynchronizer(
            self.bravo,
            max_attempts=3,
            backoff_seconds=2,
            jitter_fraction=0,
            fetcher=fetcher,
            sleep=delays.append,
        )
        result = scheduler.sync_peer(
            self.alpha.office.office_id,
            self.bravo.peers[self.alpha.office.office_id],
        )
        self.assertEqual(result.status, "synchronized")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(delays, [2, 4])

    def test_retry_budget_returns_failure_without_unbounded_loop(self) -> None:
        delays: list[float] = []

        def fetcher(_url: str, _timeout: float) -> dict:
            raise TimeoutError("peer did not answer")

        scheduler = TelegraphDirectorySynchronizer(
            self.bravo,
            max_attempts=2,
            backoff_seconds=1,
            jitter_fraction=0,
            fetcher=fetcher,
            sleep=delays.append,
        )
        result = scheduler.sync_peer(
            self.alpha.office.office_id,
            self.bravo.peers[self.alpha.office.office_id],
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.attempts, 2)
        self.assertIn("TimeoutError", result.detail)
        self.assertEqual(delays, [1])

    def test_sync_once_records_results_for_each_peer(self) -> None:
        status, _record = self.bravo.register_peer({
            "office_id": self.charlie.office.office_id,
            "identity": self.charlie.office.identity_document(),
            "trust_status": "restricted",
        })
        self.assertEqual(status.value, 201)
        directories = {
            self.alpha.office.office_id: self.alpha.directory(),
        }

        def fetcher(url: str, _timeout: float) -> dict:
            for office_id, document in directories.items():
                if office_id in url:
                    return document
            raise AssertionError(f"unexpected URL {url}")

        scheduler = TelegraphDirectorySynchronizer(self.bravo, fetcher=fetcher)
        results = scheduler.sync_once()
        self.assertEqual(results[self.alpha.office.office_id].status, "synchronized")
        self.assertEqual(results[self.charlie.office.office_id].status, "skipped")
        self.assertIs(scheduler.last_results, results)

    def test_start_and_stop_are_idempotent(self) -> None:
        scheduler = TelegraphDirectorySynchronizer(
            self.bravo,
            interval_seconds=0.01,
            fetcher=lambda _url, _timeout: self.alpha.directory(),
        )
        scheduler.start()
        first_thread = scheduler._thread
        scheduler.start()
        self.assertIs(scheduler._thread, first_thread)
        scheduler.stop(timeout=1)
        scheduler.stop(timeout=1)
        self.assertTrue(scheduler.stop_event.is_set())
        self.assertFalse(first_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
