#!/usr/bin/env python3
"""Business159 assertion exchange and Edge1-owned session gateway core.

This transport-neutral module opens no listener, reads no Business159 database
or cookie, calls no Operations API, and activates no route. A later server-side
HTTP adapter may use it behind a denied-by-default staging boundary.
"""
from __future__ import annotations

import secrets
import time
from typing import Any, Callable, Mapping, Optional

from .edge1_security_assertion import validate_assertion
from .edge1_security_auth_core import (
    ACTION_SCOPES,
    ALLOWED_SCOPES,
    MUTATION_SCOPES,
    AssertionIdentity,
    AuditUnavailableError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    GatewayConfig,
    GatewayError,
    SessionContext,
    hash_secret,
    require_event_id,
    safe_reason,
    valid_event_id,
)
from .edge1_security_auth_store import JsonlAuditSink, SQLiteGatewayStore

AuditCallable = Callable[[Mapping[str, Any]], str]


class Edge1SecurityAuthGateway:
    def __init__(
        self,
        config: GatewayConfig,
        *,
        store: Optional[SQLiteGatewayStore] = None,
        audit: Optional[AuditCallable] = None,
        now: Callable[[], float] = time.time,
    ):
        self.config = config
        self.store = store or SQLiteGatewayStore(config.state_db_path)
        self.audit = audit or JsonlAuditSink(config.audit_path)
        self.now = now

    def exchange_assertion(self, assertion: str, request_id: str) -> tuple[str, SessionContext]:
        self._require_enabled()
        request_id = require_event_id(request_id, "request_id")
        now = int(self.now())
        try:
            identity = validate_assertion(self.config, assertion, now)
            if not self.store.consume_assertion(identity.jti_hash, identity.expires_at, now):
                raise AuthenticationError("assertion_replayed")
            session_token = secrets.token_urlsafe(self.config.session_token_bytes)
            session_hash = hash_secret(session_token)
            session_expires = min(
                identity.expires_at + self.config.session_absolute_timeout_seconds,
                now + self.config.session_absolute_timeout_seconds,
            )
            event_id = self._audit(
                {
                    "event_type": "login_succeeded",
                    "request_id": request_id,
                    "actor_subject": identity.subject,
                    "session_identifier_hash": session_hash,
                    "scopes": sorted(identity.scopes),
                    "authorization_decision": "allow",
                    "reason": "business159_assertion_accepted",
                }
            )
            self.store.create_session(
                session_hash=session_hash,
                identity=identity,
                issued_at=now,
                expires_at=session_expires,
                authentication_event_id=event_id,
            )
            return session_token, SessionContext(
                subject=identity.subject,
                display_name=identity.display_name,
                source_role=identity.source_role,
                scopes=identity.scopes,
                issued_at=now,
                expires_at=session_expires,
                last_seen_at=now,
                authentication_event_id=event_id,
                session_identifier_hash=session_hash,
            )
        except GatewayError as exc:
            if not isinstance(exc, AuditUnavailableError):
                try:
                    self._audit_denial("login_failed", request_id, safe_reason(exc))
                except AuditUnavailableError:
                    pass
            raise AuthenticationError("identity assertion was denied") from exc
        except Exception as exc:
            try:
                self._audit_denial("login_failed", request_id, "internal_validation_failure")
            except AuditUnavailableError:
                pass
            raise AuthenticationError("identity assertion was denied") from exc

    def authenticate_session(self, session_token: str, request_id: str) -> SessionContext:
        self._require_enabled()
        request_id = require_event_id(request_id, "request_id")
        if not isinstance(session_token, str) or len(session_token) < 43 or len(session_token) > 256:
            self._audit_denial("authorization_denied", request_id, "malformed_session")
            raise AuthenticationError("session was denied")
        session_hash = hash_secret(session_token)
        context, reason = self.store.resolve_session(
            session_hash, int(self.now()), self.config.session_idle_timeout_seconds
        )
        if context is None:
            event_type = "session_expired" if "expired" in reason else "authorization_denied"
            self._audit_denial(event_type, request_id, reason, session_hash=session_hash)
            raise AuthenticationError("session was denied")
        return context

    def authorize_action(self, session_token: str, action_id: str, request_id: str) -> SessionContext:
        request_id = require_event_id(request_id, "request_id")
        if action_id in {"security.rules.reload", "security.logs.rotate", "security.restart"}:
            self._audit_denial("authorization_denied", request_id, "mutation_scope_locked")
            raise AuthorizationError("action is not enabled")
        required_scope = ACTION_SCOPES.get(action_id)
        if required_scope is None:
            self._audit_denial("authorization_denied", request_id, "unknown_action")
            raise AuthorizationError("action is not allowlisted")
        context = self.authenticate_session(session_token, request_id)
        if required_scope not in context.scopes:
            self._audit_denial(
                "authorization_denied", request_id, "scope_missing",
                actor_subject=context.subject,
                session_hash=context.session_identifier_hash,
                required_scope=required_scope,
                authentication_event_id=context.authentication_event_id,
            )
            raise AuthorizationError("scope is not authorized")
        self._audit(
            {
                "event_type": "authorization_granted",
                "request_id": request_id,
                "actor_subject": context.subject,
                "session_identifier_hash": context.session_identifier_hash,
                "authentication_event_id": context.authentication_event_id,
                "action_id": action_id,
                "required_scope": required_scope,
                "authorization_decision": "allow",
                "reason": "exact_scope_present",
            }
        )
        return context

    def correlate_operations_event(
        self,
        session_token: str,
        *,
        action_id: str,
        operations_event_id: str,
        request_id: str,
    ) -> str:
        operations_event_id = require_event_id(operations_event_id, "operations_event_id")
        context = self.authorize_action(session_token, action_id, request_id)
        return self._audit(
            {
                "event_type": "operations_event_correlated",
                "request_id": request_id,
                "actor_subject": context.subject,
                "session_identifier_hash": context.session_identifier_hash,
                "authentication_event_id": context.authentication_event_id,
                "operations_event_id": operations_event_id,
                "action_id": action_id,
                "authorization_decision": "allow",
                "reason": "operations_api_event_preserved",
            }
        )

    def logout(self, session_token: str, request_id: str) -> None:
        request_id = require_event_id(request_id, "request_id")
        if not isinstance(session_token, str):
            raise AuthenticationError("session was denied")
        session_hash = hash_secret(session_token)
        revoked = self.store.revoke_session(session_hash, int(self.now()))
        self._audit(
            {
                "event_type": "logout",
                "request_id": request_id,
                "session_identifier_hash": session_hash,
                "authorization_decision": "allow" if revoked else "deny",
                "reason": "session_revoked" if revoked else "unknown_session",
            }
        )

    def _require_enabled(self) -> None:
        if not self.config.enabled or not self.config.deployment_authorized:
            raise AuthenticationError("gateway_disabled")

    def _audit(self, event: Mapping[str, Any]) -> str:
        try:
            event_id = self.audit(event)
        except GatewayError:
            raise
        except Exception as exc:
            raise AuditUnavailableError("required audit evidence could not be written") from exc
        if not valid_event_id(event_id):
            raise AuditUnavailableError("audit sink returned an invalid event identifier")
        return event_id

    def _audit_denial(
        self,
        event_type: str,
        request_id: str,
        reason: str,
        *,
        actor_subject: Optional[str] = None,
        session_hash: Optional[str] = None,
        required_scope: Optional[str] = None,
        authentication_event_id: Optional[str] = None,
    ) -> None:
        event: dict[str, Any] = {
            "event_type": event_type,
            "request_id": request_id,
            "authorization_decision": "deny",
            "reason": reason,
        }
        if actor_subject:
            event["actor_subject"] = actor_subject
        if session_hash:
            event["session_identifier_hash"] = session_hash
        if required_scope:
            event["required_scope"] = required_scope
        if authentication_event_id:
            event["authentication_event_id"] = authentication_event_id
        self._audit(event)


__all__ = [
    "ACTION_SCOPES", "ALLOWED_SCOPES", "MUTATION_SCOPES", "AssertionIdentity",
    "AuditUnavailableError", "AuthenticationError", "AuthorizationError",
    "ConfigurationError", "Edge1SecurityAuthGateway", "GatewayConfig",
    "JsonlAuditSink", "SQLiteGatewayStore", "SessionContext",
]
