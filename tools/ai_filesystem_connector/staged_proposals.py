#!/usr/bin/env python3
"""Staged proposal intake for the Edge1 AI filesystem connector.

Phase 4 adds operator-controlled apply for approved staged proposals only.
There is no automatic approval, AI-initiated apply path, root-owned apply
service, or rollback execution in this module.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ALLOWED_PREFIXES = (
    "docs/",
    "registers/",
    "tests/",
    "tools/handoff/",
    "tools/ai_filesystem_connector/",
    "server/",
    "src/web/",
    "bin/",
    "config/examples/",
)
DEFAULT_DENY_GLOBS = (
    ".env",
    "*.env",
    "*.key",
    "*.pem",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*secret*",
    "*token*",
    "*credential*",
    "*password*",
    "config/private*",
    ".git/*",
    "*.service",
    "*.timer",
)
DEFAULT_STAGE_ROOT = Path("/var/lib/edge1-ai-fs-connector/staged")
DEFAULT_AUDIT_LOG = Path("/var/log/edge1-ai-fs-connector/audit.jsonl")
MAX_TEXT_BYTES = 512 * 1024
SCRIPT_SUFFIXES = {
    ".bash",
    ".cgi",
    ".js",
    ".php",
    ".pl",
    ".ps1",
    ".py",
    ".rb",
    ".sh",
}
CONFIG_SUFFIXES = {
    ".conf",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    audit_log: Path
    policy_config: Path | None = None


@dataclass(frozen=True)
class Policy:
    allowed_prefixes: tuple[str, ...]
    deny_globs: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_audit(paths: Paths, event: str, payload: dict[str, Any]) -> None:
    record = {
        "ts": utc_now(),
        "event": event,
        "phase": "phase4-operator-controlled-apply",
        **payload,
    }
    paths.audit_log.parent.mkdir(parents=True, exist_ok=True)
    with paths.audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def normalize_prefix(prefix: str) -> str:
    cleaned = prefix.strip().replace("\\", "/").lstrip("/")
    if cleaned and not cleaned.endswith("/"):
        cleaned += "/"
    return cleaned


def normalize_relative_path(raw_path: str) -> str:
    return raw_path.strip().replace("\\", "/").lstrip("/")


def load_policy(paths: Paths, proposal: dict[str, Any] | None = None) -> Policy:
    configured: dict[str, Any] = {}
    if paths.policy_config and paths.policy_config.exists():
        configured = load_json(paths.policy_config)

    allowed_source = configured.get("allowed_prefixes") or DEFAULT_ALLOWED_PREFIXES
    allowed_prefixes = tuple(
        prefix for prefix in (normalize_prefix(str(value)) for value in allowed_source) if prefix
    )
    deny_source = configured.get("deny_globs") or DEFAULT_DENY_GLOBS
    deny_globs = tuple(str(value).strip().replace("\\", "/").lstrip("/") for value in deny_source if str(value).strip())

    if proposal:
        requested = proposal.get("policy", {}).get("allowed_prefixes") if isinstance(proposal.get("policy"), dict) else None
        if requested:
            narrowed: list[str] = []
            for value in requested:
                prefix = normalize_prefix(str(value))
                if prefix and any(prefix.startswith(allowed) for allowed in allowed_prefixes):
                    narrowed.append(prefix)
            if narrowed:
                allowed_prefixes = tuple(narrowed)

    return Policy(allowed_prefixes=allowed_prefixes or DEFAULT_ALLOWED_PREFIXES, deny_globs=deny_globs)


def is_allowed_relative_path(relative: str, policy: Policy) -> bool:
    normalized = normalize_relative_path(relative)
    return any(normalized.startswith(prefix) for prefix in policy.allowed_prefixes)


def deny_reason(relative: str, policy: Policy) -> str | None:
    normalized = normalize_relative_path(relative)
    lowered = normalized.lower()
    parts = lowered.split("/")
    if not normalized:
        return "empty paths are rejected"
    if normalized.startswith(("/", "~")):
        return "absolute and home-relative paths are rejected"
    if ".." in Path(normalized).parts:
        return "parent traversal is rejected"
    if ".git" in parts:
        return "git internals are rejected"
    for marker in ("secret", "token", "credential", "password"):
        if marker in lowered:
            return f"secret-looking path marker is rejected: {marker}"
    for pattern in policy.deny_globs:
        pattern_lower = pattern.lower()
        name_lower = Path(lowered).name
        if fnmatch.fnmatch(lowered, pattern_lower) or fnmatch.fnmatch(name_lower, pattern_lower):
            return f"deny pattern matched: {pattern}"
    return None


def resolve_repo_target(repo: Path, relative: str) -> Path:
    target = (repo / normalize_relative_path(relative)).resolve()
    repo_resolved = repo.resolve()
    try:
        target.relative_to(repo_resolved)
    except ValueError as exc:
        raise ValueError(f"{relative}: target escapes repository") from exc
    return target


def has_symlink_parent(repo: Path, relative: str) -> bool:
    current = repo
    for part in Path(normalize_relative_path(relative)).parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    target = repo / normalize_relative_path(relative)
    return target.exists() and target.is_symlink()


def validate_change(repo: Path, change: dict[str, Any], policy: Policy) -> list[str]:
    errors: list[str] = []
    raw_path = change.get("path")
    content = change.get("content")
    mode = change.get("mode", "replace")
    allow_executable = bool(change.get("allow_executable", False))

    if not isinstance(raw_path, str) or not raw_path.strip():
        return ["change path must be a non-empty string"]

    relative = normalize_relative_path(raw_path)
    path_obj = Path(relative)
    reason = deny_reason(relative, policy)
    if reason:
        errors.append(f"{relative}: {reason}")
    if not is_allowed_relative_path(relative, policy):
        errors.append(f"{relative}: outside allowed prefixes {', '.join(policy.allowed_prefixes)}")
    try:
        resolve_repo_target(repo, relative)
    except ValueError as exc:
        errors.append(str(exc))
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
        errors.append(f"{relative}: executable script changes require explicit allow_executable")
    if path_obj.suffix.lower() in CONFIG_SUFFIXES and "examples/" not in relative and not allow_executable:
        errors.append(f"{relative}: config-style changes require explicit allow_executable")
    if mode == "create" and (repo / relative).exists():
        errors.append(f"{relative}: create mode target already exists")
    return errors


def validate_proposal(paths: Paths, proposal: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    changes = proposal.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("proposal changes must be a non-empty list")
        changes = []

    policy = load_policy(paths, proposal)
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"change {index}: each change must be an object")
            continue
        errors.extend(validate_change(paths.repo, change, policy))

    return {
        "ok": not errors,
        "checked_at": utc_now(),
        "allowed_prefixes": list(policy.allowed_prefixes),
        "deny_globs": list(policy.deny_globs),
        "errors": errors,
    }


def change_diff(repo: Path, change: dict[str, Any]) -> str:
    relative = normalize_relative_path(change["path"])
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
        if isinstance(change, dict) and isinstance(change.get("path"), str) and isinstance(change.get("content"), str):
            chunks.append(change_diff(repo, change))
    return "\n".join(chunk for chunk in chunks if chunk).rstrip() + "\n"


def stage_proposal(paths: Paths, proposal_path: Path) -> dict[str, Any]:
    proposal = load_json(proposal_path)
    validation = validate_proposal(paths, proposal)
    stage_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    stage_dir = paths.stage_root / stage_id
    proposed_dir = stage_dir / "proposed"
    stage_dir.mkdir(parents=True, exist_ok=False)

    for change in proposal.get("changes", []):
        if not isinstance(change, dict):
            continue
        relative = normalize_relative_path(str(change.get("path", "")))
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
            "production_apply": True,
            "root_apply_service": False,
            "automatic_approval": False,
            "ai_initiated_apply": False,
            "rollback_execution": False,
            "operator_approval_metadata": True,
        },
        "validation_ok": validation["ok"],
        "approval_status": "pending_review",
        "apply_status": "not_applied",
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
            "production_apply": status == "approved",
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


def snapshot_change(repo: Path, snapshot_root: Path, change: dict[str, Any]) -> dict[str, Any]:
    relative = normalize_relative_path(change["path"])
    target = resolve_repo_target(repo, relative)
    proposed = change["content"].encode("utf-8")
    record: dict[str, Any] = {
        "path": relative,
        "target": str(target),
        "existed": target.exists(),
        "proposed_sha256": sha256_bytes(proposed),
    }
    if target.exists():
        original = target.read_bytes()
        snapshot_path = snapshot_root / "original" / relative
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(original)
        record.update(
            {
                "original_sha256": sha256_bytes(original),
                "original_mode": stat.S_IMODE(target.stat().st_mode),
                "snapshot_path": str(snapshot_path),
            }
        )
    return record


def apply_change(repo: Path, change: dict[str, Any]) -> dict[str, Any]:
    relative = normalize_relative_path(change["path"])
    target = resolve_repo_target(repo, relative)
    content = change["content"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    if bool(change.get("allow_executable", False)) and Path(relative).suffix.lower() in SCRIPT_SUFFIXES:
        current_mode = target.stat().st_mode
        target.chmod(current_mode | stat.S_IXUSR)
    actual_sha = sha256_bytes(target.read_bytes())
    expected_sha = sha256_text(content)
    return {
        "path": relative,
        "target": str(target),
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "verified": actual_sha == expected_sha,
    }


def apply_stage(paths: Paths, stage_id: str, operator: str) -> dict[str, Any]:
    if not operator.strip():
        raise ValueError("operator name is required")
    stage_dir = find_stage(paths.stage_root, stage_id)
    manifest = load_manifest(stage_dir)
    if manifest.get("approval_status") != "approved":
        raise ValueError("stage must be approved before apply")
    if manifest.get("apply_status") == "applied":
        raise ValueError("stage has already been applied")

    validation = validate_proposal(paths, manifest["proposal"])
    write_json(stage_dir / "validation.json", validation)
    if not validation["ok"]:
        manifest["validation_ok"] = False
        manifest["approval_status"] = "pending_review"
        manifest["approval_reset_reason"] = "validation_failed_before_apply"
        write_manifest(stage_dir, manifest)
        raise ValueError("fresh validation failed before apply")

    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_root = stage_dir / "snapshots" / snapshot_id
    snapshot_root.mkdir(parents=True, exist_ok=False)
    changes = [change for change in manifest["proposal"].get("changes", []) if isinstance(change, dict)]
    snapshot_records = [snapshot_change(paths.repo, snapshot_root, change) for change in changes]
    snapshot_manifest = {
        "snapshot_id": snapshot_id,
        "created_at": utc_now(),
        "stage_id": stage_id,
        "operator": operator.strip(),
        "files": snapshot_records,
    }
    write_json(snapshot_root / "snapshot-manifest.json", snapshot_manifest)

    verification = [apply_change(paths.repo, change) for change in changes]
    verification_ok = all(item["verified"] for item in verification)
    apply_payload = {
        "stage_id": stage_id,
        "applied_at": utc_now(),
        "operator": operator.strip(),
        "snapshot_id": snapshot_id,
        "verification_ok": verification_ok,
        "verification": verification,
    }
    rollback_metadata = {
        "stage_id": stage_id,
        "snapshot_id": snapshot_id,
        "rollback_execution_available": False,
        "manual_restore_note": "Phase 4 records originals and metadata only; it does not execute rollback.",
        "snapshot_manifest": str(snapshot_root / "snapshot-manifest.json"),
    }
    write_json(stage_dir / "apply.json", apply_payload)
    write_json(stage_dir / "rollback-metadata.json", rollback_metadata)
    manifest["validation_ok"] = True
    manifest["apply_status"] = "applied" if verification_ok else "applied_verification_failed"
    manifest["applied_at"] = apply_payload["applied_at"]
    manifest["applied_by"] = apply_payload["operator"]
    manifest["snapshot_id"] = snapshot_id
    manifest["verification_ok"] = verification_ok
    write_manifest(stage_dir, manifest)
    append_audit(
        paths,
        "stage_applied",
        {
            "stage_id": stage_id,
            "operator": operator.strip(),
            "snapshot_id": snapshot_id,
            "verification_ok": verification_ok,
            "change_count": len(changes),
        },
    )
    return {"ok": verification_ok, "stage_id": stage_id, "apply": apply_payload, "rollback_metadata": rollback_metadata}


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
                "apply_status": manifest.get("apply_status", "unknown"),
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
    validation = validate_proposal(paths, manifest["proposal"])
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
    apply_path = stage_dir / "apply.json"
    approval = load_json(approval_path) if approval_path.exists() else None
    applied = load_json(apply_path) if apply_path.exists() else None
    append_audit(paths, "stage_status_viewed", {"stage_id": args.stage_id})
    print(
        json.dumps(
            {
                "ok": True,
                "stage_id": args.stage_id,
                "validation_ok": manifest.get("validation_ok"),
                "approval_status": manifest.get("approval_status", "unknown"),
                "apply_status": manifest.get("apply_status", "unknown"),
                "approval": approval,
                "apply": applied,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_apply(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    result = apply_stage(paths, args.stage_id, args.by)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def command_policy(args: argparse.Namespace) -> int:
    paths = make_paths(args)
    policy = load_policy(paths)
    print(json.dumps({"ok": True, "allowed_prefixes": policy.allowed_prefixes, "deny_globs": policy.deny_globs}, indent=2))
    return 0


def make_paths(args: argparse.Namespace) -> Paths:
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"repo does not exist: {repo}")
    stage_root = Path(args.stage_root or os.environ.get("EDGE1_AI_FS_STAGE_ROOT") or DEFAULT_STAGE_ROOT).resolve()
    audit_log = Path(args.audit_log or os.environ.get("EDGE1_AI_FS_AUDIT_LOG") or DEFAULT_AUDIT_LOG).resolve()
    policy_config_raw = args.policy_config or os.environ.get("EDGE1_AI_FS_POLICY_CONFIG")
    policy_config = Path(policy_config_raw).resolve() if policy_config_raw else None
    return Paths(repo=repo, stage_root=stage_root, audit_log=audit_log, policy_config=policy_config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bigbird-fsctl",
        description="Edge1 AI filesystem connector staged proposal workflow.",
    )
    parser.add_argument("--repo", default=".", help="Target repository used for validation, diff, and apply.")
    parser.add_argument("--stage-root", help="Staging root. Defaults to EDGE1_AI_FS_STAGE_ROOT or /var/lib.")
    parser.add_argument("--audit-log", help="Audit JSONL path. Defaults to EDGE1_AI_FS_AUDIT_LOG or /var/log.")
    parser.add_argument("--policy-config", help="Optional JSON policy config path.")
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

    status = subparsers.add_parser("status", help="Show validation, approval, and apply status.")
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

    apply = subparsers.add_parser("apply", help="Operator-controlled apply for an approved staged proposal.")
    apply.add_argument("stage_id")
    apply.add_argument("--by", required=True, help="Operator name or identifier.")
    apply.set_defaults(func=command_apply)

    policy = subparsers.add_parser("policy", help="Show the active allowlist and hard deny policy.")
    policy.set_defaults(func=command_policy)

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
