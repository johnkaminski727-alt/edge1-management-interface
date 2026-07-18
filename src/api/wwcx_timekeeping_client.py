#!/usr/bin/env python3
"""Bounded client for the WW.CX TTS Assistant API.

The bearer token is read only from WWCX_TTS_API_TOKEN. The module deliberately
exposes named actions instead of arbitrary outbound HTTP requests.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_API_BASE = "https://ww.cx/api/tts-assistant.php"
READ_ACTIONS = {"entries", "entry", "audit-events", "report"}
DRAFT_ACTIONS = {"validate", "draft", "drafts-bulk"}
MUTATING_ACTIONS = {"entry-update", "entry-void"}
ALLOWED_ACTIONS = READ_ACTIONS | DRAFT_ACTIONS | MUTATING_ACTIONS


class TimekeepingError(RuntimeError):
    """Raised for configuration, transport, or API failures."""


def _required_token() -> str:
    token = os.environ.get("WWCX_TTS_API_TOKEN", "").strip()
    if not token:
        raise TimekeepingError("WWCX_TTS_API_TOKEN is not configured")
    return token


def _base_url() -> str:
    return os.environ.get("WWCX_TTS_API_BASE", "").strip() or DEFAULT_API_BASE


def request(
    action: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    allow_existing_entry_mutation: bool = False,
    timeout_seconds: int = 30,
) -> Any:
    if action not in ALLOWED_ACTIONS:
        raise TimekeepingError("unsupported action: %s" % action)
    if action in MUTATING_ACTIONS and not allow_existing_entry_mutation:
        raise TimekeepingError("existing-entry mutation requires explicit authorization")

    query = {"action": action}
    if params:
        query.update({key: value for key, value in params.items() if value is not None})
    url = "%s?%s" % (_base_url(), urllib.parse.urlencode(query))
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer %s" % _required_token(),
        "User-Agent": "edge1-wwcx-timekeeping-connector/1.0",
    }
    data = None
    method = "GET"
    if payload is not None:
        method = "POST"
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TimekeepingError("upstream HTTP %s: %s" % (exc.code, body[:500])) from exc
    except urllib.error.URLError as exc:
        raise TimekeepingError("upstream connection failed: %s" % exc.reason) from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TimekeepingError("upstream returned invalid JSON") from exc
    if isinstance(result, dict) and result.get("error"):
        raise TimekeepingError("upstream API error: %s" % result["error"])
    return result


def list_entries(start_date: Optional[str] = None, end_date: Optional[str] = None, status: Optional[str] = None) -> Any:
    return request("entries", params={"start_date": start_date, "end_date": end_date, "status": status})


def get_entry(entry_id: str) -> Any:
    return request("entry", params={"entry_id": entry_id})


def list_audit_events(start_date: Optional[str] = None, end_date: Optional[str] = None, limit: Optional[int] = None) -> Any:
    return request("audit-events", params={"start_date": start_date, "end_date": end_date, "limit": limit})


def get_report(start_date: str, end_date: str) -> Any:
    return request("report", params={"start_date": start_date, "end_date": end_date})


def validate_entries(entries: List[Dict[str, Any]]) -> Any:
    return request("validate", payload={"entries": entries})


def create_drafts(entries: List[Dict[str, Any]], idempotency_key: Optional[str] = None) -> Any:
    payload: Dict[str, Any] = {"entries": entries}
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    return request("drafts-bulk", payload=payload)


def update_entry(entry_id: str, patch: Dict[str, Any], reason: str) -> Any:
    payload = {"entry_id": entry_id, "patch": patch, "reason": reason}
    return request("entry-update", payload=payload, allow_existing_entry_mutation=True)


def void_entry(entry_id: str, reason: str) -> Any:
    return request(
        "entry-void",
        payload={"entry_id": entry_id, "reason": reason},
        allow_existing_entry_mutation=True,
    )
