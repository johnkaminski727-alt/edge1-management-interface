#!/usr/bin/env python3
"""Caller authentication for POST /outbound-mail/send.

The send route previously trusted any loopback caller. It now requires the same
HMAC request signature as the preparation API, but with a separate secret and
client allowlist: the preparation secret is shared with the Private AI client,
so reusing it would let that client sign live sends.

The policy is fixed here rather than in gateway.json so the gateway config
schema is unchanged and the send client list cannot be widened by editing JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import outbound_mail_preparation_auth as preparation_auth


SEND_PATH = "/outbound-mail/send"
SEND_CLIENT_ID = "wwcx-mail-room"
SEND_AUTH = {
    "enabled": True,
    "authentication": preparation_auth.AUTHENTICATION,
    "secret_env": "WWCX_MAIL_SEND_TOKEN",
    "allowed_clients": [SEND_CLIENT_ID],
    "clock_skew_seconds": 120,
    "nonce_ttl_seconds": 900,
    "nonce_store": "/var/lib/wwcx-outbound-mail/send-nonces.sqlite3",
    "max_request_bytes": 327680,
}


def verify_send(
    headers: Mapping[str, str],
    method: str,
    path: str,
    body: bytes,
    *,
    nonce_store: str | Path | None = None,
    now: int | None = None,
    environment: Mapping[str, str] | None = None,
) -> preparation_auth.VerifiedPreparationClient:
    """Verify a signed send request; raises preparation_auth errors on failure.

    A missing WWCX_MAIL_SEND_TOKEN raises PreparationAuthUnavailableError, so an
    unconfigured gateway refuses every send.
    """
    if method.upper() != "POST" or path != SEND_PATH:
        raise preparation_auth.InvalidPreparationAuthError("send authentication applies only to the send route")
    return preparation_auth.verify_request(
        SEND_AUTH,
        headers,
        "POST",
        SEND_PATH,
        body,
        nonce_store or SEND_AUTH["nonce_store"],
        now=now,
        environment=environment,
    )
