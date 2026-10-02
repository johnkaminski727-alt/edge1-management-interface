#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "ava_physical_effects_broker.py"

SPEC = importlib.util.spec_from_file_location(
    "ava_physical_effects_broker",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
broker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = broker
SPEC.loader.exec_module(broker)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class AvaPhysicalEffectsBrokerTests(unittest.TestCase):
    def test_exact_catalogue_allowlist(self) -> None:
        self.assertEqual(
            broker.ALLOWED_CATALOGUE_EFFECTS,
            {
                "blue_tit_chirp",
                "donkey_braying",
                "cat_meow",
                "moist_owlette_hoot",
            },
        )

    def test_disabled_by_default(self) -> None:
        policy = broker.BrokerPolicy()
        result = policy.decide(
            "request-broker-test-0001",
            "donkey_braying",
        )
        self.assertEqual(result.disposition, "disabled")

    def test_disabled_request_does_not_consume_dedupe_or_rate_budget(self) -> None:
        clock = FakeClock()
        policy = broker.BrokerPolicy(
            enabled=False,
            max_events_per_window=1,
            clock=clock,
        )

        request_id = "request-broker-disabled-0001"

        first = policy.decide(request_id, "cat_meow")
        second = policy.decide(request_id, "cat_meow")

        self.assertEqual(first.disposition, "disabled")
        self.assertEqual(second.disposition, "disabled")
        self.assertEqual(policy._seen, {})
        self.assertEqual(len(policy._events), 0)

        policy.enabled = True

        enabled = policy.decide(request_id, "cat_meow")
        self.assertEqual(enabled.disposition, "approved")

    def test_enabled_request_is_approved(self) -> None:
        policy = broker.BrokerPolicy(enabled=True)
        result = policy.decide(
            "request-broker-test-0002",
            "cat_meow",
        )
        self.assertEqual(result.disposition, "approved")

    def test_duplicate_request_is_suppressed(self) -> None:
        clock = FakeClock()
        policy = broker.BrokerPolicy(enabled=True, clock=clock)

        first = policy.decide(
            "request-broker-test-0003",
            "blue_tit_chirp",
        )
        second = policy.decide(
            "request-broker-test-0003",
            "blue_tit_chirp",
        )

        self.assertEqual(first.disposition, "approved")
        self.assertEqual(second.disposition, "duplicate")

    def test_rate_limit_suppresses_excess_events(self) -> None:
        clock = FakeClock()
        policy = broker.BrokerPolicy(
            enabled=True,
            max_events_per_window=2,
            window_seconds=60,
            clock=clock,
        )

        self.assertEqual(
            policy.decide("request-broker-rate-0001", "cat_meow").disposition,
            "approved",
        )
        self.assertEqual(
            policy.decide("request-broker-rate-0002", "donkey_braying").disposition,
            "approved",
        )
        self.assertEqual(
            policy.decide("request-broker-rate-0003", "blue_tit_chirp").disposition,
            "rate_limited",
        )

    def test_rate_limit_expires(self) -> None:
        clock = FakeClock()
        policy = broker.BrokerPolicy(
            enabled=True,
            max_events_per_window=1,
            window_seconds=10,
            clock=clock,
        )

        self.assertEqual(
            policy.decide("request-broker-window-0001", "cat_meow").disposition,
            "approved",
        )

        clock.advance(11)

        self.assertEqual(
            policy.decide("request-broker-window-0002", "cat_meow").disposition,
            "approved",
        )

    def test_duplicate_expires(self) -> None:
        clock = FakeClock()
        policy = broker.BrokerPolicy(
            enabled=True,
            dedupe_seconds=10,
            clock=clock,
        )

        self.assertEqual(
            policy.decide("request-broker-dedupe-0001", "cat_meow").disposition,
            "approved",
        )

        clock.advance(11)

        self.assertEqual(
            policy.decide("request-broker-dedupe-0001", "cat_meow").disposition,
            "approved",
        )

    def test_unknown_catalogue_effect_fails_closed(self) -> None:
        policy = broker.BrokerPolicy(enabled=True)

        with self.assertRaises(broker.BrokerPolicyError):
            policy.decide(
                "request-broker-test-0004",
                "arbitrary_frequency_880hz",
            )

    def test_bad_request_id_fails_closed(self) -> None:
        policy = broker.BrokerPolicy(enabled=True)

        for bad in ("", "x", "../event4", " " * 20):
            with self.subTest(request_id=bad):
                with self.assertRaises(broker.BrokerPolicyError):
                    policy.decide(bad, "cat_meow")

    def test_enabled_requires_exact_boolean(self) -> None:
        for bad in (0, 1, "true", None):
            with self.subTest(enabled=bad):
                with self.assertRaises(broker.BrokerPolicyError):
                    broker.BrokerPolicy(enabled=bad)

    def test_durable_reservation_survives_policy_restart(self) -> None:
        from server.ava_physical_effects_state import (
            DurableReservationLedger,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "broker-state.json"

            first_ledger = DurableReservationLedger(
                path,
                dedupe_seconds=300,
            )
            first = broker.BrokerPolicy(
                enabled=True,
                durable_ledger=first_ledger,
            )

            request_id = "request-broker-durable-0001"

            self.assertEqual(
                first.decide(
                    request_id,
                    "donkey_braying",
                ).disposition,
                "approved",
            )

            second_ledger = DurableReservationLedger(
                path,
                dedupe_seconds=300,
            )
            second = broker.BrokerPolicy(
                enabled=True,
                durable_ledger=second_ledger,
            )

            self.assertEqual(
                second.decide(
                    request_id,
                    "donkey_braying",
                ).disposition,
                "duplicate",
            )

    def test_durable_effect_mismatch_fails_closed(self) -> None:
        from server.ava_physical_effects_state import (
            DurableReservationLedger,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "broker-state.json"
            ledger = DurableReservationLedger(
                path,
                dedupe_seconds=300,
            )

            first = broker.BrokerPolicy(
                enabled=True,
                durable_ledger=ledger,
            )

            request_id = "request-broker-effect-lock-0001"

            self.assertEqual(
                first.decide(
                    request_id,
                    "cat_meow",
                ).disposition,
                "approved",
            )

            restarted = broker.BrokerPolicy(
                enabled=True,
                durable_ledger=DurableReservationLedger(
                    path,
                    dedupe_seconds=300,
                ),
            )

            with self.assertRaises(broker.BrokerPolicyError):
                restarted.decide(
                    request_id,
                    "donkey_braying",
                )

    def test_disabled_request_does_not_touch_durable_state(self) -> None:
        from server.ava_physical_effects_state import (
            DurableReservationLedger,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "broker-state.json"
            ledger = DurableReservationLedger(
                path,
                dedupe_seconds=300,
            )
            policy = broker.BrokerPolicy(
                enabled=False,
                durable_ledger=ledger,
            )

            result = policy.decide(
                "request-broker-disabled-durable-0001",
                "cat_meow",
            )

            self.assertEqual(result.disposition, "disabled")
            self.assertFalse(path.exists())

    def test_rate_limited_request_is_not_durably_reserved(self) -> None:
        from server.ava_physical_effects_state import (
            DurableReservationLedger,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "broker-state.json"
            ledger = DurableReservationLedger(
                path,
                dedupe_seconds=300,
            )
            policy = broker.BrokerPolicy(
                enabled=True,
                max_events_per_window=1,
                durable_ledger=ledger,
            )

            self.assertEqual(
                policy.decide(
                    "request-broker-rate-durable-0001",
                    "cat_meow",
                ).disposition,
                "approved",
            )

            self.assertEqual(
                policy.decide(
                    "request-broker-rate-durable-0002",
                    "donkey_braying",
                ).disposition,
                "rate_limited",
            )

            self.assertIsNone(
                ledger.lookup(
                    "request-broker-rate-durable-0002"
                )
            )


    def test_module_contains_no_execution_or_hardware_primitive(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")

        forbidden = (
            "/dev/input",
            "event4",
            "subprocess",
            "os.system",
            "shell=True",
            "/bin/sh",
            "SND_TONE",
            "EV_SND",
            "socket.socket",
            "systemctl",
        )

        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
