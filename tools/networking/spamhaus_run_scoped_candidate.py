#!/usr/bin/env python3
"""Assignment 247: pure per-attempt table renderer (STAGING PROTOTYPE ONLY).

DO NOT wire this module into boot restoration or production recovery. It
converts a separately verified canonical candidate to an unpredictable,
per-attempt nftables table and places its ownership comment in CREATE itself.
It never executes nftables, downloads feeds or touches systemd.
"""
from __future__ import annotations

import re
import secrets

CANONICAL = "bigbird_spamhaus"
PREFIX = "bigbird_spamhaus_run_"
OWNER_PREFIX = "edge1-spamhaus-run:"
HEADER = "table inet " + CANONICAL + " {\n"
VALID_RUN_ID = re.compile(r"[0-9a-f]{32}", re.ASCII)


def new_run_id() -> str:
    return secrets.token_hex(16)


def table_name(run_id: str) -> str:
    if not isinstance(run_id, str) or not VALID_RUN_ID.fullmatch(run_id):
        raise ValueError("Expected exactly 32 lowercase hexadecimal characters")
    return PREFIX + run_id


def render_scoped_candidate(canonical_candidate: str, run_id: str) -> str:
    """Produce a create-only, separately named table with a matching run tag.

    The input MUST previously have passed installed pinned-candidate preflight.
    This is a deterministic transformer, not validation of feed authenticity.
    """
    name = table_name(run_id)
    if not isinstance(canonical_candidate, str):
        raise ValueError("Candidate must be text")
    if not canonical_candidate.startswith(HEADER):
        raise ValueError("Expected canonical Spamhaus table header")
    if canonical_candidate.count(HEADER) != 1:
        raise ValueError("Multiple canonical Spamhaus table headers")
    if canonical_candidate.count(CANONICAL) != 1:
        raise ValueError("Additional canonical name occurrence")
    if canonical_candidate.count("{") != canonical_candidate.count("}"):
        raise ValueError("Unbalanced braces")
    if not canonical_candidate.endswith("}\n"):
        raise ValueError("Truncated canonical candidate")
    if any(s in canonical_candidate for s in (
        "\x00", "include ", "delete table", "flush table", "create table",
        OWNER_PREFIX, PREFIX,
    )):
        raise ValueError("Candidate includes unexpected control statements")
    scoped_body = "table inet " + name + " {\n" + canonical_candidate[len(HEADER):]
    return (
        "create table inet " + name + " {\n"
        '    comment "' + OWNER_PREFIX + run_id + '";\n'
        "}\n\n"
        + scoped_body
    )


def expected_owner_comment(run_id: str) -> str:
    table_name(run_id)
    return OWNER_PREFIX + run_id


def classify_scoped_table(nft_document: dict, run_id: str) -> str:
    """Read-only classification only. NOT deletion authorization.

    A malicious privileged writer can replace a table between classification
    and deletion. Never infer an atomic compare-and-delete from a matching tag.
    """
    name = table_name(run_id)
    try:
        records = nft_document["nftables"]
        if not isinstance(records, list):
            return "invalid"
        found = []
        for item in records:
            if not isinstance(item, dict):
                return "invalid"
            table = item.get("table")
            if table is None:
                continue
            if not isinstance(table, dict):
                return "invalid"
            if table.get("family") == "inet" and table.get("name") == name:
                found.append(table)
        if not found:
            return "absent"
        if len(found) != 1:
            return "invalid"
        return "owned" if found[0].get("comment") == expected_owner_comment(run_id) else "foreign"
    except (KeyError, TypeError, ValueError):
        return "invalid"
