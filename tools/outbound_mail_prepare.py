#!/usr/bin/env python3
"""Prepare a controlled WW.CX outbound message without sending it.

The CLI is intended for authenticated operator workflows, approved applications,
and future ChatGPT-to-WW.CX handoffs. It applies the same gateway policy, footer,
control headers, and audit hashing as the admin console. It performs no network
request and cannot submit mail.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_gateway  # noqa: E402
import outbound_mail_policy  # noqa: E402


DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
EXAMPLE_REQUEST = {
    "from_address": "john@ww.cx",
    "to": ["records@example.com"],
    "cc": [],
    "bcc": [],
    "subject": "Records request follow-up",
    "body": "Hello,\n\nPlease provide the requested records.\n",
    "message_class": "business_correspondence",
    "signer_name": "John Kaminski",
    "signer_title": "Authorized Representative",
    "case_id": "MATTER-001",
    "action_id": "ACTION-001",
    "mailing_address": "CONFIGURE BEFORE OPERATIONAL USE",
    "reply_to": "john@ww.cx",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a policy-controlled outbound message without sending mail."
    )
    parser.add_argument(
        "--input",
        default="-",
        help="JSON request file, or '-' for standard input (default).",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Gateway configuration JSON path.",
    )
    parser.add_argument(
        "--policy",
        default="",
        help="Policy JSON path. Defaults to the path declared by the gateway config.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Prepared JSON output path, or '-' for standard output (default).",
    )
    parser.add_argument(
        "--body-output",
        default="",
        help="Optional path for the copy-ready plain-text message body.",
    )
    parser.add_argument(
        "--audit-jsonl",
        default="",
        help="Optional JSONL audit destination. The raw body and action token are excluded.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the prepared JSON artifact.",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Print an example request and exit.",
    )
    return parser.parse_args(argv)


def load_request(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path_text).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"request JSON is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def resolve_policy_path(config: dict[str, Any], override: str) -> Path:
    if override:
        return Path(override).resolve()
    return outbound_mail_gateway.resolve_repo_path(
        REPO_ROOT,
        str(config["paths"]["policy"]),
    )


def prepare_artifact(
    config: dict[str, Any],
    policy: dict[str, Any],
    request: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    requested_from = str(
        request.get("from_address") or policy["organization"]["contact_email"]
    )
    validated_from = outbound_mail_policy.validate_from_address(policy, requested_from)
    effective_policy = copy.deepcopy(policy)
    effective_policy["organization"]["contact_email"] = validated_from
    outbound_mail_policy.validate_policy(effective_policy)

    preview = outbound_mail_gateway.compose_preview(config, effective_policy, request)
    public_request = {
        key: value
        for key, value in preview["request"].items()
        if key != "body"
    }
    artifact = {
        "contract": "wwcx.outbound-mail-prepared.v1",
        "status": "prepared_not_sent",
        "network_activity": False,
        "external_delivery_attempted": False,
        "request": public_request,
        "control_id": preview["control_id"],
        "action_url": preview["action_url"],
        "action_token_sha256": preview["action_token_sha256"],
        "headers": preview["headers"],
        "body": preview["body"],
        "audit_record": preview["audit_record"],
    }
    audit_record = copy.deepcopy(preview["audit_record"])
    audit_record["source"] = "outbound_mail_prepare_cli"
    audit_record["delivery_status"] = "prepared_not_sent"
    return artifact, audit_record


def write_text(path_text: str, value: str) -> None:
    if path_text == "-":
        sys.stdout.write(value)
        if value and not value.endswith("\n"):
            sys.stdout.write("\n")
        return
    target = Path(path_text)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.example:
        write_text(args.output, json.dumps(EXAMPLE_REQUEST, indent=2) + "\n")
        return 0

    try:
        config_path = Path(args.config).resolve()
        config = outbound_mail_gateway.load_json(config_path)
        outbound_mail_gateway.validate_gateway_config(config)
        policy_path = resolve_policy_path(config, args.policy)
        policy = outbound_mail_gateway.load_json(policy_path)
        outbound_mail_policy.validate_policy(policy)
        request = load_request(args.input)
        artifact, audit_record = prepare_artifact(config, policy, request)

        indent = 2 if args.pretty else None
        separators = None if args.pretty else (",", ":")
        serialized = json.dumps(
            artifact,
            indent=indent,
            separators=separators,
            sort_keys=True,
        ) + "\n"
        write_text(args.output, serialized)
        if args.body_output:
            write_text(args.body_output, artifact["body"])
        if args.audit_jsonl:
            outbound_mail_gateway.append_audit_event(args.audit_jsonl, audit_record)
        return 0
    except (OSError, ValueError, KeyError, outbound_mail_gateway.GatewayError) as exc:
        print(f"outbound-mail-prepare: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
