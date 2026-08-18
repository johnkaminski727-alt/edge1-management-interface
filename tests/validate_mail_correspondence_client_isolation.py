#!/usr/bin/env python3
"""Validate that existing Mail API clients do not inherit correspondence access."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_gateway_server as gateway_server
import outbound_mail_preparation_auth as preparation_auth


def verified(client_id: str) -> preparation_auth.VerifiedPreparationClient:
    return preparation_auth.VerifiedPreparationClient(
        client_id=client_id,
        timestamp=1_800_000_000,
        nonce="phase28_client_isolation_nonce_1234",
        content_sha256="0" * 64,
    )


gateway_server.GatewayHandler._require_correspondence_client(
    verified(gateway_server.CORRESPONDENCE_CLIENT_ID)
)

for existing_or_unrelated_client in (
    "wwcx-website-admin",
    "wwcx-messaging-adapter",
    "other-local-client",
):
    try:
        gateway_server.GatewayHandler._require_correspondence_client(
            verified(existing_or_unrelated_client)
        )
        raise AssertionError(
            f"{existing_or_unrelated_client} incorrectly inherited correspondence access"
        )
    except preparation_auth.InvalidPreparationAuthError:
        pass

assert gateway_server.CORRESPONDENCE_CLIENT_ID == "wwcx-private-ai"

print("Mail correspondence client isolation validation passed")
print("Only the dedicated wwcx-private-ai client may cross the correspondence API boundary")
print("Existing website-admin HMAC authorization does not imply message-body read authority")
