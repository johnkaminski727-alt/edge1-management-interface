#!/usr/bin/env python3
"""Bounded repository branch-write controller for BigBird Control Plane v2.

This controller never checks out, rewrites, pushes, merges, or deploys main.
It creates a new agent/bigbird-* branch from an exact expected commit using a
temporary detached worktree, validates the candidate, commits it, then creates
the branch ref atomically. The running checkout remains untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("BIGBIRD_REPOSITORY_ROOT", "/opt/edge1-management-interface")).resolve()
STATE_ROOT = Path(os.environ.get("BIGBIRD_REPOSITORY_STATE", "/var/lib/bigbird-repository-controller")).resolve()
MAX_FILES = 20
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
BASE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^agent/bigbird-[a-z0-9][a-z0-9._-]{0,79}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$")
ALLOWED_PREFIXES = (
    "docs/",
    "registers/",
    "tests/",
    "server/",
    "src/",
    "tools/",
    "integrations/",
    "schemas/",
    "config/examples/",
)
DENIED_PREFIXES = (
    ".git/",
    ".github/",
    "deploy/",
    "config/security/",
    "config/private/",
)
DENIED_MARKERS = ("secret", "token", "credential", "password", "private_key")
DENIED_SUFFIXES = (".env", ".key", ".pem", ".p12", ".pfx")
SECRET_PATTERNS = (
    re.compile(r"BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
)


class RepositoryWriteError(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_request_digest(request: dict[str, Any]) -> str:
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env={**os.environ, "PATH": "/usr/bin:/bin"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryWriteError("git execution failed") from exc
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "git command failed").strip()[:1200]
        raise RepositoryWriteError(detail)
    return proc


def normalize_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise RepositoryWriteError("change path must be a non-empty string")
    value = raw.strip().replace("\\", "/").lstrip("/")
    parts = Path(value).parts
    if not value or ".." in parts:
        raise RepositoryWriteError("change path contains parent traversal")
    lowered = value.lower()
    if any(lowered.startswith(prefix) for prefix in DENIED_PREFIXES):
        raise RepositoryWriteError("change path is explicitly denied")
    if not any(value.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise RepositoryWriteError("change path is outside approved repository prefixes")
    name = Path(value).name.lower()
    if any(marker in lowered for marker in DENIED_MARKERS):
        raise RepositoryWriteError("change path contains a sensitive marker")
    if name == ".env" or any(name.endswith(suffix) for suffix in DENIED_SUFFIXES):
        raise RepositoryWriteError("change path has a sensitive suffix")
    return value


def validate_content(content: Any) -> str:
    if not isinstance(content, str):
        raise RepositoryWriteError("change content must be UTF-8 text")
    if "\x00" in content:
        raise RepositoryWriteError("binary-looking content is rejected")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise RepositoryWriteError("change content exceeds per-file limit")
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            raise RepositoryWriteError("change content appears to contain credential material")
    return content


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise RepositoryWriteError("request must be an object")
    allowed = {"request_id", "expected_base_sha", "branch", "commit_message", "changes"}
    unexpected = sorted(set(request) - allowed)
    if unexpected:
        raise RepositoryWriteError("unexpected request fields: " + ", ".join(unexpected))

    request_id = request.get("request_id")
    base = request.get("expected_base_sha")
    branch = request.get("branch")
    message = request.get("commit_message")
    changes = request.get("changes")

    if not isinstance(request_id, str) or not REQUEST_ID_RE.fullmatch(request_id):
        raise RepositoryWriteError("invalid request_id")
    if not isinstance(base, str) or not BASE_SHA_RE.fullmatch(base):
        raise RepositoryWriteError("expected_base_sha must be a 40-character lowercase SHA-1")
    if not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch):
        raise RepositoryWriteError("branch must match agent/bigbird-* policy")
    if not isinstance(message, str) or not 3 <= len(message) <= 200 or "\n" in message:
        raise RepositoryWriteError("commit_message must contain 3 to 200 characters on one line")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_FILES:
        raise RepositoryWriteError("changes must contain 1 to {} items".format(MAX_FILES))

    normalized_changes = []
    seen = set()
    total = 0
    for item in changes:
        if not isinstance(item, dict) or set(item) - {"path", "content", "mode"}:
            raise RepositoryWriteError("each change must contain only path, content, and mode")
        path = normalize_path(item.get("path"))
        if path in seen:
            raise RepositoryWriteError("duplicate change path")
        seen.add(path)
        content = validate_content(item.get("content"))
        mode = item.get("mode", "replace")
        if mode not in {"create", "replace"}:
            raise RepositoryWriteError("change mode must be create or replace")
        total += len(content.encode("utf-8"))
        normalized_changes.append({"path": path, "content": content, "mode": mode})
    if total > MAX_TOTAL_BYTES:
        raise RepositoryWriteError("request exceeds total content limit")

    return {
        "request_id": request_id,
        "expected_base_sha": base,
        "branch": branch,
        "commit_message": message,
        "changes": normalized_changes,
    }


def ensure_repo(repo: Path) -> None:
    top = git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    if Path(top).resolve() != repo.resolve():
        raise RepositoryWriteError("repository root mismatch")


def ensure_base(repo: Path, base: str) -> None:
    proc = git(repo, "cat-file", "-e", base + "^{commit}", check=False)
    if proc.returncode != 0:
        raise RepositoryWriteError("expected base commit is not present")


def branch_exists(repo: Path, branch: str) -> bool:
    proc = git(repo, "show-ref", "--verify", "--quiet", "refs/heads/" + branch, check=False)
    return proc.returncode == 0


def request_record_path(request_id: str) -> Path:
    return STATE_ROOT / "requests" / (request_id + ".json")


def audit(event: dict[str, Any]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    path = STATE_ROOT / "audit.jsonl"
    record = {"at": utcnow(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def idempotent_result(request: dict[str, Any], digest: str) -> dict[str, Any] | None:
    path = request_record_path(request["request_id"])
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("request_digest") != digest:
        raise RepositoryWriteError("request_id was already used with different content")
    result = record.get("result")
    if not isinstance(result, dict):
        raise RepositoryWriteError("stored request record is incomplete")
    return {**result, "idempotent_replay": True}


def save_result(request: dict[str, Any], digest: str, result: dict[str, Any]) -> None:
    path = request_record_path(request["request_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"request_digest": digest, "result": result}
    fd, temp_name = tempfile.mkstemp(prefix=".request-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_candidate(worktree: Path, change: dict[str, Any]) -> None:
    target = (worktree / change["path"]).resolve()
    try:
        target.relative_to(worktree.resolve())
    except ValueError as exc:
        raise RepositoryWriteError("candidate path escapes worktree") from exc
    if target.exists() and target.is_symlink():
        raise RepositoryWriteError("symlink targets are rejected")
    current = worktree
    for part in Path(change["path"]).parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise RepositoryWriteError("symlink parents are rejected")
    if change["mode"] == "create" and target.exists():
        raise RepositoryWriteError("create target already exists: " + change["path"])
    if change["mode"] == "replace" and not target.exists():
        raise RepositoryWriteError("replace target does not exist: " + change["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(change["content"], encoding="utf-8")


def validate_candidate(worktree: Path, changes: list[dict[str, Any]]) -> None:
    git(worktree, "diff", "--cached", "--check")
    if git(worktree, "diff", "--cached", "--quiet", check=False).returncode == 0:
        raise RepositoryWriteError("candidate produces no repository change")
    python_paths = [item["path"] for item in changes if item["path"].endswith(".py")]
    for relative in python_paths:
        proc = subprocess.run(
            ["python3", "-m", "py_compile", str(worktree / relative)],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            env={**os.environ, "PATH": "/usr/bin:/bin"},
        )
        if proc.returncode != 0:
            raise RepositoryWriteError("python syntax validation failed for " + relative)
    json_paths = [item["path"] for item in changes if item["path"].endswith(".json")]
    for relative in json_paths:
        try:
            json.loads((worktree / relative).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RepositoryWriteError("JSON validation failed for " + relative) from exc


def create_branch_commit(request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(request)
    digest = canonical_request_digest(request)
    replay = idempotent_result(request, digest)
    if replay is not None:
        return replay

    ensure_repo(REPO)
    ensure_base(REPO, request["expected_base_sha"])
    if branch_exists(REPO, request["branch"]):
        raise RepositoryWriteError("branch already exists")

    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    worktree_parent = STATE_ROOT / "worktrees"
    worktree_parent.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix=request["request_id"] + "-", dir=str(worktree_parent)))
    added = False
    try:
        git(REPO, "worktree", "add", "--detach", str(worktree), request["expected_base_sha"])
        added = True
        for change in request["changes"]:
            write_candidate(worktree, change)
        git(worktree, "add", "--", *[item["path"] for item in request["changes"]])
        validate_candidate(worktree, request["changes"])
        env = {
            **os.environ,
            "PATH": "/usr/bin:/bin",
            "GIT_AUTHOR_NAME": "WW.CX Big Bird",
            "GIT_AUTHOR_EMAIL": "bigbird-control-plane@ww.cx",
            "GIT_COMMITTER_NAME": "WW.CX Big Bird",
            "GIT_COMMITTER_EMAIL": "bigbird-control-plane@ww.cx",
        }
        proc = subprocess.run(
            ["git", "-C", str(worktree), "commit", "-m", request["commit_message"]],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env=env,
        )
        if proc.returncode != 0:
            raise RepositoryWriteError((proc.stderr or proc.stdout or "git commit failed").strip()[:1200])
        commit = git(worktree, "rev-parse", "HEAD").stdout.strip()
        parent = git(worktree, "rev-parse", "HEAD^").stdout.strip()
        if parent != request["expected_base_sha"]:
            raise RepositoryWriteError("candidate commit parent does not match expected base")

        zero = "0" * 40
        git(REPO, "update-ref", "refs/heads/" + request["branch"], commit, zero)
        result = {
            "status": "committed",
            "request_id": request["request_id"],
            "branch": request["branch"],
            "base_sha": request["expected_base_sha"],
            "commit_sha": commit,
            "changed_paths": [item["path"] for item in request["changes"]],
            "pushed": False,
            "deployed": False,
            "idempotent_replay": False,
        }
        save_result(request, digest, result)
        audit({"event": "repository.branch.committed", **result})
        return result
    except Exception as exc:
        audit({
            "event": "repository.branch.failed",
            "request_id": request["request_id"],
            "branch": request["branch"],
            "base_sha": request["expected_base_sha"],
            "error": str(exc)[:500],
        })
        raise
    finally:
        if added:
            git(REPO, "worktree", "remove", "--force", str(worktree), check=False)
        elif worktree.exists():
            try:
                worktree.rmdir()
            except OSError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("commit",))
    args = parser.parse_args()
    request = json.load(os.sys.stdin)
    if args.command == "commit":
        result = create_branch_commit(request)
    else:
        raise SystemExit("unsupported command")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
