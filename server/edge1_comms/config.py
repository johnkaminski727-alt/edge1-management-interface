"""Configuration loading and safety validation for Edge1 Comms Relay."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH=Path('/etc/wwcx/comms-relay.json')
DEFAULT_DB_PATH=Path('/var/lib/wwcx-comms/comms.sqlite3')
class ConfigError(ValueError): pass

def _is_loopback(host:str)->bool:
    if host.lower()=='localhost': return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False
@dataclass(frozen=True)
class ListenerConfig:
    host:str; port:int; enabled:bool=True; tls:bool=False; cert_file:str|None=None; key_file:str|None=None
    def validate(self,*,allow_public_bind:bool,name:str)->None:
        if not 1<=self.port<=65535: raise ConfigError(f'{name}.port must be between 1 and 65535')
        if not self.host: raise ConfigError(f'{name}.host is required')
        if self.tls and (not self.cert_file or not self.key_file): raise ConfigError(f'{name} TLS requires cert_file and key_file')
        if not _is_loopback(self.host):
            if not allow_public_bind: raise ConfigError(f'{name} non-loopback bind requires network_exposure.enabled=true')
            if not self.tls: raise ConfigError(f'{name} non-loopback bind requires TLS')
@dataclass(frozen=True)
class SecurityConfig:
    require_auth:bool=True; allow_anonymous_irc:bool=False; allow_anonymous_nntp_read:bool=False; allow_anonymous_nntp_post:bool=False
    max_line_bytes:int=8192; max_article_bytes:int=1_048_576; password_iterations:int=600_000; min_password_length:int=12
    idle_timeout_seconds:int=300; max_connections:int=128; max_connections_per_ip:int=16; command_rate_per_second:int=20; command_burst:int=40; auth_failures_per_minute:int=10
    def validate(self)->None:
        if self.password_iterations<100_000: raise ConfigError('security.password_iterations must be at least 100000')
        if not 8<=self.min_password_length<=128: raise ConfigError('security.min_password_length must be between 8 and 128')
        if not 512<=self.max_line_bytes<=65_536: raise ConfigError('security.max_line_bytes must be between 512 and 65536')
        if not 16_384<=self.max_article_bytes<=16_777_216: raise ConfigError('security.max_article_bytes must be between 16384 and 16777216')
        if not 30<=self.idle_timeout_seconds<=86_400: raise ConfigError('security.idle_timeout_seconds must be between 30 and 86400')
        if not 1<=self.max_connections<=4096: raise ConfigError('security.max_connections must be between 1 and 4096')
        if not 1<=self.max_connections_per_ip<=self.max_connections: raise ConfigError('security.max_connections_per_ip must be between 1 and max_connections')
        if not 1<=self.command_rate_per_second<=1000: raise ConfigError('security.command_rate_per_second must be between 1 and 1000')
        if not self.command_rate_per_second<=self.command_burst<=5000: raise ConfigError('security.command_burst must be at least command_rate_per_second and no more than 5000')
        if not 1<=self.auth_failures_per_minute<=100: raise ConfigError('security.auth_failures_per_minute must be between 1 and 100')
        if self.require_auth and (self.allow_anonymous_irc or self.allow_anonymous_nntp_post): raise ConfigError('require_auth conflicts with anonymous IRC or anonymous NNTP posting')
@dataclass(frozen=True)
class RetentionConfig:
    irc_history_enabled:bool=False; irc_history_days:int=30; default_news_days:int=3650; audit_days:int=365; maintenance_interval_seconds:int=3600
    def validate(self)->None:
        if not 1<=self.irc_history_days<=3650: raise ConfigError('retention.irc_history_days must be between 1 and 3650')
        if not 1<=self.default_news_days<=36500: raise ConfigError('retention.default_news_days must be between 1 and 36500')
        if not 1<=self.audit_days<=3650: raise ConfigError('retention.audit_days must be between 1 and 3650')
        if not 60<=self.maintenance_interval_seconds<=86_400: raise ConfigError('retention.maintenance_interval_seconds must be between 60 and 86400')
@dataclass(frozen=True)
class RelayConfig:
    server_name:str='edge1.ww.cx'; network_name:str='WW.CX'; database_path:str=str(DEFAULT_DB_PATH); allow_public_bind:bool=False
    irc:ListenerConfig=field(default_factory=lambda:ListenerConfig('127.0.0.1',16667,True,False)); nntp:ListenerConfig=field(default_factory=lambda:ListenerConfig('127.0.0.1',1119,True,False)); control:ListenerConfig=field(default_factory=lambda:ListenerConfig('127.0.0.1',8099,True,False)); security:SecurityConfig=field(default_factory=SecurityConfig); retention:RetentionConfig=field(default_factory=RetentionConfig)
    def validate(self)->None:
        if not self.server_name or ' ' in self.server_name: raise ConfigError('server_name must be a non-empty hostname-like token')
        if not self.network_name: raise ConfigError('network_name is required')
        if not self.database_path: raise ConfigError('database_path is required')
        self.security.validate(); self.retention.validate(); self.irc.validate(allow_public_bind=self.allow_public_bind,name='irc'); self.nntp.validate(allow_public_bind=self.allow_public_bind,name='nntp'); self.control.validate(allow_public_bind=False,name='control')
def _listener(value:dict[str,Any],default:ListenerConfig)->ListenerConfig:
    return ListenerConfig(host=str(value.get('host',default.host)),port=int(value.get('port',default.port)),enabled=bool(value.get('enabled',default.enabled)),tls=bool(value.get('tls',default.tls)),cert_file=value.get('cert_file',default.cert_file),key_file=value.get('key_file',default.key_file))
def config_from_dict(payload:dict[str,Any])->RelayConfig:
    d=RelayConfig(); e=payload.get('network_exposure',{}) or {}; s=payload.get('security',{}) or {}; r=payload.get('retention',{}) or {}; l=payload.get('listeners',{}) or {}
    cfg=RelayConfig(server_name=str(payload.get('server_name',d.server_name)),network_name=str(payload.get('network_name',d.network_name)),database_path=str(payload.get('database_path',d.database_path)),allow_public_bind=bool(e.get('enabled',d.allow_public_bind)),irc=_listener(l.get('irc',{}) or {},d.irc),nntp=_listener(l.get('nntp',{}) or {},d.nntp),control=_listener(l.get('control',{}) or {},d.control),security=SecurityConfig(require_auth=bool(s.get('require_auth',d.security.require_auth)),allow_anonymous_irc=bool(s.get('allow_anonymous_irc',d.security.allow_anonymous_irc)),allow_anonymous_nntp_read=bool(s.get('allow_anonymous_nntp_read',d.security.allow_anonymous_nntp_read)),allow_anonymous_nntp_post=bool(s.get('allow_anonymous_nntp_post',d.security.allow_anonymous_nntp_post)),max_line_bytes=int(s.get('max_line_bytes',d.security.max_line_bytes)),max_article_bytes=int(s.get('max_article_bytes',d.security.max_article_bytes)),password_iterations=int(s.get('password_iterations',d.security.password_iterations)),min_password_length=int(s.get('min_password_length',d.security.min_password_length)),idle_timeout_seconds=int(s.get('idle_timeout_seconds',d.security.idle_timeout_seconds)),max_connections=int(s.get('max_connections',d.security.max_connections)),max_connections_per_ip=int(s.get('max_connections_per_ip',d.security.max_connections_per_ip)),command_rate_per_second=int(s.get('command_rate_per_second',d.security.command_rate_per_second)),command_burst=int(s.get('command_burst',d.security.command_burst)),auth_failures_per_minute=int(s.get('auth_failures_per_minute',d.security.auth_failures_per_minute))),retention=RetentionConfig(irc_history_enabled=bool(r.get('irc_history_enabled',d.retention.irc_history_enabled)),irc_history_days=int(r.get('irc_history_days',d.retention.irc_history_days)),default_news_days=int(r.get('default_news_days',d.retention.default_news_days)),audit_days=int(r.get('audit_days',d.retention.audit_days)),maintenance_interval_seconds=int(r.get('maintenance_interval_seconds',d.retention.maintenance_interval_seconds))))
    cfg.validate(); return cfg
def load_config(path:str|Path|None=None)->RelayConfig:
    target=Path(path) if path else DEFAULT_CONFIG_PATH
    if not target.is_file(): cfg=RelayConfig(); cfg.validate(); return cfg
    payload=json.loads(target.read_text(encoding='utf-8'))
    if not isinstance(payload,dict): raise ConfigError('top-level configuration must be an object')
    return config_from_dict(payload)
def sanitized_config(cfg:RelayConfig)->dict[str,Any]:
    def listener(i:ListenerConfig)->dict[str,Any]: return {'host':i.host,'port':i.port,'enabled':i.enabled,'tls':i.tls,'cert_file_configured':bool(i.cert_file),'key_file_configured':bool(i.key_file)}
    return {'server_name':cfg.server_name,'network_name':cfg.network_name,'database_path':cfg.database_path,'network_exposure':{'enabled':cfg.allow_public_bind},'listeners':{'irc':listener(cfg.irc),'nntp':listener(cfg.nntp),'control':listener(cfg.control)},'security':{'require_auth':cfg.security.require_auth,'allow_anonymous_irc':cfg.security.allow_anonymous_irc,'allow_anonymous_nntp_read':cfg.security.allow_anonymous_nntp_read,'allow_anonymous_nntp_post':cfg.security.allow_anonymous_nntp_post,'max_line_bytes':cfg.security.max_line_bytes,'max_article_bytes':cfg.security.max_article_bytes,'password_iterations':cfg.security.password_iterations,'min_password_length':cfg.security.min_password_length,'idle_timeout_seconds':cfg.security.idle_timeout_seconds,'max_connections':cfg.security.max_connections,'max_connections_per_ip':cfg.security.max_connections_per_ip,'command_rate_per_second':cfg.security.command_rate_per_second,'command_burst':cfg.security.command_burst,'auth_failures_per_minute':cfg.security.auth_failures_per_minute},'retention':{'irc_history_enabled':cfg.retention.irc_history_enabled,'irc_history_days':cfg.retention.irc_history_days,'default_news_days':cfg.retention.default_news_days,'audit_days':cfg.retention.audit_days,'maintenance_interval_seconds':cfg.retention.maintenance_interval_seconds}}
