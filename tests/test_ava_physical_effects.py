#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "ava_physical_effects.py"

SPEC = importlib.util.spec_from_file_location("ava_physical_effects", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
effects = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = effects
SPEC.loader.exec_module(effects)


class AvaPhysicalEffectsTests(unittest.TestCase):
    def test_physical_effects_are_disabled_by_default(self) -> None:
        self.assertIs(effects.PHYSICAL_EFFECTS_ENABLED, False)

    def test_exact_semantic_allowlist(self) -> None:
        self.assertEqual(
            effects.ALLOWED_PRESENTATION_EFFECTS,
            {
                "blue_tit_easter_egg",
                "donkey_easter_egg",
                "cat_easter_egg",
                "moist_owlette_easter_egg",
            },
        )

    def test_catalogue_is_fixed_and_complete(self) -> None:
        self.assertEqual(
            effects.PHYSICAL_EFFECT_CATALOGUE,
            {
                "blue_tit_easter_egg": "blue_tit_chirp",
                "donkey_easter_egg": "donkey_braying",
                "cat_easter_egg": "cat_meow",
                "moist_owlette_easter_egg": "moist_owlette_hoot",
            },
        )

    def test_disabled_policy_returns_no_execution_authority(self) -> None:
        decision = effects.decide(
            "request-physical-test-0001",
            "donkey_easter_egg",
        )
        self.assertFalse(decision.enabled)
        self.assertEqual(decision.disposition, "disabled")
        self.assertEqual(decision.catalogue_effect, "donkey_braying")

    def test_explicit_enable_only_approves_fixed_catalogue_entry(self) -> None:
        decision = effects.decide(
            "request-physical-test-0002",
            "cat_easter_egg",
            enabled=True,
        )
        self.assertTrue(decision.enabled)
        self.assertEqual(decision.disposition, "approved")
        self.assertEqual(decision.catalogue_effect, "cat_meow")

    def test_unknown_effect_fails_closed(self) -> None:
        with self.assertRaises(effects.PhysicalEffectPolicyError):
            effects.decide(
                "request-physical-test-0003",
                "run_arbitrary_command",
                enabled=True,
            )

    def test_bad_request_identifier_fails_closed(self) -> None:
        for bad in ("", "../event4", "x", " " * 20):
            with self.subTest(request_id=bad):
                with self.assertRaises(effects.PhysicalEffectPolicyError):
                    effects.decide(
                        bad,
                        "blue_tit_easter_egg",
                        enabled=True,
                    )

    def test_module_contains_no_hardware_or_shell_primitive(self) -> None:
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
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
