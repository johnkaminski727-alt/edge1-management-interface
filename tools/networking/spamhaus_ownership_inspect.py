#!/usr/bin/env python3
"""Assignment 245: *read-only* ownership inspection for isolated rehearsal.

This module never issues a firewall-changing command. A matching table comment
is necessary but NOT sufficient for safe deletion; the lookup and a future
delete would be separate operations. The guarded boot service does not import
or invoke this experimental component.
"""
from __future__ import annotations

import json
from typing import Any

TABLE = ("inet", "bigbird_spamhaus")
PREFIX = "edge1-spamhaus-run:"


def assess_table_ownership(document: str, run_id: str) -> str:
    """Return absent, owned, foreign or invalid; NEVER authorize deletion.

    A caller must still establish exclusive control of every privileged writer
    or demonstrate a genuinely atomic ownership-conditional delete.
    """
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("Invalid expected run identifier")
    try:
        records: Any = json.loads(document)["nftables"]
        if not isinstance(records, list):
            raise ValueError("Invalid nft document")
        found = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Invalid nft record")
            table = record.get("table")
            if table is None:
                continue
            if not isinstance(table, dict):
                raise ValueError("Invalid table entry")
            family, name = table["family"], table["name"]
            if not isinstance(family, str) or not isinstance(name, str):
                raise ValueError("Invalid table identity")
            if (family, name) == TABLE:
                found.append(table)
        if not found:
            return "absent"
        if len(found) != 1:
            return "invalid"
        comment = found[0].get("comment")
        if not isinstance(comment, str) or comment != PREFIX + run_id:
            return "foreign"
        return "owned"
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "invalid"
