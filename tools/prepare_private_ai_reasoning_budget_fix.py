#!/usr/bin/env python3
"""Stage, but never apply, the Private AI reasoning-budget hotfix.

The hotfix advances an accepted 0.3.4-alpha.1 gateway source tree to
0.3.4-alpha.2. It makes Responses API reasoning effort explicit and configurable
so reasoning tokens cannot silently inherit the model's higher default effort.

This tool only reads main.py, validates the known baseline, writes a patched copy
to a separate output directory, compiles the staged source, and emits a hash
report. It does not import the gateway, read environment values, contact a model
provider, contact the Communications Relay, or modify/restart the live service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_VERSION = "0.3.4-alpha.1"
TARGET_VERSION = "0.3.4-alpha.2"
DEFAULT_REASONING_EFFORT = "minimal"
ALLOWED_REASONING_EFFORTS = ("minimal", "low", "medium", "high")


class HotfixError(RuntimeError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise HotfixError(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


def replace_one_of(text: str, replacements: list[tuple[str, str]], label: str) -> str:
    matches = [(old, new) for old, new in replacements if old in text]
    if len(matches) != 1:
        raise HotfixError(f"{label}: expected exactly one supported marker, found {len(matches)}")
    old, new = matches[0]
    return replace_once(text, old, new, label)


def patch_main(text: str) -> str:
    if f'APP_VERSION = "{EXPECTED_VERSION}"' not in text:
        raise HotfixError(f"expected gateway version {EXPECTED_VERSION}")

    for marker in (
        "OPENAI_MODEL",
        "MAX_OUTPUT_TOKENS",
        "max_output_tokens",
        "openai_no_text",
        "communications_warning",
        'REGISTRY.authorize("communications.read", payload.user.scopes)',
    ):
        if marker not in text:
            raise HotfixError(f"baseline marker missing: {marker}")

    text = replace_once(
        text,
        f'APP_VERSION = "{EXPECTED_VERSION}"',
        f'APP_VERSION = "{TARGET_VERSION}"',
        "gateway version",
    )

    reasoning_config = (
        'OPENAI_REASONING_EFFORT = os.getenv("BB_OPENAI_REASONING_EFFORT", "minimal").strip().lower()\n'
        'if OPENAI_REASONING_EFFORT not in {"minimal", "low", "medium", "high"}:\n'
        '    raise RuntimeError("BB_OPENAI_REASONING_EFFORT must be one of: minimal, low, medium, high")\n'
    )

    text = replace_one_of(
        text,
        [
            (
                'MAX_OUTPUT_TOKENS = int(os.getenv("BB_MAX_OUTPUT_TOKENS", "2400"))\n',
                'MAX_OUTPUT_TOKENS = int(os.getenv("BB_MAX_OUTPUT_TOKENS", "2400"))\n' + reasoning_config,
            ),
            (
                "MAX_OUTPUT_TOKENS = int(os.getenv('BB_MAX_OUTPUT_TOKENS', '2400'))\n",
                "MAX_OUTPUT_TOKENS = int(os.getenv('BB_MAX_OUTPUT_TOKENS', '2400'))\n" + reasoning_config,
            ),
        ],
        "reasoning configuration anchor",
    )

    text = replace_one_of(
        text,
        [
            (
                '        "max_output_tokens": MAX_OUTPUT_TOKENS,\n',
                '        "max_output_tokens": MAX_OUTPUT_TOKENS,\n'
                '        "reasoning": {"effort": OPENAI_REASONING_EFFORT},\n',
            ),
            (
                "        'max_output_tokens': MAX_OUTPUT_TOKENS,\n",
                "        'max_output_tokens': MAX_OUTPUT_TOKENS,\n"
                "        'reasoning': {'effort': OPENAI_REASONING_EFFORT},\n",
            ),
        ],
        "provider reasoning payload",
    )

    required = (
        f'APP_VERSION = "{TARGET_VERSION}"',
        'BB_OPENAI_REASONING_EFFORT", "minimal"',
        'OPENAI_REASONING_EFFORT not in {"minimal", "low", "medium", "high"}',
        '"reasoning": {"effort": OPENAI_REASONING_EFFORT}',
        "communications_warning",
        'REGISTRY.authorize("communications.read", payload.user.scopes)',
    )
    for marker in required:
        if marker not in text:
            raise HotfixError(f"patched main missing required marker: {marker}")

    compile(text, "main.py", "exec")
    return text


def prepare(source_root: Path, output_root: Path) -> dict[str, object]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()

    if source_root == output_root:
        raise HotfixError("output root must differ from source root")
    if source_root in output_root.parents:
        raise HotfixError("output root must not be inside the source tree")
    if output_root.exists() and any(output_root.iterdir()):
        raise HotfixError("output root must be absent or empty")

    main_path = source_root / "main.py"
    if not main_path.is_file():
        raise HotfixError(f"required source file missing: {main_path}")

    before = main_path.read_text(encoding="utf-8")
    after = patch_main(before)

    output_root.mkdir(parents=True, exist_ok=True)
    staged_main = output_root / "main.py"
    staged_main.write_text(after, encoding="utf-8")

    report: dict[str, object] = {
        "schema_version": 1,
        "mode": "stage_only",
        "source_root": str(source_root),
        "expected_version": EXPECTED_VERSION,
        "target_version": TARGET_VERSION,
        "default_reasoning_effort": DEFAULT_REASONING_EFFORT,
        "allowed_reasoning_efforts": list(ALLOWED_REASONING_EFFORTS),
        "files": {
            "main.py": {
                "before_sha256": sha256_text(before),
                "after_sha256": sha256_text(after),
            }
        },
        "changes": [
            "explicit configurable Responses API reasoning effort",
            "minimal default reasoning effort for bounded retrieval synthesis",
            "fail-closed validation of supported pre-GPT-5.1 reasoning effort values",
            "gateway version 0.3.4-alpha.2",
        ],
        "not_performed": [
            "live source mutation",
            "environment value inspection",
            "credential access",
            "model-provider request",
            "Communications Relay request",
            "service restart",
            "deployment",
            "output-token ceiling increase",
        ],
    }
    (output_root / "hotfix-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source_root, args.output_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
