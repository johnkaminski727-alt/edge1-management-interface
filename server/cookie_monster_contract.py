#!/usr/bin/env python3
"""Bounded Big Bird -> Cookie Monster Alpha handoff contract.

The contract deliberately carries a dataset *name*, not an arbitrary filesystem
path, URL, credential, or command. Runtime configuration maps the dataset name to
an approved staging source outside this message boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any

SCHEMA = "wwcx.cookie-monster.job.v1"
MODE = "alpha-read-only"
PIPELINE_STAGES = ("ingest", "normalize", "extract", "analyze", "knowledge-synthesize")
DATASET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
ACTOR_RE = re.compile(r"^[A-Za-z0-9._@:-]{1,80}$")


class ContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def idempotency_payload(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": request.get("schema"),
        "mode": request.get("mode"),
        "dataset": request.get("dataset"),
        "requested_stages": request.get("requested_stages"),
        "max_files": request.get("max_files"),
        "metadata_budget_seconds": request.get("metadata_budget_seconds"),
        "run_budget_seconds": request.get("run_budget_seconds"),
    }


def compute_idempotency_key(request: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(idempotency_payload(request)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_job_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
    return f"cmjob-{digest}"


def validate(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ContractError("job request must be an object")
    allowed = {
        "schema", "mode", "job_id", "idempotency_key", "dataset", "requested_stages",
        "max_files", "metadata_budget_seconds", "run_budget_seconds", "requested_by",
    }
    extra = sorted(set(request) - allowed)
    if extra:
        raise ContractError("unexpected job fields: " + ", ".join(extra))
    if request.get("schema") != SCHEMA:
        raise ContractError("unsupported job schema")
    if request.get("mode") != MODE:
        raise ContractError("job mode must remain alpha-read-only")
    dataset = request.get("dataset")
    if not isinstance(dataset, str) or not DATASET_RE.fullmatch(dataset):
        raise ContractError("dataset must be a bounded staging dataset name")
    stages = request.get("requested_stages")
    if not isinstance(stages, list) or not stages:
        raise ContractError("requested_stages must be a non-empty list")
    if len(stages) != len(set(stages)) or any(stage not in PIPELINE_STAGES for stage in stages):
        raise ContractError("requested_stages contains duplicates or unsupported stages")
    max_files = request.get("max_files")
    if not isinstance(max_files, int) or isinstance(max_files, bool) or not 1 <= max_files <= 10000:
        raise ContractError("max_files must be between 1 and 10000")
    for key, low, high in (
        ("metadata_budget_seconds", 0.1, 120.0),
        ("run_budget_seconds", 1.0, 3600.0),
    ):
        value = request.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= float(value) <= high:
            raise ContractError(f"{key} must be between {low} and {high}")
    actor = request.get("requested_by")
    if not isinstance(actor, str) or not ACTOR_RE.fullmatch(actor):
        raise ContractError("requested_by is invalid")
    expected_key = compute_idempotency_key(request)
    if request.get("idempotency_key") != expected_key:
        raise ContractError("idempotency_key does not match job contents")
    expected_job_id = compute_job_id(expected_key)
    if request.get("job_id") != expected_job_id:
        raise ContractError("job_id does not match idempotency_key")
    return dict(request)


def make_request(
    dataset: str,
    requested_by: str,
    requested_stages: list[str] | None = None,
    max_files: int = 100,
    metadata_budget_seconds: float = 20.0,
    run_budget_seconds: float = 300.0,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": MODE,
        "dataset": dataset,
        "requested_stages": requested_stages or list(PIPELINE_STAGES),
        "max_files": max_files,
        "metadata_budget_seconds": metadata_budget_seconds,
        "run_budget_seconds": run_budget_seconds,
        "requested_by": requested_by,
    }
    request["idempotency_key"] = compute_idempotency_key(request)
    request["job_id"] = compute_job_id(request["idempotency_key"])
    return validate(request)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cookie Monster Alpha job contract")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("make")
    make.add_argument("--dataset", required=True)
    make.add_argument("--requested-by", required=True)
    make.add_argument("--max-files", type=int, default=100)
    check = sub.add_parser("validate")
    check.add_argument("--file", default="-", help="JSON request file, or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.command == "make":
            value = make_request(args.dataset, args.requested_by, max_files=args.max_files)
        else:
            text = sys.stdin.read() if args.file == "-" else open(args.file, "r", encoding="utf-8").read()
            value = validate(json.loads(text))
    except (ContractError, json.JSONDecodeError, OSError) as exc:
        print(f"cookie-monster-contract: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
