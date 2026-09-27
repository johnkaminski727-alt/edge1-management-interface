#!/usr/bin/env python3
"""Assignment 250: fail-closed, READ-ONLY rollback decision prototype.

This module cannot perform nft/systemd operations, authorize deletion, disarm
watchdogs, or send notifications. Callers MUST persist the returned decision
and arrange independent human alerting. All states are diagnostic only.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

PREFIX = "bigbird_spamhaus_run_"
OWNER = "edge1-spamhaus-run:"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
BOOT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
TIMER_UNIT = re.compile(r"edge1-spamhaus-run-[0-9a-f]{32}\.timer\Z")


def _valid_metadata(meta: Any) -> bool:
    if not isinstance(meta, dict) or set(meta) != {
        "run_id", "table_name", "boot_id", "candidate_sha256", "timer_unit"
    }:
        return False
    run_id = meta.get("run_id")
    return (
        isinstance(run_id, str) and HEX32.fullmatch(run_id) is not None
        and meta.get("table_name") == PREFIX + run_id
        and isinstance(meta.get("boot_id"), str)
        and BOOT_ID.fullmatch(meta["boot_id"]) is not None
        and isinstance(meta.get("candidate_sha256"), str)
        and HEX64.fullmatch(meta["candidate_sha256"]) is not None
        and meta.get("timer_unit") == "edge1-spamhaus-run-" + run_id + ".timer"
    )


def _classify(nft: Any, meta: dict) -> str:
    if not isinstance(nft, dict) or not isinstance(nft.get("nftables"), list):
        return "invalid_listing"
    found = []
    for record in nft["nftables"]:
        if not isinstance(record, dict):
            return "invalid_listing"
        table = record.get("table")
        if table is None:
            continue
        if not isinstance(table, dict):
            return "invalid_listing"
        family, name = table.get("family"), table.get("name")
        if not isinstance(family, str) or not isinstance(name, str):
            return "invalid_listing"
        if family == "inet" and name == meta["table_name"]:
            found.append(table)
    if not found:
        return "absent"
    if len(found) != 1:
        return "invalid_listing"
    if found[0].get("comment") != OWNER + meta["run_id"]:
        return "foreign"
    return "observed_owned"


def evaluate_rollback(meta: Any, nft: Any, *, inspection_error: bool = False) -> dict:
    """Return bounded diagnostic action; NEVER an authorization to delete.

    Even 'observed_owned' mandates alert/no-delete because an uncooperative
    privileged writer can replace the table after this separate inspection.
    """
    if not _valid_metadata(meta):
        reason = "invalid_metadata"
        safe_meta = None
    elif type(inspection_error) is not bool:
        reason = "invalid_input"
        safe_meta = None
    elif inspection_error:
        reason = "inspection_failed"
        safe_meta = meta
    else:
        reason = _classify(nft, meta)
        safe_meta = meta

    result = {
        "schema_version": 1,
        "decision": "do_not_delete",
        "command_allowed": False,
        "watchdog_disarm_allowed": False,
        "reason": reason,
        "requires_human_review": reason != "absent",
        "metadata": safe_meta,
    }
    # Stable content digest permits exact-match comparison in downstream
    # audit logs; it is NOT a signature, authentication or durable storage.
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    result["evidence_sha256"] = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    return result


def verify_evidence_digest(decision: Any) -> bool:
    if not isinstance(decision, dict) or type(decision.get("schema_version")) is not int:
        return False
    digest = decision.get("evidence_sha256")
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
        return False
    unsigned = dict(decision)
    del unsigned["evidence_sha256"]
    expected = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()
    return digest == expected
