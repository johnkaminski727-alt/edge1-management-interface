#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "portal"))

from carrier_operational import (  # noqa: E402
    PortalIdentity,
    carrier_scope,
    identity_from_config,
    operational_response,
)


class CarrierOperationalTests(unittest.TestCase):
    def test_identity