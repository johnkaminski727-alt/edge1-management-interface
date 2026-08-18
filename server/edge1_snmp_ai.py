#!/usr/bin/env python3
"""Provider abstraction for evidence-bounded Edge1 SNMP AI analysis.

The default production adapter reuses the accepted loopback BigBird Private AI
gateway and its existing HMAC identity. Only sanitized evidence is serialized.
Credential profiles, API secrets, SNMP communities and passphrases are never read
by this module and therefore cannot be included in model requests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from edge1_snmp_platform import evidence_query
from edge1_snmp_incidents import incident_summary

DEFAULT_GATEWAY_URL = "http://127.0.0.1:8787/v1/chat"
MAX_PROMPT_BYTES = 16_384
MAX_RESPONSE_BYTES = 1_048_576


class AIProviderError(RuntimeError):
    pass


class AIProvider(Protocol):
    def analyze(self, *, question: str, evidence: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SignedGatewayConfig:
    url: str
    key_id: str
    secret: str

    @classmethod
    def from_environment(cls) -> "SignedGatewayConfig":
        key_id = os.environ.get("BB_RELAY_KEY_ID", "")
        secret = os.environ.get("BB_RELAY_SECRET", "")
        url = os.environ.get("EDGE1_SNMP_AI_GATEWAY_URL", DEFAULT_GATEWAY_URL)
        if not key_id or not secret:
            raise AIProviderError("Private AI gateway signing identity is not configured")
        if len(secret) < 32:
            raise AIProviderError("Private AI gateway signing secret is too short")
        return cls(url=url, key_id=key_id, secret=secret)


def _validate_gateway_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8787:
        raise AIProviderError("SNMP AI provider must use the loopback Private AI gateway on 127.0.0.1:8787")
    if parsed.path != "/v1/chat" or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise AIProviderError("SNMP AI provider gateway path is not approved")
    return parsed.path


def _compact(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _headers(body: bytes, config: SignedGatewayConfig) -> dict[str, str]:
    path = _validate_gateway_url(config.url)
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(body).hexdigest()
    canonical = f"POST\n{path}\n{timestamp}\n{nonce}\n{digest}"
    signature = hmac.new(config.secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-BB-Key-Id": config.key_id,
        "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce,
        "X-BB-Body-Sha256": digest,
        "X-BB-Signature": signature,
        "User-Agent": "wwcx-edge1-snmp-ai/1",
    }


def _sanitize_evidence(value: Any) -> Any:
    """Defensive field-name filter in addition to the upstream sanitized evidence contract."""
    forbidden = ("password", "passphrase", "community", "secret", "credential", "token", "private_key", "api_key")
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in forbidden):
                continue
            clean[str(key)] = _sanitize_evidence(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_evidence(item) for item in value[:500]]
    if isinstance(value, str):
        return value[:4000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1000]


def build_prompt(question: str, evidence: dict[str, Any]) -> str:
    question = question.strip()[:2000]
    clean = _sanitize_evidence(evidence)
    preamble = (
        "You are analyzing WW.CX Edge1 SNMP operational evidence. "
        "Use only the supplied evidence. Separate observed facts, derived metrics, deterministic rule results, "
        "AI inference, confidence, and recommended action. Never claim an inference is verified. "
        "Do not propose arbitrary shell commands or reveal credentials.\nQUESTION: " + question + "\nEVIDENCE: "
    )
    evidence_text = json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    encoded = (preamble + evidence_text).encode("utf-8")
    if len(encoded) > MAX_PROMPT_BYTES:
        budget = max(0, MAX_PROMPT_BYTES - len(preamble.encode("utf-8")) - 64)
        evidence_text = evidence_text.encode("utf-8")[:budget].decode("utf-8", errors="ignore") + "...[truncated]"
    return preamble + evidence_text


class BigBirdPrivateAIProvider:
    def __init__(self, config: SignedGatewayConfig | None = None, *, opener=None):
        self.config = config or SignedGatewayConfig.from_environment()
        self.opener = opener or urllib.request.urlopen
        _validate_gateway_url(self.config.url)

    def analyze(self, *, question: str, evidence: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        payload = {
            "request_id": request_id,
            "user": {"id": "edge1-snmp-ai", "role": "internal_viewer", "scopes": ["chat:general"]},
            "message": build_prompt(question, evidence),
            "include_edge1_status": False,
            "include_messaging_status": False,
            "include_library": False,
            "include_documentation": False,
            "library_collections": [],
            "include_communications": False,
            "communications_groups": [],
            "include_telephony": False,
        }
        body = _compact(payload)
        request = urllib.request.Request(self.config.url, data=body, headers=_headers(body, self.config), method="POST")
        try:
            with self.opener(request, timeout=90.0) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            status = int(exc.code)
        except urllib.error.URLError as exc:
            raise AIProviderError(f"Private AI gateway unavailable: {type(exc.reason).__name__}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AIProviderError("Private AI gateway response exceeded size limit")
        try:
            result = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"Private AI gateway returned unreadable HTTP {status}") from exc
        if not isinstance(result, dict):
            raise AIProviderError("Private AI gateway returned a non-object response")
        if status < 200 or status >= 300:
            raise AIProviderError(f"Private AI gateway rejected request with HTTP {status}")
        if str(result.get("request_id", request_id)) != request_id:
            raise AIProviderError("Private AI gateway response request identifier mismatch")
        return {"provider": "bigbird-private-ai", "request_id": request_id, "response": result}


def analyze_question(conn, question: str, provider: AIProvider | None = None) -> dict[str, Any]:
    deterministic = evidence_query(conn, question)
    incidents = incident_summary(conn, minutes=60) if any(word in question.lower() for word in ("why", "cause", "incident", "unreachable", "flapping")) else None
    evidence = {"operational_query": deterministic}
    if incidents is not None:
        evidence["incident_correlation"] = incidents
    if provider is None:
        provider = BigBirdPrivateAIProvider()
    model = provider.analyze(question=question, evidence=evidence)
    return {
        "question": question,
        "evidence": evidence,
        "ai": model,
        "provenance": {
            "evidence_source": "edge1-snmp-local-datastore",
            "credentials_included": False,
            "numerical_processing": "deterministic",
            "model_role": "interpretation-only",
        },
    }
