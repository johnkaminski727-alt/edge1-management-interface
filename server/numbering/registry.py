#!/usr/bin/env python3
"""
WW.CX Numbering Registry

Canonical lookup layer:
- E.164 normalization
- country lookup
- NANPA lookup
- routing decisions
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

REGISTRY = ROOT / "data" / "registry"
DB = ROOT / "data" / "telecom" / "numbering.db"

DIGITS = re.compile(r"\D+")


def normalize_number(value: str) -> str:
    digits = DIGITS.sub("", value)

    if digits.startswith("00"):
        digits = digits[2:]

    return "+" + digits


def load_json(name: str) -> dict[str, Any]:
    return json.loads(
        (REGISTRY / name).read_text()
    )


def lookup_country(number: str):

    number = normalize_number(number)

    data = load_json("countries.json")

    matches = []

    for country in data["countries"]:
        for code in country["calling_codes"]:
            if number.startswith(code):
                matches.append(country)

    if not matches:
        return None

    return sorted(
        matches,
        key=lambda x: len(
            ",".join(x["calling_codes"])
        ),
        reverse=True
    )[0]


def lookup_nanpa(number: str):

    normalized = normalize_number(number)

    if not normalized.startswith("+1"):
        return None

    digits = normalized[2:]

    if len(digits) != 10:
        return None

    npa = digits[:3]

    with sqlite3.connect(DB) as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute(
            """
            SELECT *
            FROM nanpa_npa
            WHERE npa=?
            """,
            (npa,)
        ).fetchone()

    if not row:
        return {
            "npa": npa,
            "status": "unknown"
        }

    return dict(row)


def lookup_route(number: str):

    normalized = normalize_number(number)

    # NANPA must override +1 ambiguity
    if normalized.startswith("+1"):

        nanpa = lookup_nanpa(normalized)

        if nanpa and nanpa.get("country"):

            country_code = nanpa["country"]

            data = load_json("countries.json")

            country = next(
                (
                    c for c in data["countries"]
                    if c["iso_alpha2"] == country_code
                ),
                None
            )

            return {
                "route": "NANPA",
                "country": country,
                "numbering": nanpa,
                "gateway": "kamailio-dispatcher"
            }

        return {
            "route": "NANPA",
            "country": None,
            "numbering": nanpa,
            "gateway": "kamailio-dispatcher"
        }


    country = lookup_country(normalized)

    if country:

        return {
            "route": "COUNTRY",
            "country": country
        }


    return {
        "route": "UNKNOWN",
        "country": None
    }
