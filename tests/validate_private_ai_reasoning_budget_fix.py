#!/usr/bin/env python3
"""Validate the stage-only Private AI reasoning-budget hotfix."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARER = ROOT / "tools" / "prepare_private_ai_reasoning_budget_fix.py"

spec = importlib.util.spec_from_file_location("prepare_private_ai_reasoning_budget_fix", PREPARER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load preparer: {PREPARER}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_main() -> str:
    return '''import os
APP_VERSION = "0.3.4-alpha.1"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MAX_OUTPUT_TOKENS = int(os.getenv("BB_MAX_OUTPUT_TOKENS", "2400"))
communications_warning = None

def allowed(payload):
    return REGISTRY.authorize("communications.read", payload.user.scopes)

def call_openai(payload):
    request_body = {
        "model": OPENAI_MODEL,
        "input": [],
        "instructions": "test",
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "metadata": {"request_id": "x"},
        "safety_identifier": "test",
    }
    openai_no_text = True
    return request_body
'''


def main() -> int:
    source_text = PREPARER.read_text(encoding="utf-8")
    for forbidden in (
        "requests.",
        "httpx.",
        "urllib.request",
        "subprocess",
        "os.system",
        "OPENAI_API_KEY",
        "BB_RELAY_SECRET",
    ):
        assert forbidden not in source_text, forbidden

    with tempfile.TemporaryDirectory(prefix="reasoning-budget-fix-") as raw:
        base = Path(raw)
        source = base / "source"
        output = base / "staged"
        source.mkdir()
        main_path = source / "main.py"
        original = fixture_main()
        main_path.write_text(original, encoding="utf-8")

        report = module.prepare(source, output)
        assert main_path.read_text(encoding="utf-8") == original
        assert report["mode"] == "stage_only"
        assert report["expected_version"] == "0.3.4-alpha.1"
        assert report["target_version"] == "0.3.4-alpha.2"
        assert report["default_reasoning_effort"] == "minimal"
        assert report["allowed_reasoning_efforts"] == ["minimal", "low", "medium", "high"]
        assert "output-token ceiling increase" in report["not_performed"]

        staged = (output / "main.py").read_text(encoding="utf-8")
        assert 'APP_VERSION = "0.3.4-alpha.2"' in staged
        assert 'BB_OPENAI_REASONING_EFFORT", "minimal"' in staged
        assert 'OPENAI_REASONING_EFFORT not in {"minimal", "low", "medium", "high"}' in staged
        assert '"reasoning": {"effort": OPENAI_REASONING_EFFORT}' in staged
        assert 'MAX_OUTPUT_TOKENS = int(os.getenv("BB_MAX_OUTPUT_TOKENS", "2400"))' in staged
        compile(staged, "main.py", "exec")

        try:
            module.prepare(source, source)
        except module.HotfixError:
            pass
        else:
            raise AssertionError("preparer accepted in-place output")

        wrong = base / "wrong"
        wrong.mkdir()
        (wrong / "main.py").write_text(original.replace("0.3.4-alpha.1", "0.3.3-alpha.1"), encoding="utf-8")
        try:
            module.prepare(wrong, base / "wrong-out")
        except module.HotfixError:
            pass
        else:
            raise AssertionError("preparer accepted unexpected gateway version")

    print("private AI reasoning-budget hotfix validator passed")
    print("PASS stage-only non-mutation")
    print("PASS 0.3.4-alpha.1 -> 0.3.4-alpha.2 version gate")
    print("PASS minimal default reasoning effort")
    print("PASS configurable minimal/low/medium/high effort validation")
    print("PASS provider payload reasoning field")
    print("PASS output-token ceiling unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
