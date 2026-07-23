#!/usr/bin/env python3
"""Execute CX Admin navigation discovery checks in repository CI."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "cx_admin" / "discover_navigation.py"
SPEC = importlib.util.spec_from_file_location("discover_navigation", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"unable to load navigation discovery module: {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        operations = root / "bigbird-operations-console.php"
        operations.write_text(
            "<html><title>BigBird Operations Console</title><body><main></main></body></html>",
            encoding="utf-8",
        )
        record = MODULE.inspect_page(root, operations, "/admin")
        assert record["route"] == "/admin/bigbird-operations-console.php"
        assert record["title"] == "BigBird Operations Console"
        assert record["navigable_candidate"] is True

        api_page = root / "api" / "status.php"
        api_page.parent.mkdir()
        api_page.write_text("<?php echo json_encode(['ok' => true]);", encoding="utf-8")
        api_record = MODULE.inspect_page(root, api_page, "/admin")
        assert api_record["navigable_candidate"] is False
        assert "excluded implementation directory" in api_record["exclusion_reasons"]

    print("CX Admin navigation discovery validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
