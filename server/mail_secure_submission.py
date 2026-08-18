#!/usr/bin/env python3
"""Secure provider submission boundary for fully composed WW.CX Mail Room messages.

The caller supplies an already policy-composed preview. This module builds the
provider-bound MIME message exactly once, scans those exact serialized bytes, and
only then permits provider submission. It performs no automatic activation and
fails closed when a trusted final scanner is absent or does not return clean.
"""

from __future__ import annotations

import email.policy
import smtplib
import ssl
from datetime import datetime, timezone
from typing import Any, Callable

import mail_final_scan
import outbound_mail_gateway


def _submit_smtp_message(
    config: dict[str, Any],
    preview: dict[str, Any],
    message_bytes: bytes,
    message_id: str,
) -> dict[str, Any]:
    selected = config["provider"]["selected"]
    profile = config["provider"]["profiles"][selected]
    if profile["type"] != "smtp" or not profile["enabled"]:
        raise outbound_mail_gateway.ProviderUnavailableError(
            "selected provider is not an enabled SMTP profile"
        )
    host = outbound_mail_gateway._environment_value(profile["host_env"])
    port_text = outbound_mail_gateway._environment_value(profile["port_env"])
    username = outbound_mail_gateway._environment_value(profile["username_env"])
    password = outbound_mail_gateway._environment_value(profile["password_env"])
    if not all((host, port_text, username, password)):
        raise outbound_mail_gateway.ProviderUnavailableError(
            "runtime SMTP settings are incomplete"
        )
    try:
        port = int(port_text)
    except ValueError as exc:
        raise outbound_mail_gateway.ProviderUnavailableError(
            "runtime SMTP port is invalid"
        ) from exc
    if not 1 <= port <= 65535:
        raise outbound_mail_gateway.ProviderUnavailableError(
            "runtime SMTP port is out of range"
        )

    recipients = preview["request"]["recipients"]
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=profile["timeout_seconds"]) as client:
        client.ehlo()
        if profile["starttls"]:
            client.starttls(context=context)
            client.ehlo()
        client.login(username, password)
        refused = client.sendmail(
            preview["request"]["from_address"],
            recipients,
            message_bytes,
        )
    if refused:
        raise outbound_mail_gateway.ProviderUnavailableError(
            f"SMTP provider refused {len(refused)} recipient(s)"
        )
    return {
        "provider": selected,
        "provider_type": "smtp",
        "message_id": message_id,
        "recipient_count": len(recipients),
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def send_preview(
    config: dict[str, Any],
    base_policy: dict[str, Any],
    preview: dict[str, Any],
    *,
    confirmation: bool,
    final_scanner: Callable[[bytes], dict[str, Any]] | None,
) -> dict[str, Any]:
    if not isinstance(preview, dict) or not isinstance(preview.get("request"), dict):
        raise outbound_mail_gateway.GatewayError("composed preview is invalid")

    policy = outbound_mail_gateway.runtime_policy(base_policy, preview["request"])
    outbound_mail_gateway._delivery_gate(config, policy, confirmation)

    message = outbound_mail_gateway.build_email_message(preview)
    message_bytes = message.as_bytes(policy=email.policy.SMTP)
    try:
        final_scan = mail_final_scan.require_clean(message_bytes, final_scanner)
    except mail_final_scan.FinalScanError as exc:
        raise outbound_mail_gateway.DeliveryDisabledError(str(exc)) from exc

    selected = config["provider"]["selected"]
    provider_type = config["provider"]["profiles"][selected]["type"]
    if provider_type == "smtp":
        delivery = _submit_smtp_message(
            config,
            preview,
            message_bytes,
            str(message["Message-ID"]),
        )
    elif provider_type in {"gmail_api", "webhook"}:
        raise outbound_mail_gateway.ProviderUnavailableError(
            f"{provider_type} provider contract exists but its live adapter is not installed"
        )
    else:
        raise outbound_mail_gateway.ProviderUnavailableError(
            "no delivery provider is selected"
        )

    event = outbound_mail_gateway.audit_delivery_event(preview, delivery)
    event["final_scan"] = final_scan
    return {
        "delivery": delivery,
        "control_id": preview["control_id"],
        "action_url": preview["action_url"],
        "audit_event": event,
        "final_scan": final_scan,
    }
