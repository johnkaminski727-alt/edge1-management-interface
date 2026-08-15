"""Configuration loading and safety validation for Edge1 Comms Relay."""

from __future__ import annotations

import ipaddress
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path('/etc/wwcx/comms-relay.json')
DEFAULT_DB_PATH = Path('/var/lib/wwcx-comms/comms.sqlite3')
GROUP_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9+_-]*(?:\.[A-Za-z0-9][A-Za-z0-9+_-]*)+$')
SOURCE_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{0,63}$')
GIT_REF_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$')
HOST_RE = re.compile(r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$')


class ConfigError(ValueError):
    pass


def _is_loopback(host: str) -> bool:
    if host.lower() == 'localhost':
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
            raise ConfigError(f'{name}.port must be between 1 and 65535')
        if not self.host:
            raise ConfigError(f'{name}.host is required')
        if self.tls and (not self.cert_file or not self.key_file):
            raise ConfigError(f'{name} TLS requires cert_file and key_file')
        if not _is_loopback(self.host):
            if not allow_public_bind:
                raise ConfigError(f'{name} non-loopback bind requires network_exposure.enabled=true')
            if not self.tls:
                raise ConfigError(f'{name} non-loopback bind requires TLS')


@dataclass(frozen=True)
class SecurityConfig:
    require_auth: bool = True
    allow_anonymous_irc: bool = False
    allow_anonymous_nntp_read: bool = False
    allow_anonymous_nntp_post: bool = False
    max_line_bytes: int = 8192
    max_article_bytes: int = 1_048_576
    password_iterations: int = 600_000
    min_password_length: int = 12
    idle_timeout_seconds: int = 300
    max_connections: int = 128
    max_connections_per_ip: int = 16
    command_rate_per_second: int = 20
    command_burst: int = 40
    auth_failures_per_minute: int = 10

    def validate(self) -> None:
        if self.password_iterations < 100_000:
            raise ConfigError('security.password_iterations must be at least 100000')
        if not 8 <= self.min_password_length <= 128:
            raise ConfigError('security.min_password_length must be between 8 and 128')
        if not 512 <= self.max_line_bytes <= 65_536:
            raise ConfigError('security.max_line_bytes must be between 512 and 65536')
        if not 16_384 <= self.max_article_bytes <= 16_777_216:
            raise ConfigError('security.max_article_bytes must be between 16384 and 16777216')
        if not 30 <= self.idle_timeout_seconds <= 86_400:
            raise ConfigError('security.idle_timeout_seconds must be between 30 and 86400')
        if not 1 <= self.max_connections <= 4096:
            raise ConfigError('security.max_connections must be between 1 and 4096')
        if not 1 <= self.max_connections_per_ip <= self.max_connections:
            raise ConfigError('security.max_connections_per_ip must be between 1 and max_connections')
        if not 1 <= self.command_rate_per_second <= 1000:
            raise ConfigError('security.command_rate_per_second must be between 1 and 1000')
        if not self.command_rate_per_second <= self.command_burst <= 5000:
            raise ConfigError('security.command_burst must be at least command_rate_per_second and no more than 5000')
        if not 1 <= self.auth_failures_per_minute <= 100:
            raise ConfigError('security.auth_failures_per_minute must be between 1 and 100')
        if self.require_auth and (self.allow_anonymous_irc or self.allow_anonymous_nntp_post):
            raise ConfigError('require_auth conflicts with anonymous IRC or anonymous NNTP posting')


@dataclass(frozen=True)
class RetentionConfig:
    irc_history_enabled: bool = False
    irc_history_days: int = 30
    default_news_days: int = 3650
    audit_days: int = 365
    maintenance_interval_seconds: int = 3600

    def validate(self) -> None:
        if not 1 <= self.irc_history_days <= 3650:
            raise ConfigError('retention.irc_history_days must be between 1 and 3650')
        if not 1 <= self.default_news_days <= 36500:
            raise ConfigError('retention.default_news_days must be between 1 and 36500')
        if not 1 <= self.audit_days <= 3650:
            raise ConfigError('retention.audit_days must be between 1 and 3650')
        if not 60 <= self.maintenance_interval_seconds <= 86_400:
            raise ConfigError('retention.maintenance_interval_seconds must be between 60 and 86400')


@dataclass(frozen=True)
class IngestSourceConfig:
    source_type: str
    name: str
    enabled: bool = True
    group: str | None = None
    path: str | None = None
    ref: str = 'main'
    base_url: str | None = None
    host: str | None = None
    port: int | None = None
    tls: bool | None = None
    upstream_group: str | None = None
    credential_file: str | None = None
    create_group: bool = False
    retention_days: int | None = None
    max_article_bytes: int | None = None
    initial_items: int = 8
    scan_limit: int = 500

    def validate(self) -> None:
        if self.source_type not in {'bootstrap', 'git', 'nntp'}:
            raise ConfigError(f'ingestion source {self.name!r} has unsupported type')
        if not SOURCE_RE.fullmatch(self.name):
            raise ConfigError('ingestion source name must use lowercase letters, digits, dot, underscore, or hyphen')
        if not 1 <= self.initial_items <= 100:
            raise ConfigError(f'ingestion source {self.name}.initial_items must be between 1 and 100')
        if not 10 <= self.scan_limit <= 5000:
            raise ConfigError(f'ingestion source {self.name}.scan_limit must be between 10 and 5000')
        if self.source_type == 'bootstrap':
            if any(value is not None for value in (self.group, self.path, self.base_url, self.host, self.port, self.tls, self.upstream_group, self.credential_file, self.retention_days, self.max_article_bytes)) or self.create_group:
                raise ConfigError(f'bootstrap source {self.name} accepts only bootstrap fields')
            return
        if self.source_type == 'git':
            if any(value is not None for value in (self.host, self.port, self.tls, self.upstream_group, self.credential_file, self.retention_days, self.max_article_bytes)) or self.create_group:
                raise ConfigError(f'git source {self.name} contains NNTP-only fields')
            if not self.group or not GROUP_RE.fullmatch(self.group):
                raise ConfigError(f'git source {self.name} requires a valid newsgroup')
            if not self.path or not Path(self.path).is_absolute():
                raise ConfigError(f'git source {self.name} requires an absolute repository path')
            if not GIT_REF_RE.fullmatch(self.ref) or '..' in self.ref or self.ref.endswith('/'):
                raise ConfigError(f'git source {self.name} has an unsafe ref')
            if self.base_url is not None:
                parsed = urllib.parse.urlparse(self.base_url)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                    raise ConfigError(f'git source {self.name}.base_url must be a credential-free HTTPS URL')
            return
        if self.path is not None or self.base_url is not None or self.ref != 'main':
            raise ConfigError(f'NNTP source {self.name} contains git-only fields')
        if not self.group or not GROUP_RE.fullmatch(self.group):
            raise ConfigError(f'NNTP source {self.name} requires a valid local newsgroup')
        if not self.upstream_group or not GROUP_RE.fullmatch(self.upstream_group):
            raise ConfigError(f'NNTP source {self.name} requires a valid upstream_group')
        if not self.host or not HOST_RE.fullmatch(self.host):
            raise ConfigError(f'NNTP source {self.name}.host must be a DNS hostname')
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            pass
        else:
            raise ConfigError(f'NNTP source {self.name}.host must not be an IP literal')
        if self.host.lower() == 'localhost' or self.host.lower().endswith('.localhost'):
            raise ConfigError(f'NNTP source {self.name}.host must not be localhost')
        if self.port is None or not 1 <= self.port <= 65535:
            raise ConfigError(f'NNTP source {self.name}.port must be between 1 and 65535')
        if self.tls is not True:
            raise ConfigError(f'NNTP source {self.name} requires TLS')
        if self.credential_file is not None:
            credential_path = Path(self.credential_file)
            if not credential_path.is_absolute() or '\x00' in self.credential_file:
                raise ConfigError(f'NNTP source {self.name}.credential_file must be an absolute path')
        if self.retention_days is not None and not 1 <= self.retention_days <= 36500:
            raise ConfigError(f'NNTP source {self.name}.retention_days must be between 1 and 36500')
        if self.max_article_bytes is None or not 1024 <= self.max_article_bytes <= 1_048_576:
            raise ConfigError(f'NNTP source {self.name}.max_article_bytes must be between 1024 and 1048576')


@dataclass(frozen=True)
class IngestionConfig:
    enabled: bool = False
    startup_delay_seconds: int = 5
    interval_seconds: int = 900
    max_items_per_run: int = 25
    sources: tuple[IngestSourceConfig, ...] = ()

    def validate(self) -> None:
        if not 0 <= self.startup_delay_seconds <= 300:
            raise ConfigError('ingestion.startup_delay_seconds must be between 0 and 300')
        if not 60 <= self.interval_seconds <= 86_400:
            raise ConfigError('ingestion.interval_seconds must be between 60 and 86400')
        if not 1 <= self.max_items_per_run <= 500:
            raise ConfigError('ingestion.max_items_per_run must be between 1 and 500')
        names: set[str] = set()
        for source in self.sources:
            source.validate()
            if source.name in names:
                raise ConfigError(f'duplicate ingestion source name: {source.name}')
            names.add(source.name)
        if self.enabled and not self.sources:
            raise ConfigError('ingestion.enabled requires at least one source')


@dataclass(frozen=True)
class RelayConfig:
    server_name: str = 'edge1.ww.cx'
    network_name: str = 'WW.CX'
    database_path: str = str(DEFAULT_DB_PATH)
    allow_public_bind: bool = False
    irc: ListenerConfig = field(default_factory=lambda: ListenerConfig('127.0.0.1', 16667, True, False))
    nntp: ListenerConfig = field(default_factory=lambda: ListenerConfig('127.0.0.1', 1119, True, False))
    control: ListenerConfig = field(default_factory=lambda: ListenerConfig('127.0.0.1', 8100, True, False))
    security: SecurityConfig = field(default_factory=SecurityConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)

    def validate(self) -> None:
        if not self.server_name or ' ' in self.server_name:
            raise ConfigError('server_name must be a non-empty hostname-like token')
        if not self.network_name:
            raise ConfigError('network_name is required')
        if not self.database_path:
            raise ConfigError('database_path is required')
        self.security.validate()
        self.retention.validate()
        self.ingestion.validate()
        self.irc.validate(allow_public_bind=self.allow_public_bind, name='irc')
        self.nntp.validate(allow_public_bind=self.allow_public_bind, name='nntp')
        self.control.validate(allow_public_bind=False, name='control')


def _listener(value: dict[str, Any], default: ListenerConfig) -> ListenerConfig:
    return ListenerConfig(
        host=str(value.get('host', default.host)),
        port=int(value.get('port', default.port)),
        enabled=bool(value.get('enabled', default.enabled)),
        tls=bool(value.get('tls', default.tls)),
        cert_file=value.get('cert_file', default.cert_file),
        key_file=value.get('key_file', default.key_file),
    )


def _ingest_source(value: dict[str, Any]) -> IngestSourceConfig:
    source_type = str(value.get('type', '')).strip().lower()
    return IngestSourceConfig(
        source_type=source_type,
        name=str(value.get('name', '')).strip().lower(),
        enabled=bool(value.get('enabled', True)),
        group=str(value['group']).strip().lower() if value.get('group') is not None else None,
        path=str(value['path']) if value.get('path') is not None else None,
        ref=str(value.get('ref', 'main')).strip(),
        base_url=str(value['base_url']).rstrip('/') if value.get('base_url') is not None else None,
        host=str(value['host']).strip().lower() if value.get('host') is not None else None,
        port=int(value.get('port', 563)) if source_type == 'nntp' else (int(value['port']) if value.get('port') is not None else None),
        tls=bool(value.get('tls', True)) if source_type == 'nntp' else (bool(value['tls']) if value.get('tls') is not None else None),
        upstream_group=str(value['upstream_group']).strip().lower() if value.get('upstream_group') is not None else None,
        credential_file=str(value['credential_file']) if value.get('credential_file') is not None else None,
        create_group=bool(value.get('create_group', False)),
        retention_days=int(value['retention_days']) if value.get('retention_days') is not None else None,
        max_article_bytes=int(value.get('max_article_bytes', 262144)) if source_type == 'nntp' else (int(value['max_article_bytes']) if value.get('max_article_bytes') is not None else None),
        initial_items=int(value.get('initial_items', 8)),
        scan_limit=int(value.get('scan_limit', 500)),
    )


def config_from_dict(payload: dict[str, Any]) -> RelayConfig:
    d = RelayConfig()
    e = payload.get('network_exposure', {}) or {}
    s = payload.get('security', {}) or {}
    r = payload.get('retention', {}) or {}
    l = payload.get('listeners', {}) or {}
    i = payload.get('ingestion', {}) or {}
    source_values = i.get('sources', []) or []
    if not isinstance(source_values, list) or any(not isinstance(x, dict) for x in source_values):
        raise ConfigError('ingestion.sources must be a list of objects')
    cfg = RelayConfig(
        server_name=str(payload.get('server_name', d.server_name)),
        network_name=str(payload.get('network_name', d.network_name)),
        database_path=str(payload.get('database_path', d.database_path)),
        allow_public_bind=bool(e.get('enabled', d.allow_public_bind)),
        irc=_listener(l.get('irc', {}) or {}, d.irc),
        nntp=_listener(l.get('nntp', {}) or {}, d.nntp),
        control=_listener(l.get('control', {}) or {}, d.control),
        security=SecurityConfig(
            require_auth=bool(s.get('require_auth', d.security.require_auth)),
            allow_anonymous_irc=bool(s.get('allow_anonymous_irc', d.security.allow_anonymous_irc)),
            allow_anonymous_nntp_read=bool(s.get('allow_anonymous_nntp_read', d.security.allow_anonymous_nntp_read)),
            allow_anonymous_nntp_post=bool(s.get('allow_anonymous_nntp_post', d.security.allow_anonymous_nntp_post)),
            max_line_bytes=int(s.get('max_line_bytes', d.security.max_line_bytes)),
            max_article_bytes=int(s.get('max_article_bytes', d.security.max_article_bytes)),
            password_iterations=int(s.get('password_iterations', d.security.password_iterations)),
            min_password_length=int(s.get('min_password_length', d.security.min_password_length)),
            idle_timeout_seconds=int(s.get('idle_timeout_seconds', d.security.idle_timeout_seconds)),
            max_connections=int(s.get('max_connections', d.security.max_connections)),
            max_connections_per_ip=int(s.get('max_connections_per_ip', d.security.max_connections_per_ip)),
            command_rate_per_second=int(s.get('command_rate_per_second', d.security.command_rate_per_second)),
            command_burst=int(s.get('command_burst', d.security.command_burst)),
            auth_failures_per_minute=int(s.get('auth_failures_per_minute', d.security.auth_failures_per_minute)),
        ),
        retention=RetentionConfig(
            irc_history_enabled=bool(r.get('irc_history_enabled', d.retention.irc_history_enabled)),
            irc_history_days=int(r.get('irc_history_days', d.retention.irc_history_days)),
            default_news_days=int(r.get('default_news_days', d.retention.default_news_days)),
            audit_days=int(r.get('audit_days', d.retention.audit_days)),
            maintenance_interval_seconds=int(r.get('maintenance_interval_seconds', d.retention.maintenance_interval_seconds)),
        ),
        ingestion=IngestionConfig(
            enabled=bool(i.get('enabled', d.ingestion.enabled)),
            startup_delay_seconds=int(i.get('startup_delay_seconds', d.ingestion.startup_delay_seconds)),
            interval_seconds=int(i.get('interval_seconds', d.ingestion.interval_seconds)),
            max_items_per_run=int(i.get('max_items_per_run', d.ingestion.max_items_per_run)),
            sources=tuple(_ingest_source(x) for x in source_values),
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
    payload = json.loads(target.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ConfigError('top-level configuration must be an object')
    return config_from_dict(payload)


def sanitized_config(cfg: RelayConfig) -> dict[str, Any]:
    def listener(item: ListenerConfig) -> dict[str, Any]:
        return {
            'host': item.host,
            'port': item.port,
            'enabled': item.enabled,
            'tls': item.tls,
            'cert_file_configured': bool(item.cert_file),
            'key_file_configured': bool(item.key_file),
        }

    return {
        'server_name': cfg.server_name,
        'network_name': cfg.network_name,
        'database_path': cfg.database_path,
        'network_exposure': {'enabled': cfg.allow_public_bind},
        'listeners': {'irc': listener(cfg.irc), 'nntp': listener(cfg.nntp), 'control': listener(cfg.control)},
        'security': {
            'require_auth': cfg.security.require_auth,
            'allow_anonymous_irc': cfg.security.allow_anonymous_irc,
            'allow_anonymous_nntp_read': cfg.security.allow_anonymous_nntp_read,
            'allow_anonymous_nntp_post': cfg.security.allow_anonymous_nntp_post,
            'max_line_bytes': cfg.security.max_line_bytes,
            'max_article_bytes': cfg.security.max_article_bytes,
            'password_iterations': cfg.security.password_iterations,
            'min_password_length': cfg.security.min_password_length,
            'idle_timeout_seconds': cfg.security.idle_timeout_seconds,
            'max_connections': cfg.security.max_connections,
            'max_connections_per_ip': cfg.security.max_connections_per_ip,
            'command_rate_per_second': cfg.security.command_rate_per_second,
            'command_burst': cfg.security.command_burst,
            'auth_failures_per_minute': cfg.security.auth_failures_per_minute,
        },
        'retention': {
            'irc_history_enabled': cfg.retention.irc_history_enabled,
            'irc_history_days': cfg.retention.irc_history_days,
            'default_news_days': cfg.retention.default_news_days,
            'audit_days': cfg.retention.audit_days,
            'maintenance_interval_seconds': cfg.retention.maintenance_interval_seconds,
        },
        'ingestion': {
            'enabled': cfg.ingestion.enabled,
            'startup_delay_seconds': cfg.ingestion.startup_delay_seconds,
            'interval_seconds': cfg.ingestion.interval_seconds,
            'max_items_per_run': cfg.ingestion.max_items_per_run,
            'sources': [
                {
                    'type': source.source_type,
                    'name': source.name,
                    'enabled': source.enabled,
                    'group': source.group,
                    'path': source.path,
                    'ref': source.ref,
                    'base_url': source.base_url,
                    'host': source.host,
                    'port': source.port,
                    'tls': source.tls,
                    'upstream_group': source.upstream_group,
                    'credential_file_configured': bool(source.credential_file),
                    'create_group': source.create_group,
                    'retention_days': source.retention_days,
                    'max_article_bytes': source.max_article_bytes,
                    'initial_items': source.initial_items,
                    'scan_limit': source.scan_limit,
                }
                for source in cfg.ingestion.sources
            ],
        },
    }
