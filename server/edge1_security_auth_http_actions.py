"""Read-only action handling for the Edge1 Security HTTP adapter."""
from __future__ import annotations

from .edge1_operations_client import OperationsClientError, OperationsClientTimeout
from .edge1_security_auth_http_types import HttpRequest, HttpResponse


class SecurityHttpActionMixin:
    def _validate_action(self, request: HttpRequest) -> HttpResponse:
        self._require_same_origin(request)
        if self._content_type(request) != "application/json" or request.body not in (b"", b"{}", b"{}\n"):
            raise ValueError("action_body_invalid")
        token = self._session_token(request)
        request_id = self._request_id()
        context = self.gateway.authorize_action(token, self.config.operations_action, request_id)
        if not self.gateway.store.allow_rate(
            "action:" + context.session_identifier_hash,
            int(self.now()),
            limit=self.config.action_requests,
            window_seconds=self.config.action_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited", "request_id": request_id})
        self._require_csrf(request, context.session_identifier_hash)
        guard = self.gateway.store.begin_action(
            context.session_identifier_hash,
            self.config.operations_action,
            int(self.now()),
            inflight_timeout_seconds=self.config.action_inflight_timeout_seconds,
            cooldown_seconds=self.config.action_cooldown_seconds,
        )
        if guard != "started":
            return self._json(409, {"error": "request_already_in_progress", "request_id": request_id})
        try:
            result = self.operations.run(self.config.operations_action, context.subject)
            self.gateway.correlate_operations_event(
                token,
                action_id=self.config.operations_action,
                operations_event_id=result.event_id,
                request_id=request_id,
            )
        except OperationsClientTimeout:
            return self._json(504, {"error": "operations_timeout", "request_id": request_id})
        except OperationsClientError:
            return self._json(503, {"error": "operations_unavailable", "request_id": request_id})
        finally:
            self.gateway.store.finish_action(
                context.session_identifier_hash,
                self.config.operations_action,
                int(self.now()),
            )
        status_code = 200 if result.status == "succeeded" else 409
        return self._json(status_code, {
            "action": result.action_id,
            "status": result.status,
            "message": result.message,
            "event_id": result.event_id,
            "duration_ms": result.duration_ms,
            "exit_code": result.exit_code,
            "request_id": request_id,
        })
