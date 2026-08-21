#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "server" / "operations_health_exporter.py"
SPEC = importlib.util.spec_from_file_location("operations_health_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


HEALTHY_INPUTS = dict(
    security={"health": {"status": "healthy"}, "engine": {"MemoryCurrent": 0}},
    wallet={"wallet": {"synchronized": True}, "service": {"connected": True}},
    mining={"warnings": []},
    telephony={"available": True},
    messaging={"available": True, "status": {"status": "ok"}},
    inventory={"host": "edge1"},
    network={"interfaces": ["eth0"]},
    carrier={"telephony": {"overall_status": "healthy"}},
)


def check(checks, name):
    for item in checks:
        if item["name"] == name:
            return item
    raise AssertionError(f"no check named {name}")


class OperationsHealthExporterTests(unittest.TestCase):
    def test_all_healthy_inputs_produce_healthy_checks(self):
        checks = MODULE.build_checks(**HEALTHY_INPUTS)
        self.assertTrue(all(item["state"] == "healthy" for item in checks))

    def test_mining_with_real_warnings_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, mining={"warnings": ["hardware not detected"]})
        mining_check = check(MODULE.build_checks(**inputs), "Mining")
        self.assertEqual(mining_check["state"], "warning")
        self.assertEqual(mining_check["reason_code"], "mining.hardware.not_configured")

    def test_missing_mining_file_is_warning_not_healthy(self):
        # A missing/unreadable bitcoin-mining.json loads as {} (see load()'s
        # except-Exception fallback). Before this fix, mining.get("warnings", [])
        # defaulted to an empty list, which is indistinguishable from "confirmed
        # zero warnings" and reported a false "healthy" state.
        inputs = dict(HEALTHY_INPUTS, mining={})
        mining_check = check(MODULE.build_checks(**inputs), "Mining")
        self.assertEqual(mining_check["state"], "warning")
        self.assertEqual(mining_check["reason_code"], "mining.unavailable")
        self.assertIn("unavailable", mining_check["detail"])

    def test_missing_telephony_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, telephony={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Telephony")["state"], "warning")

    def test_missing_messaging_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, messaging={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Messaging")["state"], "warning")

    def test_missing_inventory_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, inventory={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Inventory")["state"], "warning")

    def test_missing_network_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, network={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Network")["state"], "warning")

    def test_missing_carrier_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, carrier={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Carrier")["state"], "warning")

    def test_missing_wallet_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, wallet={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Bitcoin")["state"], "warning")

    def test_missing_security_file_is_warning(self):
        inputs = dict(HEALTHY_INPUTS, security={})
        self.assertEqual(check(MODULE.build_checks(**inputs), "Security")["state"], "warning")

    def test_high_security_memory_is_critical(self):
        inputs = dict(
            HEALTHY_INPUTS,
            security={
                "health": {"status": "healthy"},
                "engine": {"MemoryCurrent": 3 * 1024**3},
            },
        )
        security_check = check(MODULE.build_checks(**inputs), "Security")
        self.assertEqual(security_check["state"], "critical")
        self.assertEqual(security_check["reason_code"], "security.memory.critical")


if __name__ == "__main__":
    unittest.main()
