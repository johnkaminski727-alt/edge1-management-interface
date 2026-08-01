#!/usr/bin/env python3
"""Provider-neutral WW.CX outbound-mail gateway core.

The committed configuration is intentionally disabled. Previewing and validating
messages is allowed without external delivery. Live submission requires every
policy and gateway authorization gate, an enabled provider profile, runtime
credentials, and an explicit per-request confirmation.
"""

from __future__ import annotations

import copy
import email.policy
import email.utils
import hashlib
import json
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterable

import outbound_mail_policy


CONTRACT = "wwcx.outbound-mail-gateway.v1"
SUPPORTED_PROVIDER_TYPES = {"disabled", "smtp", "gmail_api", "webhook"}
SUPPORTED_MESSAGE_CLASSES = outbound_mail_policy.ALLOWED_MESSAGE_CLASSES


class GatewayError(RuntimeError):
    """Base class for gateway failures."""


class ConfigurationError(GatewayError):
    """Raised when gateway configuration is invalid."""


class DeliveryDisabledError(GatewayError):
    """Raised when an external-delivery request reaches a closed gate."""


class ProviderUnavailableError(GatewayError):
    """Raised when the selected provider cannot submit the message."""


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    provider_type: str
    selected: bool
    enabled: bool
    configured: bool
    ready: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.provider_type,
            "selected": self.selected,
            "enabled": self.enabled,
            "configured": self.configured,
            "ready": self.ready,
            "detail": self.detail,
        }


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ConfigurationError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{label} must be boolean")


def _require_int(value: Any, label: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConfigurationError(f"{label} must be between {minimum} and {maximum}")


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label} must be non-empty text")
    return value.strip()


def validate_gateway_config(config: dict[str, Any]) -> None:
    _require_exact_keys(
        config,
        {
            "contract",
            "enabled",
            "deployment_authorized",
            "external_delivery_authorized",
            "listen",
            "paths",
            "provider",
            "admin",
            "content",
        },
        "gateway",
    )
    if config["contract"] != CONTRACT:
        raise ConfigurationError("unsupported gateway contract")
    for key in ("enabled", "deployment_authorized", "external_delivery_authorized"):
        _require_bool(config[key], key)

    listen = config["listen"]
    _require_exact_keys(listen, {"host", "port"}, "listen")
    _require_text(listen["host"], "listen.host")
    _require_int(listen["port"], "listen.port", 1, 65535)

    paths = config["paths"]
    _require_exact_keys(paths, {"policy", "audit_jsonl"}, "paths")
    _require_text(paths["policy"], "paths.policy")
    _require_text(paths["audit_jsonl"], "paths.audit_jsonl")

    provider = config["provider"]
    _require_exact_keys(provider, {"selected", "profiles"}, "provider")
    selected = _require_text(provider["selected"], "provider.selected")
    profiles = provider["profiles"]
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigurationError("provider.profiles must be a non-empty object")
    if selected not in profiles:
        raise ConfigurationError("selected provider profile does not exist")
    for name, profile in profiles.items():
        _require_text(name, "provider profile name")
        if not isinstance(profile, dict):
            raise ConfigurationError(f"provider profile {name} must be an object")
        provider_type = _require_text(profile.get("type"), f"provider.{name}.type")
        if provider_type not in SUPPORTED_PROVIDER_TYPES:
            raise ConfigurationError(f"provider type {provider_type} is unsupported")
        _require_bool(profile.get("enabled"), f"provider.{name}.enabled")
        if provider_type == "smtp":
            expected = {
                "type",
                "enabled",
                "host_env",
                "port_env",
                "username_env",
                "password_env",
                "starttls",
                "timeout_seconds",
            }
            _require_exact_keys(profile, expected, f"provider.{name}")
            for key in ("host_env", "port_env", "username_env", "password_env"):
                _require_text(profile[key], f"provider.{name}.{key}")
            _require_bool(profile["starttls"], f"provider.{name}.starttls")
            _require_int(profile["timeout_seconds"], f"provider.{name}.timeout_seconds", 1, 120)
        elif provider_type == "gmail_api":
            _require_exact_keys(profile, {"type", "enabled", "credential_source"}, f"provider.{name}")
            _require_text(profile["credential_source"], f"provider.{name}.credential_source")
        elif provider_type == "webhook":
            _require_exact_keys(
                profile,
                {"type", "enabled", "url_env", "secret_env"},
                f"provider.{name}",
            )
            _require_text(profile["url_env"], f"provider.{name}.url_env")
            _require_text(profile["secret_env"], f"provider.{name}.secret_env")
        else:
            _require_exact_keys(profile, {"type", "enabled"}, f"provider.{name}")

    admin = config["admin"]
    _require_exact_keys(
        admin,
        {
            "preview_enabled",
            "send_endpoint_enabled",
            "require_explicit_send_confirmation",
            "max_recipient_count",
            "max_body_bytes",
            "audit_view_limit",
        },
        "admin",
    )
    for key in (
        "preview_enabled",
        "send_endpoint_enabled",
        "require_explicit_send_confirmation",
    ):
        _require_bool(admin[key], f"admin.{key}")
    _require_int(admin["max_recipient_count"], "admin.max_recipient_count", 1, 500)
    _require_int(admin["max_body_bytes"], "admin.max_body_bytes", 1024, 10 * 1024 * 1024)
    _require_int(admin["audit_view_limit"], "admin.audit_view_limit", 1, 5000)

    content = config["content"]
    _require_exact_keys(
        content,
        {"persist_message_bodies", "persist_attachment_bytes", "draft_retention_hours"},
        "content",
    )
    _require_bool(content["persist_message_bodies"], "content.persist_message_bodies")
    _require_bool(content["persist_attachment_bytes"], "content.persist_attachment_bytes")
    _require_int(content["draft_retention_hours"], "content.draft_retention_hours", 1, 720)

    if config["enabled"]:
        if not config["deployment_authorized"]:
            raise ConfigurationError("enabled gateway requires deployment authorization")
        if not config["external_delivery_authorized"]:
            raise ConfigurationError("enabled gateway requires external-delivery authorization")
        if not admin["send_endpoint_enabled"]:
            raise ConfigurationError("enabled gateway requires the send endpoint")
        selected_profile = profiles[selected]
        if selected_profile["type"] == "disabled" or not selected_profile["enabled"]:
            raise ConfigurationError("enabled gateway requires an enabled non-disabled provider")


def resolve_repo_path(repo_root: str | Path, configured_path: str) -> Path:
    root = Path(repo_root).resolve()
    candidate = (root / configured_path).resolve()
    if root != candidate and root not in candidate.parents:
        raise ConfigurationError("configured path escapes repository root")
    return candidate


def _environment_value(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def provider_statuses(config: dict[str, Any]) -> list[ProviderStatus]:
    validate_gateway_config(config)
    selected = config["provider"]["selected"]
    statuses: list[ProviderStatus] = []
    for name, profile in config["provider"]["profiles"].items():
        provider_type = profile["type"]
        enabled = bool(profile["enabled"])
        configured = False
        detail = "Disabled profile"
        if provider_type == "smtp":
            required_names = [
                profile["host_env"],
                profile["port_env"],
                profile["username_env"],
                profile["password_env"],
            ]
            configured = all(_environment_value(item) for item in required_names)
            detail = "Runtime SMTP settings present" if configured else "Runtime SMTP settings incomplete"
        elif provider_type == "gmail_api":
            configured = False
            detail = "Connector adapter reserved; no live adapter installed"
        elif provider_type == "webhook":
            configured = bool(
                _environment_value(profile["url_env"])
                and _environment_value(profile["secret_env"])
            )
            detail = "Runtime webhook settings present" if configured else "Runtime webhook settings incomplete"
        ready = (
            name == selected
            and enabled
            and configured
            and config["enabled"]
            and config["deployment_authorized"]
            and config["external_delivery_authorized"]
            and config["admin"]["send_endpoint_enabled"]
        )
        statuses.append(
            ProviderStatus(
                name=name,
                provider_type=provider_type,
                selected=name == selected,
                enabled=enabled,
                configured=configured,
                ready=ready,
                detail=detail,
            )
        )
    return statuses


def status_payload(config: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_gateway_config(config)
    outbound_mail_policy.validate_policy(policy)
    statuses = provider_statuses(config)
    return {
        "gateway": "wwcx-outbound-mail-gateway",
        "contract": CONTRACT,
        "state": "ready" if any(item.ready for item in statuses) else "disabled",
        "preview_enabled": config["admin"]["preview_enabled"],
        "external_delivery_enabled": bool(
            config["enabled"]
            and config["deployment_authorized"]
            and config["external_delivery_authorized"]
            and config["admin"]["send_endpoint_enabled"]
            and any(item.ready for item in statuses)
        ),
        "policy_enabled": policy["enabled"],
        "transparent_action_links": policy["tracking"]["transparent_action_links"],
        "hidden_open_tracking": policy["tracking"]["hidden_open_tracking"],
        "device_fingerprinting": policy["tracking"]["device_fingerprinting"],
        "persist_message_bodies": config["content"]["persist_message_bodies"],
        "persist_attachment_bytes": config["content"]["persist_attachment_bytes"],
        "providers": [item.to_dict() for item in statuses],
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _split_addresses(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
    elif isinstance(value, list):
        raw = value
    else:
        raise GatewayError("recipient fields must be text or a list")
    return [str(item).strip() for item in raw if str(item).strip()]


def normalize_message_request(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    validate_gateway_config(config)
    if not isinstance(payload, dict):
        raise GatewayError("request payload must be an object")
    subject = str(payload.get("subject", "")).strip()
    body = str(payload.get("body", ""))
    if not subject:
        raise GatewayError("subject is required")
    if not body.strip():
        raise GatewayError("message body is required")
    if len(body.encode("utf-8")) > config["admin"]["max_body_bytes"]:
        raise GatewayError("message body exceeds the configured size limit")

    to_addresses = _split_addresses(payload.get("to"))
    cc_addresses = _split_addresses(payload.get("cc"))
    bcc_addresses = _split_addresses(payload.get("bcc"))
    recipients = outbound_mail_policy.normalize_recipients(
        to_addresses + cc_addresses + bcc_addresses
    )
    if len(recipients) > config["admin"]["max_recipient_count"]:
        raise GatewayError("recipient count exceeds the configured limit")
    message_class = str(payload.get("message_class", "business_correspondence")).strip()
    if message_class not in SUPPORTED_MESSAGE_CLASSES:
        raise GatewayError("message class is unsupported")

    return {
        "from_address": str(payload.get("from_address", "john@ww.cx")).strip(),
        "to": to_addresses,
        "cc": cc_addresses,
        "bcc": bcc_addresses,
        "recipients": recipients,
        "subject": subject,
        "body": body,
        "message_class": message_class,
        "signer_name": str(payload.get("signer_name", "John Kaminski")).strip(),
        "signer_title": str(payload.get("signer_title", "Authorized Representative")).strip(),
        "case_id": str(payload.get("case_id", "")).strip() or None,
        "action_id": str(payload.get("action_id", "")).strip() or None,
        "control_id": str(payload.get("control_id", "")).strip() or None,
        "unsubscribe_url": str(payload.get("unsubscribe_url", "")).strip() or None,
        "mailing_address": str(payload.get("mailing_address", "")).strip() or None,
        "reply_to": str(payload.get("reply_to", "")).strip() or None,
    }


def runtime_policy(base_policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(base_policy)
    requested_from = str(request.get("from_address", "")).strip()
    if requested_from:
        candidate["organization"]["contact_email"] = (
            outbound_mail_policy.validate_from_address(candidate, requested_from)
        )
    if request.get("mailing_address"):
        candidate["organization"]["mailing_address"] = request["mailing_address"]
    outbound_mail_policy.validate_policy(candidate)
    return candidate


def compose_preview(
    config: dict[str, Any],
    base_policy: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not config["admin"]["preview_enabled"]:
        raise DeliveryDisabledError("message preview is disabled")
    request = normalize_message_request(config, payload)
    policy = runtime_policy(base_policy, request)
    result = outbound_mail_policy.compose_plain_text_message(
        policy,
        body=request["body"],
        subject=request["subject"],
        recipients=request["recipients"],
        signer_name=request["signer_name"],
        signer_title=request["signer_title"],
        message_class=request["message_class"],
        control_id=request["control_id"],
        case_id=request["case_id"],
        action_id=request["action_id"],
        unsubscribe_url=request["unsubscribe_url"],
    )
    return {
        "request": request,
        "body": result["body"],
        "headers": result["headers"],
        "control_id": result["control_id"],
        "action_url": result["action_url"],
        "action_token": result["action_token"],
        "action_token_sha256": result["action_token_sha256"],
        "audit_record": result["audit_record"],
    }


def build_email_message(preview: dict[str, Any]) -> EmailMessage:
    request = preview["request"]
    message = EmailMessage(policy=email.policy.SMTP)
    message["From"] = request["from_address"]
    message["To"] = ", ".join(request["to"])
    if request["cc"]:
        message["Cc"] = ", ".join(request["cc"])
    if request["reply_to"]:
        message["Reply-To"] = request["reply_to"]
    message["Subject"] = request["subject"]
    message["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = email.utils.make_msgid(domain="ww.cx")
    for name, value in preview["headers"].items():
        message[name] = value
    message.set_content(preview["body"])
    return message


def _delivery_gate(config: dict[str, Any], policy: dict[str, Any], confirmation: bool) -> None:
    validate_gateway_config(config)
    outbound_mail_policy.validate_policy(policy)
    if config["admin"]["require_explicit_send_confirmation"] and confirmation is not True:
        raise DeliveryDisabledError("explicit send confirmation is required")
    if not config["enabled"]:
        raise DeliveryDisabledError("gateway is disabled")
    if not config["deployment_authorized"]:
        raise DeliveryDisabledError("deployment is not authorized")
    if not config["external_delivery_authorized"]:
        raise DeliveryDisabledError("external delivery is not authorized")
    if not config["admin"]["send_endpoint_enabled"]:
        raise DeliveryDisabledError("send endpoint is disabled")
    if not policy["enabled"] or not policy["smtp_cutover_authorized"]:
        raise DeliveryDisabledError("outbound-mail policy cutover is not authorized")


def submit_smtp(config: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    selected = config["provider"]["selected"]
    profile = config["provider"]["profiles"][selected]
    if profile["type"] != "smtp" or not profile["enabled"]:
        raise ProviderUnavailableError("selected provider is not an enabled SMTP profile")
    host = _environment_value(profile["host_env"])
    port_text = _environment_value(profile["port_env"])
    username = _environment_value(profile["username_env"])
    password = _environment_value(profile["password_env"])
    if not all((host, port_text, username, password)):
        raise ProviderUnavailableError("runtime SMTP settings are incomplete")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ProviderUnavailableError("runtime SMTP port is invalid") from exc
    if not 1 <= port <= 65535:
        raise ProviderUnavailableError("runtime SMTP port is out of range")

    message = build_email_message(preview)
    recipients = preview["request"]["recipients"]
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=profile["timeout_seconds"]) as client:
        client.ehlo()
        if profile["starttls"]:
            client.starttls(context=context)
            client.ehlo()
        client.login(username, password)
        refused = client.send_message(message, to_addrs=recipients)
    if refused:
        raise ProviderUnavailableError(f"SMTP provider refused {len(refused)} recipient(s)")
    return {
        "provider": selected,
        "provider_type": "smtp",
        "message_id": str(message["Message-ID"]),
        "recipient_count": len(recipients),
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def append_audit_event(path: str | Path, event: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(event, sort_keys=True, separators=(",", ":"))
    with target.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")


def audit_delivery_event(preview: dict[str, Any], delivery: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "outbound_message_submitted",
        "occurred_at": delivery["submitted_at"],
        "control_id": preview["control_id"],
        "case_id": preview["request"].get("case_id"),
        "action_id": preview["request"].get("action_id"),
        "provider": delivery["provider"],
        "provider_type": delivery["provider_type"],
        "provider_message_id_sha256": hashlib.sha256(
            delivery["message_id"].encode("utf-8")
        ).hexdigest(),
        "recipient_count": delivery["recipient_count"],
        "action_token_sha256": preview["action_token_sha256"],
        "policy_contract": outbound_mail_policy.CONTRACT,
        "gateway_contract": CONTRACT,
    }


def send_message(
    config: dict[str, Any],
    base_policy: dict[str, Any],
    payload: dict[str, Any],
    *,
    confirmation: bool,
    audit_path: str | Path | None = None,
) -> dict[str, Any]:
    preview = compose_preview(config, base_policy, payload)
    policy = runtime_policy(base_policy, preview["request"])
    _delivery_gate(config, policy, confirmation)
    selected = config["provider"]["selected"]
    provider_type = config["provider"]["profiles"][selected]["type"]
    if provider_type == "smtp":
        delivery = submit_smtp(config, preview)
    elif provider_type in {"gmail_api", "webhook"}:
        raise ProviderUnavailableError(
            f"{provider_type} provider contract exists but its live adapter is not installed"
        )
    else:
        raise ProviderUnavailableError("no delivery provider is selected")

    event = audit_delivery_event(preview, delivery)
    if audit_path is not None and base_policy["audit"]["write_jsonl"]:
        append_audit_event(audit_path, event)
    return {
        "delivery": delivery,
        "control_id": preview["control_id"],
        "action_url": preview["action_url"],
        "audit_event": event,
    }


def read_audit_events(path: str | Path, limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    target = Path(path)
    if not target.is_file():
        return []
    lines = target.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events
