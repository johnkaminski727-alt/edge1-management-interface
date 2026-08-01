#!/usr/bin/env python3
"""Disabled-by-default inbound mail routing core for WW.CX.

This module does not open an SMTP listener or alter MX records. It validates a
normalized inbound envelope supplied by an authenticated provider webhook or a
trusted local MTA adapter, resolves recipients, and emits minimal audit events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT = "wwcx.inbound-mail-hub.v1"
SUPPORTED_INGRESS_TYPES = {"disabled", "webhook", "local_mta"}
SUPPORTED_DESTINATION_TYPES = {"mailbox", "webhook", "quarantine"}
UNKNOWN_ACTIONS = {"reject", "quarantine"}


class InboundHubError(RuntimeError):
    """Base inbound hub error."""


class ConfigurationError(InboundHubError):
    """Raised for invalid configuration."""


class IngressDisabledError(InboundHubError):
    """Raised when an inbound delivery reaches a closed gate."""


class AuthenticationError(InboundHubError):
    """Raised when ingress authentication fails."""


@dataclass(frozen=True)
class RouteDecision:
    recipient: str
    action: str
    destination_type: str
    destination: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipient": self.recipient,
            "action": self.action,
            "destination_type": self.destination_type,
            "destination": self.destination,
            "reason": self.reason,
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


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label} must be non-empty text")
    return value.strip()


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{label} must be boolean")


def _require_int(value: Any, label: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConfigurationError(f"{label} must be between {minimum} and {maximum}")


def normalize_address(value: Any) -> str:
    address = _require_text(value, "address").casefold()
    if "\r" in address or "\n" in address or address.count("@") != 1:
        raise InboundHubError("invalid email address")
    local, domain = address.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise InboundHubError("invalid email address")
    return address


def validate_config(config: dict[str, Any]) -> None:
    _require_exact_keys(
        config,
        {
            "contract", "enabled", "deployment_authorized",
            "production_routing_authorized", "listen", "paths", "ingress",
            "domains", "routing", "limits", "content",
        },
        "hub",
    )
    if config["contract"] != CONTRACT:
        raise ConfigurationError("unsupported inbound hub contract")
    for key in ("enabled", "deployment_authorized", "production_routing_authorized"):
        _require_bool(config[key], key)

    listen = config["listen"]
    _require_exact_keys(listen, {"host", "port"}, "listen")
    _require_text(listen["host"], "listen.host")
    _require_int(listen["port"], "listen.port", 1, 65535)

    paths = config["paths"]
    _require_exact_keys(paths, {"audit_jsonl", "quarantine_jsonl"}, "paths")
    _require_text(paths["audit_jsonl"], "paths.audit_jsonl")
    _require_text(paths["quarantine_jsonl"], "paths.quarantine_jsonl")

    ingress = config["ingress"]
    _require_exact_keys(ingress, {"selected", "profiles"}, "ingress")
    selected = _require_text(ingress["selected"], "ingress.selected")
    profiles = ingress["profiles"]
    if not isinstance(profiles, dict) or selected not in profiles:
        raise ConfigurationError("selected ingress profile does not exist")
    for name, profile in profiles.items():
        _require_text(name, "ingress profile name")
        if not isinstance(profile, dict):
            raise ConfigurationError(f"ingress profile {name} must be an object")
        profile_type = _require_text(profile.get("type"), f"ingress.{name}.type")
        if profile_type not in SUPPORTED_INGRESS_TYPES:
            raise ConfigurationError(f"unsupported ingress type: {profile_type}")
        _require_bool(profile.get("enabled"), f"ingress.{name}.enabled")
        if profile_type == "webhook":
            _require_exact_keys(profile, {"type", "enabled", "secret_env"}, f"ingress.{name}")
            _require_text(profile["secret_env"], f"ingress.{name}.secret_env")
        elif profile_type == "local_mta":
            _require_exact_keys(profile, {"type", "enabled", "trusted_token_env"}, f"ingress.{name}")
            _require_text(profile["trusted_token_env"], f"ingress.{name}.trusted_token_env")
        else:
            _require_exact_keys(profile, {"type", "enabled"}, f"ingress.{name}")

    domains = config["domains"]
    if not isinstance(domains, list) or not domains:
        raise ConfigurationError("domains must be a non-empty list")
    normalized_domains = {_require_text(item, "domain").casefold() for item in domains}
    if len(normalized_domains) != len(domains):
        raise ConfigurationError("domains must be unique")

    routing = config["routing"]
    _require_exact_keys(routing, {"unknown_recipient_action", "routes"}, "routing")
    if routing["unknown_recipient_action"] not in UNKNOWN_ACTIONS:
        raise ConfigurationError("unknown recipient action is unsupported")
    routes = routing["routes"]
    if not isinstance(routes, dict):
        raise ConfigurationError("routing.routes must be an object")
    for recipient, route in routes.items():
        normalized = normalize_address(recipient)
        if normalized != recipient:
            raise ConfigurationError("route keys must be normalized lowercase addresses")
        if normalized.rsplit("@", 1)[1] not in normalized_domains:
            raise ConfigurationError("route recipient is outside configured domains")
        _require_exact_keys(route, {"destination_type", "destination", "enabled"}, f"route.{recipient}")
        if route["destination_type"] not in SUPPORTED_DESTINATION_TYPES:
            raise ConfigurationError("route destination type is unsupported")
        _require_text(route["destination"], f"route.{recipient}.destination")
        _require_bool(route["enabled"], f"route.{recipient}.enabled")

    limits = config["limits"]
    _require_exact_keys(limits, {"max_message_bytes", "max_recipient_count", "audit_view_limit"}, "limits")
    _require_int(limits["max_message_bytes"], "limits.max_message_bytes", 1024, 100 * 1024 * 1024)
    _require_int(limits["max_recipient_count"], "limits.max_recipient_count", 1, 500)
    _require_int(limits["audit_view_limit"], "limits.audit_view_limit", 1, 5000)

    content = config["content"]
    _require_exact_keys(
        content,
        {"persist_raw_message", "persist_attachment_bytes", "persist_body_preview", "retention_days"},
        "content",
    )
    for key in ("persist_raw_message", "persist_attachment_bytes", "persist_body_preview"):
        _require_bool(content[key], f"content.{key}")
    _require_int(content["retention_days"], "content.retention_days", 1, 730)

    if config["enabled"]:
        if not config["deployment_authorized"] or not config["production_routing_authorized"]:
            raise ConfigurationError("enabled hub requires deployment and production routing authorization")
        profile = profiles[selected]
        if profile["type"] == "disabled" or not profile["enabled"]:
            raise ConfigurationError("enabled hub requires an enabled ingress profile")


def status_payload(config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    selected = config["ingress"]["selected"]
    profile = config["ingress"]["profiles"][selected]
    secret_name = profile.get("secret_env") or profile.get("trusted_token_env")
    configured = bool(secret_name and os.environ.get(secret_name, "").strip())
    ready = bool(
        config["enabled"]
        and config["deployment_authorized"]
        and config["production_routing_authorized"]
        and profile["enabled"]
        and profile["type"] != "disabled"
        and configured
    )
    return {
        "hub": "wwcx-inbound-mail-hub",
        "contract": CONTRACT,
        "state": "ready" if ready else "disabled",
        "production_routing_enabled": ready,
        "selected_ingress": selected,
        "ingress_type": profile["type"],
        "ingress_configured": configured,
        "domains": list(config["domains"]),
        "route_count": len(config["routing"]["routes"]),
        "unknown_recipient_action": config["routing"]["unknown_recipient_action"],
        "persist_raw_message": config["content"]["persist_raw_message"],
        "persist_attachment_bytes": config["content"]["persist_attachment_bytes"],
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def authenticate(config: dict[str, Any], supplied_token: str | None) -> None:
    validate_config(config)
    selected = config["ingress"]["selected"]
    profile = config["ingress"]["profiles"][selected]
    env_name = profile.get("secret_env") or profile.get("trusted_token_env")
    expected = os.environ.get(env_name, "") if env_name else ""
    if not expected or not supplied_token or not hmac.compare_digest(expected, supplied_token):
        raise AuthenticationError("inbound ingress authentication failed")


def normalize_envelope(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    if not isinstance(payload, dict):
        raise InboundHubError("payload must be an object")
    envelope_from = normalize_address(payload.get("envelope_from"))
    recipients_raw = payload.get("recipients")
    if not isinstance(recipients_raw, list) or not recipients_raw:
        raise InboundHubError("recipients must be a non-empty list")
    recipients = sorted({normalize_address(item) for item in recipients_raw})
    if len(recipients) > config["limits"]["max_recipient_count"]:
        raise InboundHubError("recipient count exceeds configured limit")
    message_size = payload.get("message_size")
    if not isinstance(message_size, int) or message_size < 0:
        raise InboundHubError("message_size must be a non-negative integer")
    if message_size > config["limits"]["max_message_bytes"]:
        raise InboundHubError("message exceeds configured size limit")
    provider_id = _require_text(payload.get("provider_message_id"), "provider_message_id")
    subject = str(payload.get("subject", ""))
    return {
        "envelope_from": envelope_from,
        "recipients": recipients,
        "message_size": message_size,
        "provider_message_id": provider_id,
        "provider_message_id_sha256": hashlib.sha256(provider_id.encode("utf-8")).hexdigest(),
        "subject_sha256": hashlib.sha256(subject.encode("utf-8")).hexdigest(),
    }


def route_envelope(config: dict[str, Any], envelope: dict[str, Any]) -> list[RouteDecision]:
    validate_config(config)
    domains = {item.casefold() for item in config["domains"]}
    routes = config["routing"]["routes"]
    unknown_action = config["routing"]["unknown_recipient_action"]
    decisions: list[RouteDecision] = []
    for recipient in envelope["recipients"]:
        domain = recipient.rsplit("@", 1)[1]
        if domain not in domains:
            decisions.append(RouteDecision(recipient, "reject", "quarantine", None, "domain_not_managed"))
            continue
        route = routes.get(recipient)
        if route and route["enabled"]:
            decisions.append(
                RouteDecision(
                    recipient,
                    "route",
                    route["destination_type"],
                    route["destination"],
                    "explicit_route",
                )
            )
        else:
            decisions.append(
                RouteDecision(
                    recipient,
                    unknown_action,
                    "quarantine",
                    None,
                    "unknown_recipient",
                )
            )
    return decisions


def process_ingress(config: dict[str, Any], payload: dict[str, Any], supplied_token: str | None) -> dict[str, Any]:
    validate_config(config)
    if not config["enabled"] or not config["production_routing_authorized"]:
        raise IngressDisabledError("inbound production routing is disabled")
    authenticate(config, supplied_token)
    envelope = normalize_envelope(config, payload)
    decisions = route_envelope(config, envelope)
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event = {
        "event": "inbound_message_routed",
        "occurred_at": occurred_at,
        "provider_message_id_sha256": envelope["provider_message_id_sha256"],
        "envelope_from_sha256": hashlib.sha256(envelope["envelope_from"].encode("utf-8")).hexdigest(),
        "subject_sha256": envelope["subject_sha256"],
        "message_size": envelope["message_size"],
        "recipient_count": len(envelope["recipients"]),
        "decisions": [item.to_dict() for item in decisions],
        "contract": CONTRACT,
    }
    return {"accepted": all(item.action != "reject" for item in decisions), "event": event}


def append_jsonl(path: str | Path, event: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def read_events(path: str | Path, limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    target = Path(path)
    if not target.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in reversed(target.read_text(encoding="utf-8").splitlines()[-limit:]):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events
