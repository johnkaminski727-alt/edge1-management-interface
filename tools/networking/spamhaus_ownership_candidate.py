#!/usr/bin/env python3
"""Assignment 244 (staging only): create-only, run-tagged candidate derivation.

Pure transformation of an already-approved canonical nft candidate. This tool
does not run nftables, systemd, fetch feeds, or change firewall state. Its
output must be separately checked in an isolated nftables execution rehearsal.
"""
from __future__ import annotations

import re
import secrets

HEADER = "table inet bigbird_spamhaus {\n"
IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")
OWNER_PREFIX = "edge1-spamhaus-run:"


def new_run_id() -> str:
    return secrets.token_hex(16)


def derive_owned_candidate(candidate: str, run_id: str) -> str:
    """Insert a create-only guard and table comment into a validated candidate.

    Only the canonical single-table form produced by the existing parser is
    accepted. The rendered output is not itself authorization for deployment.
    """
    if not IDENTIFIER.fullmatch(run_id):
        raise ValueError("Run identifier must be exactly 32 lowercase hex characters")
    if not candidate.startswith(HEADER):
        raise ValueError("Candidate is not the expected canonical Spamhaus table")
    if candidate.count(HEADER) != 1 or candidate.count("table inet bigbird_spamhaus") != 1:
        raise ValueError("Candidate contains an unexpected table declaration")
    if not candidate.endswith("}\n"):
        raise ValueError("Candidate is incomplete")
    if "\x00" in candidate or OWNER_PREFIX in candidate or "delete table" in candidate:
        raise ValueError("Candidate includes disallowed control content")
    return (
        "create table inet bigbird_spamhaus\n\n"
        + HEADER
        + '  comment "' + OWNER_PREFIX + run_id + '"\n'
        + candidate[len(HEADER):]
    )


def parse_owner_comment(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith(OWNER_PREFIX):
        return None
    owner = value[len(OWNER_PREFIX):]
    return owner if IDENTIFIER.fullmatch(owner) else None
