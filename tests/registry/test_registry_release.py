#!/usr/bin/env python3

import json
import re
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
EXPECTED_ISO_COUNT = 249
EXPECTED_UNASSIGNED_CALLING_CODES = {"AQ", "BV", "GS", "HM", "PN", "TF", "UM"}
EXPECTED_UNASSIGNED_TIMEZONES = {"BV", "HM"}


def load(name):
    with (REGISTRY / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class RegistryReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load("country_registry.json")
        cls.countries = cls.registry["countries"]
        cls.by_iso = {country["iso_alpha2"]: country for country in cls.countries}

    def test_complete_iso_3166_coverage(self):
        self.assertEqual(EXPECTED_ISO_COUNT, len(self.countries))
        self.assertEqual(EXPECTED_ISO_COUNT, len(self.by_iso))

    def test_required_country_fields(self):
        for country in self.countries:
            with self.subTest(country=country.get("iso_alpha2")):
                self.assertRegex(country["iso_alpha2"], r"^[A-Z]{2}$")
                self.assertRegex(country["iso_alpha3"], r"^[A-Z]{3}$")
                self.assertTrue(country["name"])
                self.assertRegex(country["currency"], r"^[A-Z]{3}$")

    def test_calling_codes_are_normalized(self):
        missing = set()
        for country in self.countries:
            codes = country["calling_codes"]
            if not codes:
                missing.add(country["iso_alpha2"])
            for code in codes:
                self.assertRegex(code, r"^\+[1-9][0-9]{0,2}$")
        self.assertEqual(EXPECTED_UNASSIGNED_CALLING_CODES, missing)

    def test_timezones_are_valid_iana_identifiers(self):
        missing = set()
        for country in self.countries:
            zones = country["timezones"]
            if not zones:
                missing.add(country["iso_alpha2"])
            for zone in zones:
                try:
                    ZoneInfo(zone)
                except ZoneInfoNotFoundError as exc:
                    self.fail(f"Unknown IANA timezone {zone}: {exc}")
        self.assertEqual(EXPECTED_UNASSIGNED_TIMEZONES, missing)

    def test_registry_is_sorted(self):
        codes = [country["iso_alpha2"] for country in self.countries]
        self.assertEqual(sorted(codes), codes)

    def test_source_standards_are_declared(self):
        declared = set(self.registry["source_standards"])
        self.assertTrue({"ISO 3166", "ITU E.164", "IANA TZDB", "ISO 4217"} <= declared)


if __name__ == "__main__":
    unittest.main()
