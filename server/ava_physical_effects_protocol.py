#!/usr/bin/env python3
"""Bounded protocol for the AVA physical-presentation broker.

The protocol accepts only a request identifier and a fixed catalogue effect.
Peer identity is supplied by the trusted transport boundary and checked here.
This module performs no hardware access.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

try:
    from ava_physical_effects_broker import BrokerPolicy, BrokerPolicyError
except ImportError:
    from server.ava_physical_effects_broker import BrokerPolicy, BrokerPolicyError


PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 512


class ProtocolError(ValueError):
    """Raised when a physical-effect protocol request fails closed."""


@dataclass(frozen=True)
class PeerIdentity:
    pid: int
    uid: int
    gid: int


class PhysicalEffectsProtocol:
    def __init__(
        self,
        policy: BrokerPolicy,
        *,
        allowed_uid: int,
        allowed_gid: int,
    ) -> None:
        if allowed_uid < 0 or allowed_gid < 0:
            raise ProtocolError("invalid allowed peer identity")

        self.policy = policy
        self.allowed_uid = int(allowed_uid)
        self.allowed_gid = int(allowed_gid)

    def _authorize_peer(self, peer: PeerIdentity) -> None:
        if not isinstance(peer, PeerIdentity):
            raise ProtocolError("missing peer credentials")

        if peer.uid != self.allowed_uid or peer.gid != self.allowed_gid:
            raise ProtocolError("peer is not authorized")

    @staticmethod
    def _parse(payload: bytes) -> tuple[str, str]:
        if not isinstance(payload, bytes):
            raise ProtocolError("request must be bytes")

        if not payload or len(payload) > MAX_REQUEST_BYTES:
            raise ProtocolError("invalid request size")

        try:
            request = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("invalid request encoding") from exc

        if not isinstance(request, dict):
            raise ProtocolError("request must be an object")

        if set(request) != {"version", "request_id", "catalogue_effect"}:
            raise ProtocolError("request fields are not exact")

        if request["version"] != PROTOCOL_VERSION:
            raise ProtocolError("unsupported protocol version")

        request_id = request["request_id"]
        catalogue_effect = request["catalogue_effect"]

        if not isinstance(request_id, str) or not isinstance(catalogue_effect, str):
            raise ProtocolError("request fields have invalid types")

        return request_id, catalogue_effect

    def handle(self, payload: bytes, peer: PeerIdentity) -> bytes:
        self._authorize_peer(peer)
        request_id, catalogue_effect = self._parse(payload)

        try:
            decision = self.policy.decide(request_id, catalogue_effect)
        except BrokerPolicyError as exc:
            raise ProtocolError("broker policy rejected request") from exc

        response = {
            "version": PROTOCOL_VERSION,
            "request_id": decision.request_id,
            "catalogue_effect": decision.catalogue_effect,
            "disposition": decision.disposition,
        }

        return (
            json.dumps(
                response,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
