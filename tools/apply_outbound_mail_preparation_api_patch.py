#!/usr/bin/env python3
"""One-shot source patch for the disabled authenticated preparation API foundation."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path_text: str, old: str, new: str, label: str) -> None:
    path = ROOT / path_text
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path_text: str, pattern: str, replacement: str, label: str) -> None:
    path = ROOT / path_text
    text = path.read_text(encoding="utf-8")
    match = re.search(pattern, text, flags=re.S)
    if match is None:
        raise SystemExit(f"{label}: expected one regex match, found 0")
    if re.search(pattern, text[match.end() :], flags=re.S) is not None:
        raise SystemExit(f"{label}: regex match was not unique")
    path.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")


def update_config() -> None:
    path = ROOT / "config/messaging/outbound-mail-gateway.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    preparation_api = {
        "enabled": False,
        "authentication": "hmac_sha256",
        "secret_env": "WWCX_MAIL_GATEWAY_TOKEN",
        "allowed_clients": ["wwcx-website-admin"],
        "clock_skew_seconds": 300,
        "nonce_ttl_seconds": 900,
        "nonce_store": "var/outbound-mail/preparation-nonces.sqlite3",
        "max_request_bytes": 327680,
    }
    ordered: dict[str, object] = {}
    for key, value in config.items():
        if key == "preparation_api":
            continue
        ordered[key] = value
        if key == "admin":
            ordered["preparation_api"] = preparation_api
    if "preparation_api" not in ordered:
        raise SystemExit("admin configuration anchor was not found")
    path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")


def update_gateway_core() -> None:
    path = "server/outbound_mail_gateway.py"
    replace_once(
        path,
        "import outbound_mail_policy\n",
        "import outbound_mail_policy\nimport outbound_mail_preparation_auth\n",
        "gateway auth import",
    )
    replace_once(
        path,
        '            "provider",\n            "admin",\n            "content",',
        '            "provider",\n            "admin",\n            "preparation_api",\n            "content",',
        "gateway top-level preparation API key",
    )
    replace_once(
        path,
        '    _require_int(admin["audit_view_limit"], "admin.audit_view_limit", 1, 5000)\n\n'
        '    content = config["content"]',
        '    _require_int(admin["audit_view_limit"], "admin.audit_view_limit", 1, 5000)\n\n'
        '    try:\n'
        '        outbound_mail_preparation_auth.validate_config(config["preparation_api"])\n'
        '    except outbound_mail_preparation_auth.PreparationAuthConfigurationError as exc:\n'
        '        raise ConfigurationError(str(exc)) from exc\n\n'
        '    content = config["content"]',
        "gateway preparation API validation",
    )
    replace_once(
        path,
        '        "persist_attachment_bytes": config["content"]["persist_attachment_bytes"],\n'
        '        "providers": [item.to_dict() for item in statuses],',
        '        "persist_attachment_bytes": config["content"]["persist_attachment_bytes"],\n'
        '        "preparation_api": outbound_mail_preparation_auth.status_payload(\n'
        '            config["preparation_api"]\n'
        '        ),\n'
        '        "providers": [item.to_dict() for item in statuses],',
        "gateway preparation API status",
    )


def update_server() -> None:
    path = "server/outbound_mail_gateway_server.py"
    replace_once(
        path,
        "import argparse\nimport json\nimport sys\n",
        "import argparse\nimport json\nimport sys\nfrom datetime import datetime, timezone\n",
        "server datetime import",
    )
    replace_once(
        path,
        "import outbound_mail_policy\n",
        "import outbound_mail_policy\nimport outbound_mail_preparation_auth as preparation_auth\n",
        "server preparation auth import",
    )

    old_load = '''    def load(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
        config = gateway.load_json(self.config_path)
        gateway.validate_gateway_config(config)
        policy_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["policy"])
        audit_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["audit_jsonl"])
        policy = outbound_mail_policy.load_policy(policy_path)
        outbound_mail_policy.validate_policy(policy)
        identities = gateway.load_json(self.identities_path)
        mail_identity_registry.validate_registry(identities)
        return config, policy, identities, audit_path
'''
    new_load = '''    def load(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, Path]:
        config = gateway.load_json(self.config_path)
        gateway.validate_gateway_config(config)
        policy_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["policy"])
        audit_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["audit_jsonl"])
        nonce_path = gateway.resolve_repo_path(
            REPO_ROOT,
            config["preparation_api"]["nonce_store"],
        )
        policy = outbound_mail_policy.load_policy(policy_path)
        outbound_mail_policy.validate_policy(policy)
        identities = gateway.load_json(self.identities_path)
        mail_identity_registry.validate_registry(identities)
        return config, policy, identities, audit_path, nonce_path
'''
    replace_once(path, old_load, new_load, "server application load tuple")

    old_reader = '''    def _read_json(self, max_bytes: int) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise gateway.GatewayError("invalid Content-Length") from exc
        if length < 1 or length > max_bytes:
            raise gateway.GatewayError("request body length is invalid")
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise gateway.GatewayError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise gateway.GatewayError("request JSON must be an object")
        return payload
'''
    new_reader = '''    def _read_body(self, max_bytes: int) -> bytes:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise gateway.GatewayError("invalid Content-Length") from exc
        if length < 1 or length > max_bytes:
            raise gateway.GatewayError("request body length is invalid")
        return self.rfile.read(length)

    def _decode_json(self, body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise gateway.GatewayError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise gateway.GatewayError("request JSON must be an object")
        return payload

    def _read_json(self, max_bytes: int) -> dict[str, Any]:
        return self._decode_json(self._read_body(max_bytes))

    def _authenticate_preparation_api(
        self,
        config: dict[str, Any],
        nonce_path: Path,
        method: str,
        path: str,
        body: bytes,
    ) -> preparation_auth.VerifiedPreparationClient:
        return preparation_auth.verify_request(
            config["preparation_api"],
            dict(self.headers.items()),
            method,
            path,
            body,
            nonce_path,
        )
'''
    replace_once(path, old_reader, new_reader, "server body and authentication helpers")

    replace_once(
        path,
        "    def _handle_error(self, exc: Exception) -> None:\n"
        "        if isinstance(exc, gateway.DeliveryDisabledError):",
        "    def _handle_error(self, exc: Exception) -> None:\n"
        "        if isinstance(exc, preparation_auth.PreparationApiDisabledError):\n"
        "            status = HTTPStatus.FORBIDDEN\n"
        "            code = \"preparation_api_disabled\"\n"
        "        elif isinstance(exc, preparation_auth.PreparationAuthUnavailableError):\n"
        "            status = HTTPStatus.SERVICE_UNAVAILABLE\n"
        "            code = \"preparation_auth_unavailable\"\n"
        "        elif isinstance(exc, preparation_auth.PreparationReplayError):\n"
        "            status = HTTPStatus.CONFLICT\n"
        "            code = \"replay_detected\"\n"
        "        elif isinstance(exc, preparation_auth.InvalidPreparationAuthError):\n"
        "            status = HTTPStatus.UNAUTHORIZED\n"
        "            code = \"authentication_failed\"\n"
        "            exc = RuntimeError(\"Preparation API authentication failed.\")\n"
        "        elif isinstance(exc, gateway.DeliveryDisabledError):",
        "server authentication error mapping",
    )
    replace_once(
        path,
        "                gateway.ConfigurationError,\n"
        "                mail_identity_registry.IdentityRegistryError,",
        "                gateway.ConfigurationError,\n"
        "                preparation_auth.PreparationAuthConfigurationError,\n"
        "                mail_identity_registry.IdentityRegistryError,",
        "server authentication configuration mapping",
    )

    get_pattern = (
        r"(?P<prefix>    def do_GET\(self\) -> None:\n"
        r"        parsed = urlparse\(self\.path\)\n"
        r"        try:\n)"
        r"            config, policy, identities, audit_path = self\.application\.load\(\)\n"
    )
    path_obj = ROOT / path
    server_text = path_obj.read_text(encoding="utf-8")
    match = re.search(get_pattern, server_text)
    if match is None:
        raise SystemExit("server GET load tuple: expected function-scoped match")
    replacement = (
        match.group("prefix")
        + "            config, policy, identities, audit_path, nonce_path = self.application.load()\n"
    )
    path_obj.write_text(
        server_text[: match.start()] + replacement + server_text[match.end() :],
        encoding="utf-8",
    )

    status_anchor = '''            if parsed.path == "/outbound-mail/status":
                self._send_json(
                    HTTPStatus.OK,
                    identity_gateway.status_payload(config, policy, identities),
                )
                return
'''
    status_route = status_anchor + '''            if parsed.path == "/outbound-mail/api/v1/status":
                client = self._authenticate_preparation_api(
                    config,
                    nonce_path,
                    "GET",
                    parsed.path,
                    b"",
                )
                status_payload = identity_gateway.status_payload(config, policy, identities)
                status_payload["preparation_api"]["contract"] = (
                    "wwcx.outbound-mail-preparation-api.v1"
                )
                status_payload["preparation_api"]["authenticated_client_id"] = (
                    client.client_id
                )
                self._send_json(HTTPStatus.OK, status_payload)
                return
'''
    replace_once(path, status_anchor, status_route, "server authenticated status route")

    old_post = '''    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, policy, identities, audit_path = self.application.load()
            max_bytes = config["admin"]["max_body_bytes"] + 65536
            payload = self._read_json(max_bytes)
            if parsed.path == "/outbound-mail/preview":
                preview = identity_gateway.compose_preview(config, policy, identities, payload)
                preview.pop("action_token", None)
                self._send_json(HTTPStatus.OK, preview)
                return
            if parsed.path == "/outbound-mail/send":
                confirmation = payload.pop("confirm_send", False) is True
                result = identity_gateway.send_message(
                    config,
                    policy,
                    identities,
                    payload,
                    confirmation=confirmation,
                    audit_path=audit_path,
                )
                self._send_json(HTTPStatus.ACCEPTED, result)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:
            self._handle_error(exc)
'''
    new_post = '''    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, policy, identities, audit_path, nonce_path = self.application.load()
            if parsed.path == "/outbound-mail/api/v1/prepare":
                body = self._read_body(config["preparation_api"]["max_request_bytes"])
                client = self._authenticate_preparation_api(
                    config,
                    nonce_path,
                    "POST",
                    parsed.path,
                    body,
                )
                payload = self._decode_json(body)
                preview = identity_gateway.compose_preview(
                    config,
                    policy,
                    identities,
                    payload,
                )
                preview.pop("action_token", None)
                audit_event = dict(preview["audit_record"])
                audit_event.update(
                    {
                        "event": "outbound_message_prepared_api",
                        "occurred_at": datetime.now(timezone.utc).isoformat(
                            timespec="seconds"
                        ),
                        "client_id": client.client_id,
                        "sender_address": preview["request"]["from_address"],
                        "sender_selection_reason": preview["sender_selection"]["reason"],
                        "sender_identity_key": preview["sender_selection"]["identity_key"],
                        "delivery_status": "prepared_not_sent",
                    }
                )
                gateway.append_audit_event(audit_path, audit_event)
                preview["preparation_api"] = {
                    "contract": "wwcx.outbound-mail-preparation-api.v1",
                    "authenticated_client_id": client.client_id,
                    "delivery_status": "prepared_not_sent",
                }
                self._send_json(HTTPStatus.OK, preview)
                return

            max_bytes = config["admin"]["max_body_bytes"] + 65536
            payload = self._read_json(max_bytes)
            if parsed.path == "/outbound-mail/preview":
                preview = identity_gateway.compose_preview(config, policy, identities, payload)
                preview.pop("action_token", None)
                self._send_json(HTTPStatus.OK, preview)
                return
            if parsed.path == "/outbound-mail/send":
                confirmation = payload.pop("confirm_send", False) is True
                result = identity_gateway.send_message(
                    config,
                    policy,
                    identities,
                    payload,
                    confirmation=confirmation,
                    audit_path=audit_path,
                )
                self._send_json(HTTPStatus.ACCEPTED, result)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:
            self._handle_error(exc)
'''
    replace_once(path, old_post, new_post, "server authenticated prepare route")
    replace_once(
        path,
        "    config, policy, identities, _ = application.load()\n",
        "    config, policy, identities, _, _ = application.load()\n",
        "server main load tuple",
    )


def update_tests() -> None:
    unit_path = "tests/test_outbound_mail_gateway.py"
    replace_once(
        unit_path,
        '        self.assertFalse(self.config["admin"]["send_endpoint_enabled"])\n'
        '        self.assertEqual(self.config["provider"]["selected"], "none")',
        '        self.assertFalse(self.config["admin"]["send_endpoint_enabled"])\n'
        '        self.assertFalse(self.config["preparation_api"]["enabled"])\n'
        '        self.assertEqual(\n'
        '            self.config["preparation_api"]["authentication"],\n'
        '            "hmac_sha256",\n'
        '        )\n'
        '        self.assertEqual(self.config["provider"]["selected"], "none")',
        "gateway unit committed preparation API state",
    )
    replace_once(
        unit_path,
        '        self.assertFalse(status["device_fingerprinting"])\n',
        '        self.assertFalse(status["device_fingerprinting"])\n'
        '        self.assertFalse(status["preparation_api"]["enabled"])\n'
        '        self.assertFalse(status["preparation_api"]["runtime_secret_configured"])\n',
        "gateway unit preparation API status",
    )

    validator_path = ROOT / "tests/validate_outbound_mail_gateway.py"
    text = validator_path.read_text(encoding="utf-8")
    changes = [
        (
            'FACADE_PATH = ROOT / "server" / "identity_aware_outbound_gateway.py"\n',
            'FACADE_PATH = ROOT / "server" / "identity_aware_outbound_gateway.py"\n'
            'AUTH_PATH = ROOT / "server" / "outbound_mail_preparation_auth.py"\n',
        ),
        (
            'assert status["persist_attachment_bytes"] is False\n',
            'assert status["persist_attachment_bytes"] is False\n'
            'assert status["preparation_api"]["enabled"] is False\n'
            'assert status["preparation_api"]["authentication"] == "hmac_sha256"\n'
            'assert status["preparation_api"]["runtime_secret_configured"] is False\n',
        ),
        (
            "    FACADE_PATH,\n    IDENTITIES_PATH,\n",
            "    FACADE_PATH,\n    AUTH_PATH,\n    IDENTITIES_PATH,\n",
        ),
        (
            '    \'"/outbound-mail/send"\',\n    "DEFAULT_IDENTITIES",\n',
            '    \'"/outbound-mail/send"\',\n'
            '    \'"/outbound-mail/api/v1/status"\',\n'
            '    \'"/outbound-mail/api/v1/prepare"\',\n'
            '    "preparation_auth.verify_request",\n'
            '    "outbound_message_prepared_api",\n'
            '    "DEFAULT_IDENTITIES",\n',
        ),
        (
            '        "tests.test_identity_aware_outbound_gateway",\n',
            '        "tests.test_identity_aware_outbound_gateway",\n'
            '        "tests.test_outbound_mail_preparation_auth",\n',
        ),
        (
            "        str(FACADE_PATH),\n",
            "        str(FACADE_PATH),\n        str(AUTH_PATH),\n",
        ),
    ]
    for old, new in changes:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"validator anchor expected once, found {count}: {old!r}")
        text = text.replace(old, new, 1)
    validator_path.write_text(text, encoding="utf-8")


def main() -> int:
    update_config()
    update_gateway_core()
    update_server()
    update_tests()
    print("Preparation API patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
