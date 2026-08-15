"""Configuration loading and safety validation for Edge1 Comms Relay."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("/etc/wwcx/comms-relay.json")
DEFAULT_DB_PATH = Path("/var/lib/wwcx-comms/comms.sqlite3")


class ConfigError(ValueError):
    """Raised when a communications configuration is unsafe or invalid."""


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class ListenerConfig:
    host: str
    port: int
    enabled: bool = True
    tls: bool = False
    cert_file: str | None = None
    key_file: str | None = None

    def validate(self, *, allow_public_bind: bool, name: str) -> None:
        if not 1 <= self.port <= 65535:
            raise ConfigError(f"{name}.port must be between 1 and 65535")
        if not self.host:
            raise ConfigError(f"{name}.host is required")
        if self.tls and (not self.cert_file or not self.key_file):
            raise ConfigError(f"{name} TLS requires cert_file and key_file")
        if not _is_loopback(self.host):
            if not allow_public_bind:
                raise ConfigError(f"{name} non-loopback bind requires network_exposure.enabled=true")
            if not self.tls:
                raise ConfigError(f"{name} non-loopback bind requires TLS")


@dataclass(frozen=True)
class SecurityConfig:
    require_auth: bool = True
    allow_anonymous_irc: bool = False
    allow_anonymous_nntp_read: bool = False
    allow_anonymous_nntp_post: bool = False
    max_line_bytes: int = 8192
    max_article_bytes: int = 1_048_576
    password_iterations: int = 240_000

    def validate(self) -> None:
        if self.password_iterations < 100_000:
            raise ConfigError("security.password_iterations must be at least 100000")
        if not 512 <= self.max_line_bytes <= 65_536:
            raise ConfigError("security.max_line_bytes must be between 512 and 65536")
        if not 16_384 <= self.max_article_bytes <= 16_777_216:
            raise ConfigError("security.max_article_bytes must be between 16384 and 16777216")
        if self.require_auth and (self.allow_anonymous_irc or self.allow_anonymous_nntp_post):
            raise ConfigError("require_auth conflicts with anonymous IRC or anonymous NNTP posting")


@dataclass(frozen=True)
class RetentionConfig:
    irc_history_enabled: bool = False
    irc_history_days: int = 30
    default_news_days: int = 3650

    def validate(self) -> None:
        if self.irc_history_days < 1:
            raise ConfigError("retention.irc_history_days must be positive")
        if self.default_news_days < 1:
            raise ConfigError("retention.default_news_days must be positive")


@dataclass(frozen=True)
class RelayConfig:
    server_name: str = "edge1.ww.cx"
    network_name: str = "WW.CX"
    database_path: str = str(DEFAULT_DB_PATH)
    allow_public_bind: bool = False
    irc: ListenerConfig = field(default_factory=lambda: ListenerConfig("127.0.0.1", 16667, True, False))
    nntp: ListenerConfig = field(default_factory=lambda: ListenerConfig("127.0.0.1", 1119, True, False))
    control: ListenerConfig = field(default_factory=lambda: ListenerConfig("127.0.0.1", 8099, True, False))
    security: SecurityConfig = field(default_factory=SecurityConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)

    def validate(self) -> None:
        if not self.server_name or " " in self.server_name:
            raise ConfigError("server_name must be a non-empty hostname-like token")
        if not self.network_name:
            raise ConfigError("network_name is required")
        if not self.database_path:
            raise ConfigError("database_path is required")
        self.security.validate()
        self.retention.validate()
        self.irc.validate(allow_public_bind=self.allow_public_bind, name="irc")
        self.nntp.validate(allow_public_bind=self.allow_public_bind, name="nntp")
        self.control.validate(allow_public_bind=False, name="control")


def _listener(value: dict[str, Any], default: ListenerConfig) -> ListenerConfig:
    return ListenerConfig(
        host=str(value.get("host", default.host)),
        port=int(value.get("port", default.port)),
        enabled=bool(value.get("enabled", default.enabled)),
        tls=bool(value.get("tls", default.tls)),
        cert_file=value.get("cert_file", default.cert_file),
        key_file=value.get("key_file", default.key_file),
    )


def config_from_dict(payload: dict[str, Any]) -> RelayConfig:
    defaults = RelayConfig()
    exposure = payload.get("network_exposure", {}) or {}
    security_raw = payload.get("security", {}) or {}
    retention_raw = payload.get("retention", {}) or {}
    listeners = payload.get("listeners", {}) or {}
    cfg = RelayConfig(
        server_name=str(payload.get("server_name", defaults.server_name)),
        network_name=str(payload.get("network_name", defaults.network_name)),
        database_path=str(payload.get("database_path", defaults.database_path)),
        allow_public_bind=bool(exposure.get("enabled", defaults.allow_public_bind)),
        irc=_listener(listeners.get("irc", {}) or {}, defaults.irc),
        nntp=_listener(listeners.get("nntp", {}) or {}, defaults.nntp),
        control=_listener(listeners.get("control", {}) or {}, defaults.control),
        security=SecurityConfig(
            require_auth=bool(security_raw.get("require_auth", defaults.security.require_auth)),
            allow_anonymous_irc=bool(security_raw.get("allow_anonymous_irc", defaults.security.allow_anonymous_irc)),
            allow_anonymous_nntp_read=bool(security_raw.get("allow_anonymous_nntp_read", defaults.security.allow_anonymous_nntp_read)),
            allow_anonymous_nntp_post=bool(security_raw.get("allow_anonymous_nntp_post", defaults.security.allow_anonymous_nntp_post)),
            max_line_bytes=int(security_raw.get("max_line_bytes", defaults.security.max_line_bytes)),
            max_article_bytes=int(security_raw.get("max_article_bytes", defaults.security.max_article_bytes)),
            password_iterations=int(security_raw.get("password_iterations", defaults.security.password_iterations)),
        ),
        retention=RetentionConfig(
            irc_history_enabled=bool(retention_raw.get("irc_history_enabled", defaults.retention.irc_history_enabled)),
            irc_history_days=int(retention_raw.get("irc_history_days", defaults.retention.irc_history_days)),
            default_news_days=int(retention_raw.get("default_news_days", defaults.retention.default_news_days)),
        ),
    )
    cfg.validate()
    return cfg


def load_config(path: str | Path | None = None) -> RelayConfig:
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    if not target.is_file():
        cfg = RelayConfig()
        cfg.validate()
        return cfg
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigError("top-level configuration must be an object")
    return config_from_dict(payload)


def sanitized_config(cfg: RelayConfig) -> dict[str, Any]:
    def listener(item: ListenerConfig) -> dict[str, Any]:
        return {
            "host": item.host,
            "port": item.port,
            "enabled": item.enabled,
            "tls": item.tls,
            "cert_file_configured": bool(item.cert_file),
            "key_file_configured": bool(item.key_file),
        }

    return {
        "server_name": cfg.server_name,
        "network_name": cfg.network_name,
        "database_path": cfg.database_path,
        "network_exposure": {"enabled": cfg.allow_public_bind},
        "listeners": {"irc": listener(cfg.irc), "nntp": listener(cfg.nntp), "control": listener(cfg.control)},
        "security": {
            "require_auth": cfg.security.require_auth,
            "allow_anonymous_irc": cfg.security.allow_anonymous_irc,
            "allow_anonymous_nntp_read": cfg.security.allow_anonymous_nntp_read,
            "allow_anonymous_nntp_post": cfg.security.allow_anonymous_nntp_post,
            "max_line_bytes": cfg.security.max_line_bytes,
            "max_article_bytes": cfg.security.max_article_bytes,
            "password_iterations": cfg.security.password_iterations,
        },
        "retention": {
            "irc_history_enabled": cfg.retention.irc_history_enabled,
            "irc_history_days": cfg.retention.irc_history_days,
            "default_news_days": cfg.retention.default_news_days,
        },
    }
