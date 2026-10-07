#!/usr/bin/env python3
"""Bounded planning, source routing, and verification for the WW.CX Ava browser agent.

This module never grants scopes, never executes host commands, and never changes the
Private AI gateway listener contract. It may only reduce already-authorized read-only
source selections before a request is relayed to the loopback gateway.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

CONTROLLER_VERSION = "0.3.0"
MAX_STEPS = 10


class AgentControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceRule:
    step_id: str
    label: str
    flag: str
    scope: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class AgentStep:
    step_id: str
    label: str
    capability: str

    def public(self) -> dict[str, str]:
        return {"id": self.step_id, "label": self.label, "capability": self.capability}


@dataclass(frozen=True)
class AgentPlan:
    request_id: str
    auto_route: bool
    source_flags: dict[str, bool]
    steps: tuple[AgentStep, ...]

    def public(self) -> dict[str, Any]:
        return {
            "controller_version": CONTROLLER_VERSION,
            "mode": "auto-route-read-only" if self.auto_route else "explicit-read-only",
            "steps": [step.public() for step in self.steps],
        }


SOURCE_RULES: tuple[SourceRule, ...] = (
    SourceRule("systems", "Check current systems", "include_edge1_status", "edge1:status:read", (
        "status", "health", "system", "service", "edge1", "server", "host", "network", "disk", "uptime", "listener",
    )),
    SourceRule("knowledge", "Search private knowledge", "include_library", "library:search", (
        "search", "find", "knowledge", "archive", "record", "project", "history", "document", "file", "source", "latest", "previous",
    )),
    SourceRule("documentation", "Review documentation", "include_documentation", "library:document:read", (
        "documentation", "docs", "runbook", "procedure", "architecture", "design", "config", "configuration", "how", "reference",
    )),
    SourceRule("mail", "Review Mail Room", "include_mail", "mail:read", (
        "email", "mail", "message", "inbox", "mail room", "mailroom", "quarantine", "junk", "unread", "correspondence",
    )),
    SourceRule("communications", "Review communications", "include_communications", "communications:read", (
        "communications", "conversation", "irc", "nntp", "news", "newsgroup", "relay", "said", "wrote",
    )),
    SourceRule("contacts", "Search Unified Contacts", "include_contacts", "contacts:read", (
        "contact", "contacts", "person", "people", "organization", "company", "business",
        "phone number", "telephone number", "email address", "who is", "who owns", "caller", "directory",
    )),
    SourceRule("voice", "Check Voice & PBX", "include_telephony", "telephony:read", (
        "call", "phone", "voice", "pbx", "asterisk", "freepbx", "sip", "pjsip", "trunk", "telephony", "voicemail",
    )),
)

WEB_RULE = SourceRule("web", "Research public websites", "include_web", "web:search",
    ("web", "website", "online", "research", "latest", "current", "search", "look up"))

OPTIONAL_SCOPES = {"web:search"} | {rule.scope for rule in SOURCE_RULES} | {"library:document:read"}
FORBIDDEN_RESULT_KEYS = {
    "body", "raw_body", "raw_article_body", "raw_mime", "password", "passwd", "secret",
    "api_key", "token", "authorization", "sip_password", "private_key",
}


def _message(payload: dict[str, Any]) -> str:
    value = payload.get("routing_message", payload.get("message", ""))
    return value.lower() if isinstance(value, str) else ""


def _keyword_match(message: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in message for keyword in keywords)


def build_plan(payload: dict[str, Any]) -> AgentPlan:
    request_id = str(payload.get("request_id", ""))
    if not request_id:
        raise AgentControllerError("request identifier is missing")
    auto_route = payload.get("agent_auto_route") is True
    message = _message(payload)
    source_flags: dict[str, bool] = {}
    steps: list[AgentStep] = [AgentStep("understand", "Understand the request", "chat")]

    for rule in SOURCE_RULES + ((WEB_RULE,) if "include_web" in payload else ()):
        enabled = payload.get(rule.flag) is True
        selected = enabled and ((rule.flag == "include_web" and bool(payload.get("web_query"))) or not auto_route or _keyword_match(message, rule.keywords))
        source_flags[rule.flag] = selected
        if selected:
            steps.append(AgentStep(rule.step_id, rule.label, rule.scope))

    steps.append(AgentStep("synthesize", "Synthesize the answer", "chat"))
    steps.append(AgentStep("verify", "Verify evidence and boundaries", "verification"))
    if len(steps) > MAX_STEPS:
        raise AgentControllerError("agent plan exceeds the bounded step limit")
    return AgentPlan(request_id=request_id, auto_route=auto_route, source_flags=source_flags, steps=tuple(steps))


def _normalize_library_collections(payload: dict[str, Any], enabled: bool) -> list[str]:
    value = payload.get("library_collections", [])
    if not isinstance(value, list) or len(value) > 8:
        raise AgentControllerError("library collection selection is invalid")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AgentControllerError("library collection selection is invalid")
        candidate = item.strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", candidate) is None:
            raise AgentControllerError("library collection name is invalid")
        if candidate not in normalized:
            normalized.append(candidate)
    if enabled and not normalized:
        raise AgentControllerError("library search requires an approved collection")
    if not enabled and normalized:
        raise AgentControllerError("library collections require library access")
    return normalized


def prepare_gateway_request(payload: dict[str, Any], plan: AgentPlan) -> dict[str, Any]:
    prepared = dict(payload)
    for key in tuple(prepared):
        if key.startswith("agent_"):
            prepared.pop(key, None)

    for flag, selected in plan.source_flags.items():
        if selected and payload.get(flag) is not True:
            raise AgentControllerError(f"controller attempted to expand {flag}")
        prepared[flag] = selected

    if prepared.get("include_library") is True:
        prepared["library_collections"] = _normalize_library_collections(payload, True)
    elif payload.get("include_library") is True:
        # Auto-routing may only narrow an already-authorized Library request.
        # Discard its approved collections when Library is not selected.
        prepared["library_collections"] = []
    else:
        prepared["library_collections"] = _normalize_library_collections(payload, False)
    if prepared.get("include_communications") is not True:
        prepared["communications_groups"] = []

    user = prepared.get("user")
    if isinstance(user, dict):
        clean_user = dict(user)
        scopes = clean_user.get("scopes")
        if isinstance(scopes, list):
            allowed_optional: set[str] = set()
            if prepared.get("include_edge1_status") is True:
                allowed_optional.add("edge1:status:read")
            if prepared.get("include_library") is True:
                allowed_optional.update({"library:search", "library:document:read"})
            if prepared.get("include_mail") is True:
                allowed_optional.add("mail:read")
            if prepared.get("include_communications") is True:
                allowed_optional.add("communications:read")
            if prepared.get("include_contacts") is True:
                allowed_optional.add("contacts:read")
            if prepared.get("include_telephony") is True:
                allowed_optional.add("telephony:read")
            if prepared.get("include_web") is True:
                allowed_optional.add("web:search")
            else:
                prepared.pop("web_query", None)
            clean_user["scopes"] = [
                scope for scope in scopes
                if isinstance(scope, str) and (scope not in OPTIONAL_SCOPES or scope in allowed_optional)
            ]
        prepared["user"] = clean_user
    return prepared


def progress_payload(plan: AgentPlan, phase: str, message: str, active_step: str | None = None) -> dict[str, Any]:
    if phase not in {"planning", "gathering", "verifying", "complete"}:
        raise AgentControllerError("invalid progress phase")
    return {
        "phase": phase,
        "message": str(message)[:180],
        "active_step": active_step if active_step in {s.step_id for s in plan.steps} else None,
        "plan": [step.public() for step in plan.steps],
        "controller_version": CONTROLLER_VERSION,
    }


def _source_count(result: dict[str, Any], key: str) -> int:
    value = result.get(key)
    return len(value) if isinstance(value, list) else 0


def _reject_sensitive_keys(value: Any, path: str = "result") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_RESULT_KEYS:
                raise AgentControllerError(f"gateway result exposed forbidden field at {path}.{lowered}")
            _reject_sensitive_keys(child, f"{path}.{lowered}")
    elif isinstance(value, list):
        for index, child in enumerate(value[:32]):
            _reject_sensitive_keys(child, f"{path}[{index}]")


ALLOWED_UI_EFFECTS = frozenset({
    "blue_tit_easter_egg",
    "donkey_easter_egg",
    "cat_easter_egg",
    "moist_owlette_easter_egg",
})


def sanitize_gateway_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with presentation-only UI effects independently allowlisted."""
    sanitized = dict(result)
    raw_effects = result.get("ui_effects", [])

    effects: list[str] = []
    if isinstance(raw_effects, list):
        for effect in raw_effects[:8]:
            if (
                isinstance(effect, str)
                and effect in ALLOWED_UI_EFFECTS
                and effect not in effects
            ):
                effects.append(effect)

    sanitized["ui_effects"] = effects
    return sanitized


def verify_gateway_result(request_id: str, result: dict[str, Any], plan: AgentPlan) -> dict[str, Any]:
    if str(result.get("request_id", "")) != request_id:
        raise AgentControllerError("gateway response request identifier mismatch")
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 65536:
        raise AgentControllerError("gateway answer is empty or out of bounds")
    mode = str(result.get("mode", "read-only"))
    if mode != "read-only":
        raise AgentControllerError("Ava browser agent requires read-only gateway mode")
    _reject_sensitive_keys(result)

    evidence = {
        "knowledge": _source_count(result, "sources"),
        "communications": _source_count(result, "communications_sources"),
        "contacts": _source_count(result, "contact_sources"),
        "telephony": _source_count(result, "telephony_sources"),
        "mail": _source_count(result, "mail_sources"),
    }
    evidence_total = sum(evidence.values())
    return {
        "controller_version": CONTROLLER_VERSION,
        "mode": "auto-route-read-only" if plan.auto_route else "explicit-read-only",
        "verification": "passed",
        "steps": [{**step.public(), "status": "completed"} for step in plan.steps],
        "evidence": evidence,
        "evidence_total": evidence_total,
        "evidence_class": "source-backed" if evidence_total else "model-synthesis",
    }
