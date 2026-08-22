#!/usr/bin/env python3
"""Deliberately tiny, data-only Fengus worker for Cookie Monster Alpha.

The worker accepts bounded JSON work items. It never accepts an archive path,
URL, shell command, credential, or arbitrary executable operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

SCHEMA = "wwcx.cookie-monster.fengus-work.v1"
RESULT_SCHEMA = "wwcx.cookie-monster.fengus-result.v1"
JOB_RE = re.compile(r"^cmjob-[a-f0-9]{24}$")
OPERATIONS = {"text.token-stats", "facts.normalize"}
FORBIDDEN_KEYS = {"path", "url", "uri", "command", "shell", "token", "secret", "password", "credential", "archive"}
MAX_INPUT_BYTES = 128 * 1024
MAX_TEXT_CHARS = 100_000


class WorkerError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _scan_forbidden(value: Any, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_KEYS or any(part in normalized for part in ("secret", "password", "credential", "token", "command")):
                raise WorkerError("forbidden worker input key: " + ".".join((*trail, str(key))))
            _scan_forbidden(child, (*trail, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden(child, (*trail, str(index)))


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise WorkerError("work item must be an object")
    if len(canonical_json(request).encode("utf-8")) > MAX_INPUT_BYTES:
        raise WorkerError("work item exceeds bounded input size")
    allowed = {"schema", "job_id", "work_id", "operation", "source_asset_id", "payload"}
    extra = sorted(set(request) - allowed)
    if extra:
        raise WorkerError("unexpected work item fields: " + ", ".join(extra))
    if request.get("schema") != SCHEMA:
        raise WorkerError("unsupported work schema")
    if not JOB_RE.fullmatch(str(request.get("job_id", ""))):
        raise WorkerError("invalid job_id")
    work_id = request.get("work_id")
    if not isinstance(work_id, str) or not re.fullmatch(r"^work-[a-f0-9]{16,64}$", work_id):
        raise WorkerError("invalid work_id")
    operation = request.get("operation")
    if operation not in OPERATIONS:
        raise WorkerError("operation is not allowlisted")
    source_asset_id = request.get("source_asset_id")
    if not isinstance(source_asset_id, str) or not re.fullmatch(r"^sha256:[a-f0-9]{64}$", source_asset_id):
        raise WorkerError("invalid source_asset_id")
    payload = request.get("payload")
    if not isinstance(payload, dict):
        raise WorkerError("payload must be an object")
    _scan_forbidden(payload)
    return dict(request)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(request)
    op = request["operation"]
    payload = request["payload"]
    if op == "text.token-stats":
        text = payload.get("text")
        if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
            raise WorkerError("text.token-stats requires bounded payload.text")
        output = {
            "characters": len(text),
            "lines": 0 if not text else text.count("\n") + 1,
            "words": len(text.split()),
        }
    elif op == "facts.normalize":
        facts = payload.get("facts")
        if not isinstance(facts, dict) or len(facts) > 100:
            raise WorkerError("facts.normalize requires a bounded facts object")
        output = {str(key).strip().lower().replace(" ", "_"): value for key, value in sorted(facts.items())}
    else:  # pragma: no cover - validate_request is authoritative
        raise WorkerError("operation is not implemented")
    result = {
        "schema": RESULT_SCHEMA,
        "job_id": request["job_id"],
        "work_id": request["work_id"],
        "operation": op,
        "source_asset_id": request["source_asset_id"],
        "output": output,
    }
    result["result_hash"] = "sha256:" + hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
    return result


def atomic_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cookie Monster bounded Fengus worker")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        result = execute(request)
        atomic_result(args.result, result)
    except (OSError, json.JSONDecodeError, WorkerError) as exc:
        print(f"cookie-monster-fengus-worker: {exc}", file=sys.stderr)
        return 2
    print(canonical_json({"status": "completed", "work_id": result["work_id"], "result_hash": result["result_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
