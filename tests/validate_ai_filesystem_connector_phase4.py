#!/usr/bin/env python3
"""Validate Phase 4 operator-controlled apply behavior."""

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


def cli_args(repo: Path, stage_root: Path, audit_log: Path, *args: str) -> list[str]:
    return [
        sys.executable,
        str(repo / "bin" / "bigbird-fsctl"),
        "--repo",
        str(repo),
        "--stage-root",
        str(stage_root),
        "--audit-log",
        str(audit_log),
        *args,
    ]


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    target = repo / "docs" / "ai-filesystem-write-connector" / "phase-4-smoke.md"
    existed = target.exists()
    original = target.read_text(encoding="utf-8") if existed else None

    try:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            stage_root = temp_root / "staged"
            audit_log = temp_root / "audit.jsonl"
            proposal = temp_root / "proposal.json"
            proposal.write_text(
                json.dumps(
                    {
                        "description": "Phase 4 operator-controlled apply smoke proposal",
                        "actor": "validation",
                        "changes": [
                            {
                                "path": "docs/ai-filesystem-write-connector/phase-4-smoke.md",
                                "mode": "replace",
                                "content": "# Phase 4 Smoke\n\nApplied by operator-controlled validation.\n",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            staged = run(cli_args(repo, stage_root, audit_log, "stage", "--proposal", str(proposal)), repo)
            require(staged.returncode == 0, staged.stdout)
            stage_id = json.loads(staged.stdout)["stage_id"]

            refused = run(cli_args(repo, stage_root, audit_log, "apply", stage_id, "--by", "validation"), repo)
            require(refused.returncode != 0, "apply must be refused before approval")

            approved = run(cli_args(repo, stage_root, audit_log, "approve", stage_id, "--by", "validation"), repo)
            require(approved.returncode == 0, approved.stdout)

            applied = run(cli_args(repo, stage_root, audit_log, "apply", stage_id, "--by", "validation"), repo)
            require(applied.returncode == 0, applied.stdout)
            apply_data = json.loads(applied.stdout)
            require(apply_data["ok"] is True, "apply did not report ok")
            require(target.exists(), "target file was not applied")
            require("Phase 4 Smoke" in target.read_text(encoding="utf-8"), "target content was not applied")

            stage_dir = stage_root / stage_id
            require((stage_dir / "apply.json").exists(), "apply metadata missing")
            require((stage_dir / "rollback-metadata.json").exists(), "rollback metadata missing")
            snapshot_id = apply_data["apply"]["snapshot_id"]
            require((stage_dir / "snapshots" / snapshot_id / "snapshot-manifest.json").exists(), "snapshot manifest missing")

            denied = temp_root / "denied.json"
            denied.write_text(
                json.dumps(
                    {
                        "description": "Denied secret path",
                        "changes": [
                            {
                                "path": "config/examples/token-example.txt",
                                "mode": "replace",
                                "content": "must not stage\n",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            denied_stage = run(cli_args(repo, stage_root, audit_log, "stage", "--proposal", str(denied)), repo)
            require(denied_stage.returncode != 0, "secret-looking paths must fail validation")

            audit_text = audit_log.read_text(encoding="utf-8")
            require("stage_applied" in audit_text, "apply audit event missing")

        print("AI filesystem connector Phase 4 validation passed.")
        return 0
    finally:
        if existed and original is not None:
            target.write_text(original, encoding="utf-8")
        elif target.exists():
            target.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
