#!/usr/bin/env python3
"""Policy and composition helpers for the WW.CX outbound-mail gateway.

The module prepares controlled outbound messages. It does not deliver mail.
Live delivery is a separate provider action and remains disabled unless the
policy explicitly authorizes it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

CONTRACT = "wwcx.outbound-mail-policy.v1"
FOOTER_MARKER = "[WWCX-CORRESPONDENCE-CONTROL]"
PLACEHOLDER_ADDRESS = "CONFIGURE_AT_DEPLOYMENT"
ALLOWED_MESSAGE_CLASSES = {
    "business_correspondence",
    "commercial",
    "legal_notice",
    "support",
}
ALLOWED_PROVIDERS = {
    "disabled",
    "smtp_submission",
    "gmail_api",
    "microsoft_graph",
    "manual_export",
}
CONTROL_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{5,127}$")
HEADER_VALUE_RE = re.compile(r"^[\x20-\x7e]{1,998}$")
EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


def load_policy(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f"{label} keys invalid; missing={missing}, unexpected={unexpected}")


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    _require_exact_keys(
        policy,
        {
            "contract",
            "enabled",
            "deployment_authorized",
            "smtp_cutover_authorized",
            "organization",
            "footer",
            "tracking",
            "audit",
            "delivery",
        },
        "policy",
    )
    if policy["contract"] != CONTRACT:
        raise ValueError("unsupported policy contract")

    for key in ("enabled", "deployment_authorized", "smtp_cutover_authorized"):
        _require_bool(policy[key], key)

    organization = policy["organization"]
    _require_exact_keys(
        organization,
        {
            "legal_name",
            "operating_name",
            "website",
            "privacy_url",
            "contact_email",
            "mailing_address",
        },
        "organization",
    )
    for key in organization:
        _require_text(organization[key], f"organization.{key}")
    if not EMAIL_RE.fullmatch(organization["contact_email"]):
        raise ValueError("organization.contact_email is invalid")

    footer = policy["footer"]
    _require_exact_keys(
        footer,
        {
            "append_to_plain_text",
            "append_to_html",
            "include_confidentiality_notice",
            "include_non_creation_caveat",
            "include_action_link",
            "include_tracking_disclosure",
            "require_unsubscribe_for_commercial",
        },
        "footer",
    )
    for key, value in footer.items():
        _require_bool(value, f"footer.{key}")

    tracking = policy["tracking"]
    _require_exact_keys(
        tracking,
        {
            "action_base_url",
            "transparent_action_links",
            "hidden_open_tracking",
            "device_fingerprinting",
            "collect_full_ip",
            "ip_storage_mode",
            "retention_days",
        },
        "tracking",
    )
    _require_text(tracking["action_base_url"], "tracking.action_base_url")
    for key in (
        "transparent_action_links",
        "hidden_open_tracking",
        "device_fingerprinting",
        "collect_full_ip",
    ):
        _require_bool(tracking[key], f"tracking.{key}")
    if tracking["hidden_open_tracking"]:
        raise ValueError("hidden open tracking is prohibited")
    if tracking["device_fingerprinting"]:
        raise ValueError("device fingerprinting is prohibited")
    if tracking["collect_full_ip"]:
        raise ValueError("full IP-address storage is prohibited by this contract")
    if tracking["ip_storage_mode"] not in {"none", "truncated", "keyed_hash"}:
        raise ValueError("tracking.ip_storage_mode is unsupported")
    if not isinstance(tracking["retention_days"], int) or not 1 <= tracking["retention_days"] <= 730:
        raise ValueError("tracking.retention_days must be between 1 and 730")

    audit = policy["audit"]
    _require_exact_keys(
        audit,
        {
            "write_jsonl",
            "record_recipient_addresses",
            "record_body",
            "record_action_token",
            "record_action_token_hash",
        },
        "audit",
    )
    for key, value in audit.items():
        _require_bool(value, f"audit.{key}")
    if audit["record_body"]:
        raise ValueError("message bodies must not be copied into the audit event")
    if audit["record_action_token"]:
        raise ValueError("raw action tokens must not be written to the audit event")
    if not audit["record_action_token_hash"]:
        raise ValueError("the action-token hash is required for correlation and revocation")

    delivery = policy["delivery"]
    _require_exact_keys(
        delivery,
        {
            "provider",
            "allow_prepare",
            "allow_external_submission",
            "allow_live_delivery",
            "allowed_from_domains",
            "max_recipients",
            "message_size_limit_bytes",
        },
        "delivery",
    )
    if delivery["provider"] not in ALLOWED_PROVIDERS:
        raise ValueError("delivery.provider is unsupported")
    for key in ("allow_prepare", "allow_external_submission", "allow_live_delivery"):
        _require_bool(delivery[key], f"delivery.{key}")
    if not isinstance(delivery["allowed_from_domains"], list) or not delivery["allowed_from_domains"]:
        raise ValueError("delivery.allowed_from_domains must be a non-empty list")
    for domain in delivery["allowed_from_domains"]:
        domain_text = _require_text(domain, "delivery.allowed_from_domains item").casefold()
        if "." not in domain_text or "@" in domain_text:
            raise ValueError("delivery.allowed_from_domains contains an invalid domain")
    if not isinstance(delivery["max_recipients"], int) or not 1 <= delivery["max_recipients"] <= 500:
        raise ValueError("delivery.max_recipients must be between 1 and 500")
    if not isinstance(delivery["message_size_limit_bytes"], int) or not 1024 <= delivery["message_size_limit_bytes"] <= 10_485_760:
        raise ValueError("delivery.message_size_limit_bytes is outside the supported range")

    if policy["enabled"] and not policy["deployment_authorized"]:
        raise ValueError("enabled policy requires deployment authorization")
    if delivery["allow_external_submission"] and not policy["enabled"]:
        raise ValueError("external submission requires an enabled policy")
    if delivery["allow_live_delivery"]:
        if not policy["enabled"] or not policy["deployment_authorized"]:
            raise ValueError("live delivery requires an enabled, deployment-authorized policy")
        if not policy["smtp_cutover_authorized"]:
            raise ValueError("live delivery requires explicit SMTP/API cutover authorization")
        if delivery["provider"] in {"disabled", "manual_export"}:
            raise ValueError("live delivery requires a delivery-capable provider")
        if organization["mailing_address"] == PLACEHOLDER_ADDRESS:
            raise ValueError("live delivery requires a configured mailing address")

    if footer["include_action_link"]:
        if not tracking["transparent_action_links"]:
            raise ValueError("action links must be transparent")
        if not footer["include_tracking_disclosure"]:
            raise ValueError("action links require a tracking disclosure")


def normalize_recipients(recipients: Iterable[str], *, max_count: int = 500) -> list[str]:
    normalized: list[str] = []
    for recipient in recipients:
        value = _require_text(recipient, "recipient").casefold()
        if "\r" in value or "\n" in value or not EMAIL_RE.fullmatch(value):
            raise ValueError("recipient address is invalid")
        normalized.append(value)
    normalized = sorted(set(normalized))
    if not normalized:
        raise ValueError("at least one recipient is required")
    if len(normalized) > max_count:
        raise ValueError("recipient count exceeds the configured maximum")
    return normalized


def validate_from_address(policy: dict[str, Any], from_address: str) -> str:
    validate_policy(policy)
    address = _require_text(from_address, "from_address").casefold()
    if not EMAIL_RE.fullmatch(address):
        raise ValueError("from_address is invalid")
    domain = address.rsplit("@", 1)[1]
    allowed = {str(item).casefold() for item in policy["delivery"]["allowed_from_domains"]}
    if domain not in allowed:
        raise ValueError("from_address domain is not allowed")
    return address


def generate_action_token(byte_count: int = 32) -> tuple[str, str]:
    if not isinstance(byte_count, int) or not 16 <= byte_count <= 64:
        raise ValueError("byte_count must be between 16 and 64")
    token = secrets.token_urlsafe(byte_count)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, digest


def build_action_url(base_url: str, token: str) -> str:
    base = _require_text(base_url, "base_url").rstrip("/")
    opaque = _require_text(token, "token")
    return f"{base}/{quote(opaque, safe='')}"


def derive_control_id(
    subject: str,
    recipients: Iterable[str],
    *,
    namespace: str = "WWCX",
    now: datetime | None = None,
) -> str:
    timestamp = now or datetime.now(timezone.utc)
    normalized_recipients = normalize_recipients(recipients)
    material = json.dumps(
        {
            "subject": _require_text(subject, "subject"),
            "recipients": normalized_recipients,
            "time": timestamp.isoformat(timespec="seconds"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    suffix = hashlib.sha256(material).hexdigest()[:12].upper()
    return f"{namespace}-{timestamp:%Y%m%dT%H%M%SZ}-{suffix}"


def _validate_control_id(value: str, label: str) -> str:
    control_id = _require_text(value, label)
    if not CONTROL_ID_RE.fullmatch(control_id):
        raise ValueError(f"{label} contains unsupported characters")
    return control_id


def build_control_headers(
    *,
    control_id: str,
    case_id: str | None = None,
    action_id: str | None = None,
    policy_contract: str = CONTRACT,
) -> dict[str, str]:
    headers = {
        "X-WWCX-Control-ID": _validate_control_id(control_id, "control_id"),
        "X-WWCX-Policy": _require_text(policy_contract, "policy_contract"),
        "X-WWCX-Tracking": "disclosed-action-link; no-hidden-pixel",
    }
    if case_id:
        headers["X-WWCX-Case-ID"] = _validate_control_id(case_id, "case_id")
    if action_id:
        headers["X-WWCX-Action-ID"] = _validate_control_id(action_id, "action_id")
    for name, value in headers.items():
        if not HEADER_VALUE_RE.fullmatch(value) or "\r" in value or "\n" in value:
            raise ValueError(f"unsafe header value for {name}")
    return headers


def render_plain_text_footer(
    policy: dict[str, Any],
    *,
    message_class: str,
    signer_name: str,
    signer_title: str,
    control_id: str,
    action_url: str | None,
    unsubscribe_url: str | None = None,
) -> str:
    validate_policy(policy)
    if message_class not in ALLOWED_MESSAGE_CLASSES:
        raise ValueError("unsupported message class")
    organization = policy["organization"]
    footer = policy["footer"]
    if message_class == "commercial" and footer["require_unsubscribe_for_commercial"]:
        _require_text(unsubscribe_url, "unsubscribe_url")

    lines = [
        "--",
        _require_text(signer_name, "signer_name"),
        _require_text(signer_title, "signer_title"),
        f"{organization['operating_name']} | {organization['legal_name']}",
        organization["mailing_address"],
        f"Email: {organization['contact_email']} | Web: {organization['website']}",
        "",
        FOOTER_MARKER,
        f"Correspondence control: {_validate_control_id(control_id, 'control_id')}",
    ]
    if footer["include_action_link"]:
        lines.append(
            "View the correspondence record or acknowledge receipt: "
            + _require_text(action_url, "action_url")
        )
    if footer["include_tracking_disclosure"]:
        lines.append(
            "Access to the linked correspondence record may be logged for security, "
            "delivery verification, records management, and dispute resolution."
        )
        lines.append(f"Privacy information: {organization['privacy_url']}")
    if footer["include_confidentiality_notice"]:
        lines.extend(
            [
                "",
                "CONFIDENTIALITY AND RECORDS NOTICE: This message and any attachments may "
                "contain confidential information intended for the addressed recipient. "
                "If received in error, notify the sender and delete the material.",
            ]
        )
    if footer["include_non_creation_caveat"]:
        lines.append(
            "This notice does not create confidentiality, privilege, a contractual duty, "
            "or other legal rights where they do not otherwise exist."
        )
    if message_class == "commercial" and unsubscribe_url:
        lines.extend(["", f"Commercial-message preferences or unsubscribe: {unsubscribe_url}"])
    return "\n".join(lines).rstrip() + "\n"


def render_html_footer(
    policy: dict[str, Any],
    *,
    message_class: str,
    signer_name: str,
    signer_title: str,
    control_id: str,
    action_url: str | None,
    unsubscribe_url: str | None = None,
) -> str:
    plain = render_plain_text_footer(
        policy,
        message_class=message_class,
        signer_name=signer_name,
        signer_title=signer_title,
        control_id=control_id,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url,
    )
    paragraphs = [escape(line) for line in plain.rstrip().split("\n")]
    return (
        '<div data-wwcx-correspondence-control="1" '
        'style="margin-top:24px;border-top:1px solid #bbb;padding-top:14px;'
        'font-family:Arial,sans-serif;font-size:12px;line-height:1.45;color:#444">'
        + "<br>".join(paragraphs)
        + "</div>"
    )


def append_plain_text_footer(body: str, footer: str) -> str:
    message_body = body.rstrip()
    if FOOTER_MARKER in message_body:
        return message_body + "\n"
    return f"{message_body}\n\n{footer}" if message_body else footer


def append_html_footer(body_html: str, footer_html: str) -> str:
    if 'data-wwcx-correspondence-control="1"' in body_html:
        return body_html
    return body_html.rstrip() + footer_html


def build_audit_record(
    policy: dict[str, Any],
    *,
    control_id: str,
    message_class: str,
    subject: str,
    body: str,
    recipients: Iterable[str],
    token_hash: str,
    from_address: str,
    case_id: str | None = None,
    action_id: str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    if message_class not in ALLOWED_MESSAGE_CLASSES:
        raise ValueError("unsupported message class")
    event_time = timestamp or datetime.now(timezone.utc)
    normalized_recipients = normalize_recipients(
        recipients,
        max_count=policy["delivery"]["max_recipients"],
    )
    record: dict[str, Any] = {
        "event": "outbound_message_prepared",
        "occurred_at": event_time.isoformat(timespec="seconds"),
        "control_id": _validate_control_id(control_id, "control_id"),
        "message_class": message_class,
        "subject_sha256": hashlib.sha256(_require_text(subject, "subject").encode("utf-8")).hexdigest(),
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "recipient_count": len(normalized_recipients),
        "from_address": validate_from_address(policy, from_address),
        "action_token_sha256": _require_text(token_hash, "token_hash"),
        "policy_contract": CONTRACT,
        "delivery_provider": policy["delivery"]["provider"],
        "live_delivery_authorized": policy["delivery"]["allow_live_delivery"],
    }
    if policy["audit"]["record_recipient_addresses"]:
        record["recipients"] = normalized_recipients
    if case_id:
        record["case_id"] = _validate_control_id(case_id, "case_id")
    if action_id:
        record["action_id"] = _validate_control_id(action_id, "action_id")
    return record


def compose_message(
    policy: dict[str, Any],
    *,
    body: str,
    subject: str,
    recipients: Iterable[str],
    from_address: str,
    signer_name: str,
    signer_title: str,
    message_class: str = "business_correspondence",
    body_html: str | None = None,
    control_id: str | None = None,
    case_id: str | None = None,
    action_id: str | None = None,
    unsubscribe_url: str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    if not policy["delivery"]["allow_prepare"]:
        raise ValueError("message preparation is disabled")
    event_time = timestamp or datetime.now(timezone.utc)
    normalized_recipients = normalize_recipients(
        recipients,
        max_count=policy["delivery"]["max_recipients"],
    )
    resolved_from = validate_from_address(policy, from_address)
    resolved_control_id = control_id or derive_control_id(
        subject,
        normalized_recipients,
        now=event_time,
    )
    token, token_hash = generate_action_token()
    action_url = build_action_url(policy["tracking"]["action_base_url"], token)
    plain_footer = render_plain_text_footer(
        policy,
        message_class=message_class,
        signer_name=signer_name,
        signer_title=signer_title,
        control_id=resolved_control_id,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url,
    )
    composed_body = append_plain_text_footer(body, plain_footer)
    composed_html = None
    if body_html is not None:
        html_footer = render_html_footer(
            policy,
            message_class=message_class,
            signer_name=signer_name,
            signer_title=signer_title,
            control_id=resolved_control_id,
            action_url=action_url,
            unsubscribe_url=unsubscribe_url,
        )
        composed_html = append_html_footer(body_html, html_footer)
    total_size = len(composed_body.encode("utf-8")) + len((composed_html or "").encode("utf-8"))
    if total_size > policy["delivery"]["message_size_limit_bytes"]:
        raise ValueError("prepared message exceeds the configured size limit")

    headers = build_control_headers(
        control_id=resolved_control_id,
        case_id=case_id,
        action_id=action_id,
    )
    audit_record = build_audit_record(
        policy,
        control_id=resolved_control_id,
        message_class=message_class,
        subject=subject,
        body=body,
        recipients=normalized_recipients,
        token_hash=token_hash,
        from_address=resolved_from,
        case_id=case_id,
        action_id=action_id,
        timestamp=event_time,
    )
    return {
        "body": composed_body,
        "html_body": composed_html,
        "headers": headers,
        "control_id": resolved_control_id,
        "action_url": action_url,
        "action_token": token,
        "action_token_sha256": token_hash,
        "from_address": resolved_from,
        "recipients": normalized_recipients,
        "audit_record": audit_record,
        "delivery": {
            "provider": policy["delivery"]["provider"],
            "live_delivery_authorized": policy["delivery"]["allow_live_delivery"],
            "status": "prepared_not_sent",
        },
    }


def activated_prepare_only_copy(policy: dict[str, Any], mailing_address: str) -> dict[str, Any]:
    """Return a safe preview/API candidate without enabling live delivery."""
    candidate = copy.deepcopy(policy)
    candidate["enabled"] = True
    candidate["deployment_authorized"] = True
    candidate["organization"]["mailing_address"] = _require_text(mailing_address, "mailing_address")
    candidate["delivery"]["allow_prepare"] = True
    candidate["delivery"]["allow_external_submission"] = True
    candidate["delivery"]["allow_live_delivery"] = False
    candidate["delivery"]["provider"] = "manual_export"
    validate_policy(candidate)
    return candidate
