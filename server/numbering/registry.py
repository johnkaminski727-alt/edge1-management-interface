#!/usr/bin/env python3
"""
WW.CX Numbering Registry Interface

Canonical numbering intelligence layer.

Order of evaluation:
1. Normalize E.164
2. Determine country/calling code
3. Apply NANPA logic only for +1
4. Produce routing decision
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "registry"
    / "calling_codes.json"
)


DIGITS = re.compile(r"\D+")


def normalize_number(value: str) -> str:
    digits = DIGITS.sub("", value)

    if digits.startswith("00"):
        digits = digits[2:]

    return "+" + digits


def _load_calling_codes() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return []

    return json.loads(
        DATA_FILE.read_text()
    )["calling_codes"]


def lookup_country(number: str) -> dict[str, Any] | None:
    normalized = normalize_number(number)

    matches = []

    for entry in _load_calling_codes():
        if normalized.startswith(entry["calling_code"]):
            matches.append(entry)

    if not matches:
        return None

    return sorted(
        matches,
        key=lambda x: len(x["calling_code"]),
        reverse=True
    )[0]


def lookup_nanpa(number: str) -> dict[str, Any] | None:
    """
    NANPA applies only to +1 numbers.
    """

    normalized = normalize_number(number)

    if not normalized.startswith("+1"):
        return None

    digits = normalized[2:]

    if len(digits) != 10:
        return None

    npa = digits[:3]

    if npa[0] not in "23456789":
        return None

    return {
        "region": "NANPA",
        "npa": npa,
        "number": digits,
        "e164": normalized,
    }


def lookup_route(number: str) -> dict[str, Any]:

    country = lookup_country(number)

    if country and country.get("calling_code") == "+1":
        nanpa = lookup_nanpa(number)

        if nanpa:
            return {
                "route": "NANPA",
                "gateway": "kamailio-dispatcher",
                "destination": nanpa,
            }

    if country:
        return {
            "route": "COUNTRY",
            "destination": country,
        }

    return {
        "route": "UNKNOWN",
        "destination": None,
    }
