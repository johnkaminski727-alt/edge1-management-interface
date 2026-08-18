#!/usr/bin/env python3
"""Run focused authenticated SNMP Operations Console unit/static regressions in CI."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_edge1_snmp_ui_client import SnmpUiClientTests
from tests.test_snmp_operations_console import SnmpOperationsConsoleStaticTests


def validate_embedded_javascript() -> None:
    source = Path("src/web/operations-center/snmp.html").read_text(encoding="utf-8")
    if source.count("<script>") != 1 or source.count("</script>") != 1:
        raise RuntimeError("SNMP console script template shape is invalid")
    script = source.split("<script>", 1)[1].split("</script>", 1)[0]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as handle:
        handle.write(script)
        handle.flush()
        completed = subprocess.run(
            ["node", "--check", handle.name],
            text=True,
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "JavaScript syntax validation failed")[-4000:])


def main() -> int:
    validate_embedded_javascript()
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(SnmpUiClientTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(SnmpOperationsConsoleStaticTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
