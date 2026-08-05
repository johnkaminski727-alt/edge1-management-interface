"""Strict configuration contract for the Edge1 Security authentication HTTP adapter."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Mapping

HTTP_CONTRACT = "wwcx.edge1-security-auth-http.v1"
@dataclasses.dataclass(frozen=True)
class HttpAdapterConfig:
    enabled: bool
    deployment_authorized: bool
    live_route_authorized: bool
    allowed_host: str
    business159_origin: str
    same_origin: str
    routes: Mapping[str, str]
    session_cookie_name: str
    csrf_cookie_name: str
    cookie_path: str
    maximum_body_bytes: int
    exchange_requests: int
    exchange_window_seconds: int
    session_requests: int
    session_window_seconds: int
    action_requests: int
    action_window_seconds: int
    logout_requests: int
    logout_window_seconds: int
    action_inflight_timeout_seconds: int
    action_cooldown_seconds: int
    operations_origin: str
    operations_secret_path: Path
    operations_timeout_seconds: int
    operations_action: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HttpAdapterConfig":
        expected = {
            "contract", "status", "enabled", "deployment_authorized",
            "live_route_authorized", "allowed_host", "business159_origin",
            "same_origin", "routes", "cookies", "request_limits",
            "operations_api", "boundaries",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("HTTP adapter fields do not match the contract")
        if value["contract"] != HTTP_CONTRACT or value["status"] != "staged_disabled":
            raise ValueError("HTTP adapter contract or status is invalid")
        for flag in ("enabled", "deployment_authorized", "live_route_authorized"):
            if not isinstance(value[flag], bool):
                raise ValueError(f"{flag} must be boolean")
        if value["enabled"] and not value["deployment_authorized"]:
            raise ValueError("HTTP adapter cannot be enabled without deployment authorization")
        if value["allowed_host"] != "edge1.ww.cx":
            raise ValueError("HTTP adapter host must remain exact")
        if value["business159_origin"] != "https://business159.ww.cx":
            raise ValueError("Business159 origin must remain exact")
        if value["same_origin"] != "https://edge1.ww.cx":
            raise ValueError("Edge1 origin must remain exact")
        routes = value["routes"]
        expected_routes = {
            "health": "/healthz",
            "exchange": "/edge1-ops/session/exchange",
            "session": "/edge1-ops/session",
            "logout": "/edge1-ops/session/logout",
            "validate": "/edge1-ops/api/v1/security/validate",
            "redirect_after_exchange": "/edge1-ops/security/",
        }
        if routes != expected_routes:
            raise ValueError("HTTP adapter routes do not match the contract")
        cookies = value["cookies"]
        expected_cookie_keys = {
            "session_name", "csrf_name", "path", "secure",
            "http_only_session", "same_site", "persistent",
        }
        if not isinstance(cookies, dict) or set(cookies) != expected_cookie_keys:
            raise ValueError("HTTP cookie fields do not match the contract")
        if cookies != {
            "session_name": "__Secure-wwcx_edge1_ops_session",
            "csrf_name": "__Secure-wwcx_edge1_ops_csrf",
            "path": "/edge1-ops/",
            "secure": True,
            "http_only_session": True,
            "same_site": "Strict",
            "persistent": False,
        }:
            raise ValueError("HTTP cookie policy does not match the contract")
        limits = value["request_limits"]
        limit_keys = {
            "maximum_body_bytes", "exchange_requests", "exchange_window_seconds",
            "session_requests", "session_window_seconds", "action_requests",
            "action_window_seconds", "logout_requests", "logout_window_seconds",
            "action_inflight_timeout_seconds", "action_cooldown_seconds",
        }
        if not isinstance(limits, dict) or set(limits) != limit_keys:
            raise ValueError("HTTP request limits do not match the contract")
        for key in limit_keys:
            if isinstance(limits[key], bool) or not isinstance(limits[key], int) or limits[key] < 1:
                raise ValueError(f"request limit {key} is invalid")
        if not 1024 <= limits["maximum_body_bytes"] <= 65536:
            raise ValueError("maximum body size is invalid")
        operations = value["operations_api"]
        if not isinstance(operations, dict) or set(operations) != {
            "origin", "secret_path", "timeout_seconds", "allowed_action"
        }:
            raise ValueError("Operations API fields do not match the contract")
        if operations["origin"] != "http://127.0.0.1:8097":
            raise ValueError("Operations API origin must remain loopback")
        if operations["allowed_action"] != "security.validate_config":
            raise ValueError("Only configuration validation is allowed")
        if not isinstance(operations["secret_path"], str) or not operations["secret_path"].startswith("/"):
            raise ValueError("Operations API secret path must be absolute")
        if not isinstance(operations["timeout_seconds"], int) or not 1 <= operations["timeout_seconds"] <= 60:
            raise ValueError("Operations API timeout is invalid")
        boundaries = value["boundaries"]
        if boundaries != {
            "loopback_only": True,
            "trusted_proxy_required": True,
            "csrf_required_for_authenticated_post": True,
            "raw_assertion_storage": False,
            "raw_session_storage": False,
            "raw_operations_output_to_browser": False,
            "mutation_actions_enabled": False,
        }:
            raise ValueError("HTTP adapter boundaries do not match the contract")
        return cls(
            enabled=value["enabled"],
            deployment_authorized=value["deployment_authorized"],
            live_route_authorized=value["live_route_authorized"],
            allowed_host=value["allowed_host"],
            business159_origin=value["business159_origin"],
            same_origin=value["same_origin"],
            routes=routes,
            session_cookie_name=cookies["session_name"],
            csrf_cookie_name=cookies["csrf_name"],
            cookie_path=cookies["path"],
            maximum_body_bytes=limits["maximum_body_bytes"],
            exchange_requests=limits["exchange_requests"],
            exchange_window_seconds=limits["exchange_window_seconds"],
            session_requests=limits["session_requests"],
            session_window_seconds=limits["session_window_seconds"],
            action_requests=limits["action_requests"],
            action_window_seconds=limits["action_window_seconds"],
            logout_requests=limits["logout_requests"],
            logout_window_seconds=limits["logout_window_seconds"],
            action_inflight_timeout_seconds=limits["action_inflight_timeout_seconds"],
            action_cooldown_seconds=limits["action_cooldown_seconds"],
            operations_origin=operations["origin"],
            operations_secret_path=Path(operations["secret_path"]),
            operations_timeout_seconds=operations["timeout_seconds"],
            operations_action=operations["allowed_action"],
        )

    @classmethod
    def from_path(cls, path: Path) -> "HttpAdapterConfig":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("HTTP adapter configuration must be an object")
        return cls.from_mapping(value)
