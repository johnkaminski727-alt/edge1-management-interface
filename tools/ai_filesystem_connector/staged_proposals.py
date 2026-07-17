#!/usr/bin/env python3
"""Staged proposal intake for the Edge1 AI filesystem connector.

Phase 3 adds operator approval metadata for staged proposals.
There is still no apply, rollback, or production write path in this module.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ALLOWED_PREFIXES = ("docs/", "registers/")
DEFAULT_STAGE_ROOT = Path("/var/lib/edge1-ai-fs-connector/staged")
DEFAULT_AUDIT_LOG = Path("/var/log/edge1-ai-fs-connector/audit.jsonl")
MAX_TEXT_BYTES = 512 * 1024
SCRIPT_SUFFIXES = {
    ".bash",
    ".cgi",
    ".conf",
    ".env",
    ".ini",
    ".js",
    ".php",
    ".pl",
    ".ps1",
    ".py",
    ".rb",
    ".service",
    ".sh",
    ".timer",
    ".toml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    audit_log: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("proposal must be a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_audit(paths: Paths, event: str, payload: dict[str, Any]) -> None:
    record = {
        "ts": utc_now(),
        "event": event,
        "phase": "phase3-operator-approval-metadata",
        **payload,
    }
    paths.audit_log.parent.mkdir(parents=True, exist_ok=True)
    with paths.audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def allowed_prefixes(proposal: dict[str, Any]) -> tuple[str, ...]:
    policy = proposal.get("policy", {})
    prefixes = policy.get("allowed_prefixes") if isinstance(policy, dict) else None
    if not prefixes:
        prefixes = DEFAULT_ALLOWED_PREFIXES
    normalized: list[str] = []
    for prefix in prefixes:
        if not isinstance(prefix, str):
            continue
        cleaned = prefix.strip().lstrip("/")
        if cleaned and not cleaned.endswith("/"):
            cleaned += "/"
        if cleaned:
            normalized.append(cleaned)
    return tuple(normalized or DEFAULT_ALLOWED_PREFIXES)


def is_allowed_relative_path(relative: str, prefixes: tuple[str, ...]) -> bool:
    normalized = relative.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in prefixes)


def has_symlink_parent(repo: Path, relative: str) -> bool:
    current = repo
    for part in Path(relative).parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    target = repo / relative
    return target.exists() and target.is_symlink()


def validate_change(repo: Path, change: dict[str, Any], prefixes: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    raw_path = change.get("path")
    content = change.get("content")
    mode = change.get("mode", "replace")
    allow_executable = bool(change.get("allow_executable", False))

    if not isinstance(raw_path, str) or not raw_path.strip():
        return ["change path must be a non-empty string"]

    relative = raw_path.strip().replace("\\", "/")
    path_obj = Path(relative)
    if path_obj.is_absolute():
        errors.append(f"{relative}: absolute paths are rejected")
    if ".." in path_obj.parts:
        errors.append(f"{relative}: parent traversal is rejected")
    if not is_allowed_relative_path(relative, prefixes):
        errors.append(f"{relative}: outside allowed prefixes {', '.join(prefixes)}")
    if has_symlink_parent(repo, relative):
        errors.append(f"{relative}: symlink targets or symlink parents are rejected")
    if mode not in {"create", "replace"}:
        errors.append(f"{relative}: mode must be create or replace")
    if not isinstance(content, str):
        errors.append(f"{relative}: content must be UTF-8 text")
    else:
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_TEXT_BYTES:
            errors.append(f"{relative}: content exceeds {MAX_TEXT_BYTES} bytes")
        if "\x00" in content:
            errors.append(f"{relative}: binary-looking NUL content is rejected")
    if path_obj.suffix.lower() in SCRIPT_SUFFIXES and not allow_executable:
        errors.append(f"{relative}: script/config style changes require explicit review")
    if mode == "create" and (repo / relative).exists():
        errors.append(f"{relative}: create mode target already exists")
    return errors


def validate_proposal(repo: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    changes = proposal.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("proposal changes must be a non-empty list")
        changes = []

    prefixes = allowed_prefixes(proposal)
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"change {index}: each change must be an object")
            continue
        errors.extend(validate_change(repo, change, prefixes))

    return {
        "ok": not errors,
        "checked_at": utc_now(),
        "allowed_prefixes": list(prefixes),
        "errors": errors,
    }


def change_diff(repo: Path, change: dict[str, Any]) -> str:
    relative = change["path"].strip().replace("\\", "/")
    target = repo / relative
    old_text = target.read_text(encoding="utf-8") if target.exists() else ""
    new_text = change["content"]
    return "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )


def render_diff(repo: Path, proposal: dict[str, Any]) -> str:
    chunks: list[str] = []
    for change in proposal.get("changes", []):
        if isinstance(change, dict) and isinstance(change.get("path"), str):
            chunks.append(change_diff(repo, change))
    return "\n".join(chunk for chunk in chunks if chunk).rstrip() + "\n"


def stage_proposal(paths: Paths, proposal_path: Path) -> dict[str, Any]:
    proposal = load_json(proposal_path)
    validation = validate_proposal(paths.repo, proposal)
    stage_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    stage_dir = paths.stage_root / stage_id
    proposed_dir = stage_dir / "proposed"
    stage_dir.mkdir(parents=True, exist_ok=False)

    for change in proposal.get("changes", []):
        if not isinstance(change, dict):
            continue
        relative = str(change.get("path", "")).strip().replace("\\", "/")
        content = change.get("content")
        if relative and isinstance(content, str):
            output = proposed_dir / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")

    diff_text = render_diff(paths.repo, proposal)
    (stage_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    write_json(stage_dir / "validation.json", validation)

    manifest = {
        "stage_id": stage_id,
        "created_at": utc_now(),
        "repo": str(paths.repo),
        "proposal_source": str(proposal_path),
        "proposal_sha256": sha256_text(json.dumps(proposal, sort_keys=True)),
        "phase_boundary": {
            "production_apply": False,
            "root_apply_service": False,
            "automatic_approval": False,
            "rollback_execution": False,
            "operator_approval_metadata": True,
        },
        "validation_ok": validation["ok"],
        "approval_status": "pending_review",
        "proposal": proposal,
    }
    write_json(stage_dir / "manifest.json", manifest)
    append_audit(
        paths,
        "stage_created",
        {
            "stage_id": stage_id,
            "proposal_source": str(proposal_path),
            "validation_ok": validation["ok"],
            "change_count": len(proposal.get("changes", [])),
        },
    )
    return manifest


def find_stage(stage_root: Path, stage_id: str) -> Path:
    stage_dir = stage_root / stage_id
    if not stage_dir.is_dir():
        raise FileNotFoundError(f"stage not found: {stage_id}")
    return stage_dir


def load_manifest(stage_dir: Path) -> dict[str, Any]:
    return load_json(stage_dir / "manifest.json")


def write_manifest(stage_dir: Path, manifest: dict[str, Any]) -> None:
    write_json(stage_dir / "manifest.json", manifest)


def approval_payload(status: str, operator: str, note: str | None) -> dict[str, Any]:
    payload = {
        "status": status,
        "operator": operator,
        "recorded_at": utc_now(),
        "phase_boundary": {
            "production_apply": False,
            "root_apply_service": False,
            "automatic_approval": False,
            "rollback_execution": False,
        },
    }
    if note:
        payload["note"] = note
    return payload


def set_approval_status(paths: Paths, stage_id: str, status: str, operator: str, note: str | None) -> dict[str, Any]:
    if not operator.strip():
        raise ValueError("operator name is required")
    stage_dir = find_stage(paths.stage_root, stage_id)
    manifest = load_manifest(stage_dir)
    if status == "approved" and not bool(manifest.get("validation_ok")):
        raise ValueError("cannot approve a staged proposal that failed validation")

    payload = approval_payload(status, operator.strip(), note)
    write_json(stage_dir / "approval.json", payload)
    manifest["approval_status"] = status
    manifest["approval_recorded_at"] = payload["recorded_at"]
    manifest["approval_operator"] = payload["operator"]
    write_manifest(stage_dir, manifest)
    append_audit(
        paths,
        f"stage_{status}",
        {"stage_id": stage_id, "operator": payload["operator"], "has_note": bool(note)},
    )
    return {"ok": True, "stage_id": stage_id, "approval": payload}


def command_stage(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    manifest = stage_proposal(paths, Path(args.proposal).resolve())
    print(json.dumps({"ok": True, "stage_id": manifest["stage_id"], "validation_ok": manifest["validation_ok"]}, indent=2))
    return 0 if manifest["validation_ok"] else 1


def command_list(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for manifest_path in sorted(paths.stage_root.glob("*/manifest.json")):
        manifest = load_json(manifest_path)
        rows.append(
            {
                "stage_id": manifest.get("stage_id"),
                "created_at": manifest.get("created_at"),
                "validation_ok": manifest.get("validation_ok"),
                "approval_status": manifest.get("approval_status", "unknown"),
                "description": manifest.get("proposal", {}).get("description", ""),
            }
        )
    append_audit(paths, "stage_listed", {"count": len(rows)})
    print(json.dumps({"ok": True, "stages": rows}, indent=2))
    return 0


def command_show(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    stage_dir = find_stage(paths.stage_root, args.stage_id)
    manifest = load_manifest(stage_dir)
    append_audit(paths, "stage_shown", {"stage_id": args.stage_id})
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def command_diff(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    stage_dir = find_stage(paths.stage_root, args.stage_id)
    append_audit(paths, "stage_diff_viewed", {"stage_id": args.stage_id})
    print((stage_dir / "diff.patch").read_text(encoding="utf-8"), end="")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    stage_dir = find_stage(paths.stage_root, args.stage_id)
    manifest = load_manifest(stage_dir)
    validation = validate_proposal(paths.repo, manifest["proposal"])
    write_json(stage_dir / "validation.json", validation)
    manifest["validation_ok"] = validation["ok"]
    manifest["validated_at"] = validation["checked_at"]
    if not validation["ok"] and manifest.get("approval_status") == "approved":
        manifest["approval_status"] = "pending_review"
        manifest["approval_reset_reason"] = "validation_failed_after_recheck"
    write_manifest(stage_dir, manifest)
    append_audit(paths, "stage_validated", {"stage_id": args.stage_id, "validation_ok": validation["ok"]})
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0 if validation["ok"] else 1


def command_approve(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    result = set_approval_status(paths, args.stage_id, "approved", args.by, args.note)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_reject(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    result = set_approval_status(paths, args.stage_id, "rejected", args.by, args.reason)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_status(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    stage_dir = find_stage(paths.stage_root, args.stage_id)
    manifest = load_manifest(stage_dir)
    approval_path = stage_dir / "approval.json"
    approval = load_json(approval_path) if approval_path.exists() else None
    append_audit(paths, "stage_status_viewed", {"stage_id": args.stage_id})
    print(
        json.dumps(
            {
                "ok": True,
                "stage_id": args.stage_id,
                "validation_ok": manifest.get("validation_ok"),
                "approval_status": manifest.get("approval_status", "unknown"),
                "approval": approval,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def make_paths(args: argparse.Namespace) -> Paths:
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"repo does not exist: {repo}")
    stage_root = Path(args.stage_root or os.environ.get("EDGE1_AI_FS_STAGE_ROOT") or DEFAULT_STAGE_ROOT).resolve()
    audit_log = Path(args.audit_log or os.environ.get("EDGE1_AI_FS_AUDIT_LOG") or DEFAULT_AUDIT_LOG).resolve()
    return Paths(repo=repo, stage_root=stage_root, audit_log=audit_log)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bigbird-fsctl",
        description="Edge1 AI filesystem connector staged proposal intake and approval metadata.",
    )
    parser.add_argument("--repo", default=".", help="Target repository used for validation and diff context.")
    parser.add_argument("--stage-root", help="Staging root. Defaults to EDGE1_AI_FS_STAGE_ROOT or /var/lib.")
    parser.add_argument("--audit-log", help="Audit JSONL path. Defaults to EDGE1_AI_FS_AUDIT_LOG or /var/log.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage = subparsers.add_parser("stage", help="Stage a proposal JSON file.")
    stage.add_argument("--proposal", required=True, help="Path to proposal JSON.")
    stage.set_defaults(func=command_stage)

    list_cmd = subparsers.add_parser("list", help="List staged proposals.")
    list_cmd.set_defaults(func=command_list)

    show = subparsers.add_parser("show", help="Show a staged proposal manifest.")
    show.add_argument("stage_id")
    show.set_defaults(func=command_show)

    diff = subparsers.add_parser("diff", help="Print a staged proposal diff.")
    diff.add_argument("stage_id")
    diff.set_defaults(func=command_diff)

    validate = subparsers.add_parser("validate", help="Re-run staged proposal validation.")
    validate.add_argument("stage_id")
    validate.set_defaults(func=command_validate)

    status = subparsers.add_parser("status", help="Show validation and approval status for a staged proposal.")
    status.add_argument("stage_id")
    status.set_defaults(func=command_status)

    approve = subparsers.add_parser("approve", help="Record operator approval metadata for a staged proposal.")
    approve.add_argument("stage_id")
    approve.add_argument("--by", required=True, help="Operator name or identifier.")
    approve.add_argument("--note", help="Optional approval note.")
    approve.set_defaults(func=command_approve)

    reject = subparsers.add_parser("reject", help="Record operator rejection metadata for a staged proposal.")
    reject.add_argument("stage_id")
    reject.add_argument("--by", required=True, help="Operator name or identifier.")
    reject.add_argument("--reason", help="Optional rejection reason.")
    reject.set_defaults(func=command_reject)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
