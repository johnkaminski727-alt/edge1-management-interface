#!/usr/bin/env python3
"""Run an explicitly authorized SMTP STARTTLS/authentication-only canary.

The canary validates an expiring authorization file, loads SMTP settings from
the environment names already defined by the gateway profile, establishes
verified STARTTLS, authenticates, executes NOOP and RSET, then quits. It never
issues envelope, recipient, content, or submission commands and never sends a
message. Credentials are never printed, hashed into evidence beyond the
username identity hash, or accepted as command-line values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import smtplib
import ssl
import stat
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config/messaging/outbound-mail-gateway.json"
AUTH_CONTRACT = "wwcx.smtp-auth-canary-authorization.v1"
RESULT_CONTRACT = "wwcx.smtp-auth-canary-result.v1"
MAX_AUTHORIZATION_SECONDS = 24 * 60 * 60


class SmtpCanaryError(RuntimeError):
    """Raised for a safe, bounded canary failure."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmtpCanaryError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise SmtpCanaryError(f"{label} must be a JSON object")
    return value


def _private_regular_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise SmtpCanaryError(f"{label} is absent or unsafe")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SmtpCanaryError(f"{label} permissions are too broad")


def load_profile(config_path: pathlib.Path) -> dict[str, Any]:
    config = _load_json(config_path, "gateway configuration")
    profile = config.get("provider", {}).get("profiles", {}).get("smtp_submission")
    if not isinstance(profile, dict) or profile.get("type") != "smtp":
        raise SmtpCanaryError("SMTP submission profile is absent")
    required = {
        "type",
        "enabled",
        "host_env",
        "port_env",
        "username_env",
        "password_env",
        "starttls",
        "timeout_seconds",
    }
    if set(profile) != required:
        raise SmtpCanaryError("SMTP submission profile keys are invalid")
    if profile["starttls"] is not True:
        raise SmtpCanaryError("SMTP authentication canary requires STARTTLS")
    if not isinstance(profile["timeout_seconds"], int) or not 1 <= profile["timeout_seconds"] <= 120:
        raise SmtpCanaryError("SMTP timeout is invalid")
    for key in ("host_env", "port_env", "username_env", "password_env"):
        value = profile[key]
        if not isinstance(value, str) or not value.startswith("WWCX_MAIL_"):
            raise SmtpCanaryError(f"SMTP profile {key} is invalid")
    return profile


def load_runtime_settings(
    profile: dict[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = os.environ if environment is None else environment
    host = str(source.get(profile["host_env"], "")).strip().casefold()
    port_text = str(source.get(profile["port_env"], "")).strip()
    username = str(source.get(profile["username_env"], "")).strip()
    password = str(source.get(profile["password_env"], ""))
    if not host or any(character.isspace() for character in host) or "/" in host:
        raise SmtpCanaryError("SMTP host is unavailable or invalid")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise SmtpCanaryError("SMTP port is unavailable or invalid") from exc
    if not 1 <= port <= 65535:
        raise SmtpCanaryError("SMTP port is outside the allowed range")
    if not username or len(username) > 320:
        raise SmtpCanaryError("SMTP username is unavailable or invalid")
    if not password or len(password) > 4096:
        raise SmtpCanaryError("SMTP password is unavailable or invalid")
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "timeout_seconds": profile["timeout_seconds"],
    }


def validate_authorization(
    authorization: dict[str, Any],
    settings: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    expected = {
        "contract",
        "authentication_canary_authorized",
        "provider_profile",
        "expected_host_sha256",
        "expected_port",
        "expected_username_sha256",
        "expires_at",
        "mail_from_authorized",
        "recipient_authorized",
        "message_authorized",
    }
    if set(authorization) != expected:
        raise SmtpCanaryError("SMTP canary authorization keys are invalid")
    if authorization["contract"] != AUTH_CONTRACT:
        raise SmtpCanaryError("SMTP canary authorization contract is unsupported")
    if authorization["authentication_canary_authorized"] is not True:
        raise SmtpCanaryError("SMTP authentication canary is not authorized")
    if authorization["provider_profile"] != "smtp_submission":
        raise SmtpCanaryError("SMTP canary provider profile is invalid")
    if any(
        authorization[key] is not False
        for key in ("mail_from_authorized", "recipient_authorized", "message_authorized")
    ):
        raise SmtpCanaryError("SMTP canary authorization permits message activity")
    if authorization["expected_host_sha256"] != _sha256(settings["host"]):
        raise SmtpCanaryError("SMTP host does not match authorization")
    if authorization["expected_port"] != settings["port"]:
        raise SmtpCanaryError("SMTP port does not match authorization")
    if authorization["expected_username_sha256"] != _sha256(settings["username"]):
        raise SmtpCanaryError("SMTP username does not match authorization")
    try:
        expires = datetime.fromisoformat(str(authorization["expires_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SmtpCanaryError("SMTP canary authorization expiry is invalid") from exc
    if expires.tzinfo is None:
        raise SmtpCanaryError("SMTP canary authorization expiry lacks a timezone")
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    remaining = (expires.astimezone(timezone.utc) - current).total_seconds()
    if remaining <= 0:
        raise SmtpCanaryError("SMTP canary authorization has expired")
    if remaining > MAX_AUTHORIZATION_SECONDS:
        raise SmtpCanaryError("SMTP canary authorization window exceeds 24 hours")
    return {
        "expires_at": expires.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "remaining_seconds": int(remaining),
    }


def _smtp_code(response: Any, label: str) -> int:
    if not isinstance(response, tuple) or len(response) < 1:
        raise SmtpCanaryError(f"SMTP {label} returned an invalid response")
    code = int(response[0])
    if not 200 <= code < 300:
        raise SmtpCanaryError(f"SMTP {label} was not accepted")
    return code


def run_canary(
    settings: dict[str, Any],
    authorization: dict[str, Any],
    *,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
    ssl_context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
    now: datetime | None = None,
) -> dict[str, Any]:
    authorization_status = validate_authorization(authorization, settings, now=now)
    client: Any | None = None
    try:
        client = smtp_factory(
            host=settings["host"],
            port=settings["port"],
            timeout=settings["timeout_seconds"],
        )
        _smtp_code(client.ehlo(), "initial EHLO")
        if not client.has_extn("starttls"):
            raise SmtpCanaryError("SMTP server does not advertise STARTTLS")
        context = ssl_context_factory()
        _smtp_code(client.starttls(context=context), "STARTTLS")
        _smtp_code(client.ehlo(), "post-TLS EHLO")
        if not client.has_extn("auth"):
            raise SmtpCanaryError("SMTP server does not advertise AUTH after STARTTLS")
        _smtp_code(client.login(settings["username"], settings["password"]), "authentication")
        noop_code = _smtp_code(client.noop(), "NOOP")
        rset_code = _smtp_code(client.rset(), "RSET")
        peer_certificate_sha256 = None
        tls_version = None
        cipher_name = None
        sock = getattr(client, "sock", None)
        if sock is not None:
            certificate = sock.getpeercert(binary_form=True)
            if certificate:
                peer_certificate_sha256 = hashlib.sha256(certificate).hexdigest()
            if hasattr(sock, "version"):
                tls_version = sock.version()
            if hasattr(sock, "cipher"):
                cipher = sock.cipher()
                if isinstance(cipher, tuple) and cipher:
                    cipher_name = str(cipher[0])
        quit_code = _smtp_code(client.quit(), "QUIT")
        client = None
    except SmtpCanaryError:
        raise
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpCanaryError("SMTP authentication was rejected") from exc
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise SmtpCanaryError("SMTP authentication canary transport failed") from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    return {
        "contract": RESULT_CONTRACT,
        "checked_at": (datetime.now(timezone.utc) if now is None else now).astimezone(timezone.utc).isoformat(timespec="seconds"),
        "provider_profile": "smtp_submission",
        "host_sha256": _sha256(settings["host"]),
        "port": settings["port"],
        "username_sha256": _sha256(settings["username"]),
        "authorization_expires_at": authorization_status["expires_at"],
        "starttls_supported": True,
        "tls_active": True,
        "tls_version": tls_version,
        "cipher_name": cipher_name,
        "peer_certificate_sha256": peer_certificate_sha256,
        "auth_supported": True,
        "authenticated": True,
        "noop_code": noop_code,
        "rset_code": rset_code,
        "quit_code": quit_code,
        "envelope_command_issued": False,
        "recipient_command_issued": False,
        "content_command_issued": False,
        "message_submission_attempted": False,
        "message_sent": False,
        "credentials_output": False,
    }


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    repo = ROOT.resolve()
    return resolved == repo or repo in resolved.parents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _inside_repo(args.authorization):
        print("refusing SMTP authorization inside the Git working tree", file=sys.stderr)
        return 2
    if args.output is not None and _inside_repo(args.output):
        print("refusing SMTP canary output inside the Git working tree", file=sys.stderr)
        return 2
    try:
        _private_regular_file(args.authorization, "SMTP canary authorization")
        profile = load_profile(args.gateway_config)
        settings = load_runtime_settings(profile)
        result = run_canary(settings, _load_json(args.authorization, "SMTP canary authorization"))
    except SmtpCanaryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        result,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        os.chmod(args.output, 0o600)
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
