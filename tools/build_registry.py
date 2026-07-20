#!/usr/bin/env python3
"""Build canonical Edge1 geographic registry artifacts.

This generator is intentionally source-driven. Authoritative source imports can
be added without changing consumers of the generated registry files.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "registry"


def load(name):
    with (REGISTRY / name).open() as handle:
        return json.load(handle)


def validate():
    countries = load("countries.json")
    seen = set()
    for