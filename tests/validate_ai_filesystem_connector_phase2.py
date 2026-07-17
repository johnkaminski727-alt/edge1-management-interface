#!/usr/bin/env python3
"""Validate the Phase 2 staged-only filesystem connector behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    cli = repo / "bin" / "bigbird-fsctl"
    require(cli.exists(), "bin/bigbird-fsctl is missing")

    with tempfile.TemporaryDirectory() as temp:
        temp_root = Path(temp)
        stage_root = temp_root / "staged"
        audit_log = temp_root / "audit.jsonl"
        proposal = temp_root / "proposal.json"
        proposal.write_text(
            json.dumps(
                {
                    "description": "Phase 2 smoke proposal",
                    "actor": "validation",
                    "changes": [
                        {
                            "path": "docs/ai-filesystem-write-connector/phase-2-smoke.md",
                            "mode": "replace",
                            "content": "# Phase 2 Smoke\n\nThis file is staged only.\n",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        staged = run(
            [
                sys.executable,
                str(cli),
                "--repo",
                str(repo),
                "--stage-root",
                str(stage_root),
                "--audit-log",
                str(audit_log),
                "stage",
                "--proposal",
                str(proposal),
            ],
            repo,
        )
        require(staged.returncode == 0, staged.stdout)
        stage_id = json.loads(staged.stdout)["stage_id"]
        require((stage_root / stage_id / "manifest.json").exists(), "manifest was not created")
        require((stage_root / stage_id / "diff.patch").exists(), "diff was not created")
        require(audit_log.exists(), "audit log was not created")

        diffed = run(
            [
                sys.executable,
                str(cli),
                "--repo",
                str(repo),
                "--stage-root",
                str(stage_root),
                "--audit-log",
                str(audit_log),
                "diff",
                stage_id,
            ],
            repo,
        )
        require(diffed.returncode == 0, diffed.stdout)
        require("phase-2-smoke.md" in diffed.stdout, "diff did not include staged path")

        listed = run(
            [
                sys.executable,
                str(cli),
                "--repo",
                str(repo),
                "--stage-root",
                str(stage_root),
                "--audit-log",
                str(audit_log),
                "list",
            ],
            repo,
        )
        require(listed.returncode == 0, listed.stdout)
        require(stage_id in listed.stdout, "list did not include staged proposal")

        forbidden = run([sys.executable, str(cli), "apply", stage_id], repo)
        require(forbidden.returncode != 0, "apply command must not exist in Phase 2")

    print("AI filesystem connector Phase 2 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
