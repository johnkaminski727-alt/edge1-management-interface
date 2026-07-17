#!/usr/bin/env python3
"""Validate the Phase 3 approval-metadata filesystem connector behavior."""

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
                    "description": "Phase 3 approval metadata smoke proposal",
                    "actor": "validation",
                    "changes": [
                        {
                            "path": "docs/ai-filesystem-write-connector/phase-3-smoke.md",
                            "mode": "replace",
                            "content": "# Phase 3 Smoke\n\nThis file is staged and approval-marked only.\n",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        staged = run(cli_args(repo, stage_root, audit_log, "stage", "--proposal", str(proposal)), repo)
        require(staged.returncode == 0, staged.stdout)
        stage_id = json.loads(staged.stdout)["stage_id"]
        manifest_path = stage_root / stage_id / "manifest.json"
        require(manifest_path.exists(), "manifest was not created")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest["approval_status"] == "pending_review", "new stage should be pending_review")

        approved = run(
            cli_args(repo, stage_root, audit_log, "approve", stage_id, "--by", "validation", "--note", "smoke"),
            repo,
        )
        require(approved.returncode == 0, approved.stdout)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest["approval_status"] == "approved", "stage was not marked approved")
        require((stage_root / stage_id / "approval.json").exists(), "approval record was not created")

        status = run(cli_args(repo, stage_root, audit_log, "status", stage_id), repo)
        require(status.returncode == 0, status.stdout)
        status_data = json.loads(status.stdout)
        require(status_data["approval_status"] == "approved", "status did not report approval")

        rejected = run(
            cli_args(repo, stage_root, audit_log, "reject", stage_id, "--by", "validation", "--reason", "smoke reset"),
            repo,
        )
        require(rejected.returncode == 0, rejected.stdout)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest["approval_status"] == "rejected", "stage was not marked rejected")

        audit_text = audit_log.read_text(encoding="utf-8")
        require("stage_approved" in audit_text, "approval audit event missing")
        require("stage_rejected" in audit_text, "rejection audit event missing")

        forbidden = run(cli_args(repo, stage_root, audit_log, "apply", stage_id), repo)
        require(forbidden.returncode != 0, "apply command must not exist in Phase 3")

    print("AI filesystem connector Phase 3 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
