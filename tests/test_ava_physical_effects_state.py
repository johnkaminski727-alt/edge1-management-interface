#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "ava_physical_effects_state.py"

SPEC = importlib.util.spec_from_file_location(
    "ava_physical_effects_state",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
state = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = state
SPEC.loader.exec_module(state)


class FakeWallClock:
    def __init__(self):
        self.now = 1000000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class DurableReservationLedgerTests(unittest.TestCase):
    def make_ledger(self, directory, clock, **kwargs):
        return state.DurableReservationLedger(
            Path(directory) / "broker-state.json",
            dedupe_seconds=kwargs.pop("dedupe_seconds", 300),
            wall_clock=clock,
            **kwargs,
        )

    def test_missing_state_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            self.assertIsNone(
                ledger.lookup("request-state-test-0001")
            )

    def test_reservation_survives_new_instance(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()

            first = self.make_ledger(td, clock)
            self.assertTrue(
                first.reserve(
                    "request-state-test-0002",
                    "donkey_braying",
                )
            )

            second = self.make_ledger(td, clock)

            self.assertEqual(
                second.lookup("request-state-test-0002"),
                {
                    "catalogue_effect": "donkey_braying",
                    "reserved_at": clock.now,
                },
            )

            self.assertFalse(
                second.reserve(
                    "request-state-test-0002",
                    "donkey_braying",
                )
            )

    def test_expired_reservation_can_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(
                td,
                clock,
                dedupe_seconds=10,
            )

            self.assertTrue(
                ledger.reserve(
                    "request-state-test-0003",
                    "cat_meow",
                )
            )

            clock.advance(11)

            self.assertIsNone(
                ledger.lookup("request-state-test-0003")
            )

            self.assertTrue(
                ledger.reserve(
                    "request-state-test-0003",
                    "cat_meow",
                )
            )

    def test_state_file_is_mode_0600(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            ledger.reserve(
                "request-state-test-0004",
                "blue_tit_chirp",
            )

            mode = (
                Path(td, "broker-state.json").stat().st_mode
                & 0o777
            )
            self.assertEqual(mode, 0o600)

    def test_schema_is_exact_and_versioned(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            ledger.reserve(
                "request-state-test-0005",
                "moist_owlette_hoot",
            )

            data = json.loads(
                Path(td, "broker-state.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                set(data),
                {"version", "reservations"},
            )
            self.assertEqual(data["version"], 1)

            record = data["reservations"][
                "request-state-test-0005"
            ]
            self.assertEqual(
                set(record),
                {"catalogue_effect", "reserved_at"},
            )

    def test_malformed_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            path = Path(td, "broker-state.json")
            path.write_text("{not-json", encoding="utf-8")

            ledger = self.make_ledger(td, clock)

            with self.assertRaises(
                state.PhysicalEffectsStateError
            ):
                ledger.lookup("request-state-test-0006")

    def test_unknown_state_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            path = Path(td, "broker-state.json")
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reservations": {},
                        "surprise": True,
                    }
                ),
                encoding="utf-8",
            )

            ledger = self.make_ledger(td, clock)

            with self.assertRaises(
                state.PhysicalEffectsStateError
            ):
                ledger.lookup("request-state-test-0007")

    def test_bound_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(
                td,
                clock,
                max_records=1,
            )

            self.assertTrue(
                ledger.reserve(
                    "request-state-bound-0001",
                    "cat_meow",
                )
            )

            with self.assertRaises(
                state.PhysicalEffectsStateError
            ):
                ledger.reserve(
                    "request-state-bound-0002",
                    "donkey_braying",
                )

    def test_duplicate_json_state_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            path = Path(td, "broker-state.json")
            path.write_text(
                '{"version":1,"version":1,"reservations":{}}',
                encoding="utf-8",
            )

            ledger = self.make_ledger(td, clock)

            with self.assertRaises(
                state.PhysicalEffectsStateError
            ):
                ledger.lookup("request-state-duplicate-key-0001")

    def test_duplicate_request_does_not_replace_effect(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            request_id = "request-state-effect-lock-0001"

            self.assertTrue(
                ledger.reserve(
                    request_id,
                    "cat_meow",
                )
            )

            self.assertFalse(
                ledger.reserve(
                    request_id,
                    "donkey_braying",
                )
            )

            self.assertEqual(
                ledger.lookup(request_id),
                {
                    "catalogue_effect": "cat_meow",
                    "reserved_at": clock.now,
                },
            )


    def test_recent_count_uses_strict_window_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            self.assertTrue(
                ledger.reserve(
                    "request-state-recent-0001",
                    "cat_meow",
                )
            )

            clock.advance(59)
            self.assertEqual(ledger.recent_count(60), 1)

            clock.advance(1)
            self.assertEqual(ledger.recent_count(60), 0)

    def test_recent_count_missing_state_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)
            path = Path(td) / "broker-state.json"

            self.assertEqual(ledger.recent_count(60), 0)
            self.assertFalse(path.exists())

    def test_recent_count_rejects_invalid_window(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(td, clock)

            for bad in (
                True,
                0,
                -1,
                "60",
                float("nan"),
                float("inf"),
                float("-inf"),
            ):
                with self.subTest(window_seconds=bad):
                    with self.assertRaises(
                        state.PhysicalEffectsStateError
                    ):
                        ledger.recent_count(bad)

    def test_retention_seconds_exposes_dedupe_window(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            ledger = self.make_ledger(
                td,
                clock,
                dedupe_seconds=321,
            )

            self.assertEqual(
                ledger.retention_seconds,
                321.0,
            )


    def test_invalid_constructor_types_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            clock = FakeWallClock()
            path = Path(td) / "broker-state.json"

            for bad in (True, 0, -1, "300", float("nan"), float("inf"), float("-inf")):
                with self.subTest(dedupe_seconds=bad):
                    with self.assertRaises(
                        state.PhysicalEffectsStateError
                    ):
                        state.DurableReservationLedger(
                            path,
                            dedupe_seconds=bad,
                            wall_clock=clock,
                        )

            for bad in (True, 0, -1, 1.5, "256"):
                with self.subTest(max_records=bad):
                    with self.assertRaises(
                        state.PhysicalEffectsStateError
                    ):
                        state.DurableReservationLedger(
                            path,
                            dedupe_seconds=300,
                            max_records=bad,
                            wall_clock=clock,
                        )


if __name__ == "__main__":
    unittest.main()
