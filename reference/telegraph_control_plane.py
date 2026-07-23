#!/usr/bin/env python3
"""Leaderless control-plane state for Telegraph federation offices.

This module produces and consumes signed heartbeat documents, tracks peer
liveness and congestion, computes deterministic health scores and route-cost
adjustments, represents maintenance windows, and emits quarantine recommendations.
It does not itself mutate production routing or trust state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from reference.telegraph_crypto import verify_document


HEALTHY = "healthy"
DEGRADED = "degraded"
UNREACHABLE = "unreachable"
MAINTENANCE = "maintenance"
QUARANTINE_RECOMMENDED = "quarantine_recommended"


@dataclass(frozen=True)
class ControlPlanePolicy:
    heartbeat_interval_seconds: int = 30
    degraded_after_seconds: int = 90
    unreachable_after_seconds: int = 180
    quarantine_after_failures: int = 5
    quarantine_score_threshold: int = 20
    congestion_warning_percent: int = 75
    congestion_critical_percent: int = 95
    maximum_clock_skew_seconds: int = 300
    base_route_cost: int = 100

    def __post_init__(self) -> None:
        positive = (
            self.heartbeat_interval_seconds,
            self.degraded_after_seconds,
            self.unreachable_after_seconds,
            self.quarantine_after_failures,
            self.maximum_clock_skew_seconds,
            self.base_route_cost,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("control-plane thresholds must be positive")
        if self.degraded_after_seconds >= self.unreachable_after_seconds:
            raise ValueError("degraded threshold must precede unreachable threshold")
        if not 0 <= self.quarantine_score_threshold <= 100:
            raise ValueError("quarantine score threshold must be between 0 and 100")
        if not 0 <= self.congestion_warning_percent < self.congestion_critical_percent <= 100:
            raise ValueError("invalid congestion thresholds")


@dataclass
class PeerObservation:
    office_id: str
    sequence: int = 0
    last_seen_at: int | None = None
    last_issued_at: int | None = None
    consecutive_failures: int = 0
    latency_ms: int | None = None
    queue_depth: int = 0
    queue_capacity: int = 0
    active_workers: int = 0
    maintenance_until: int | None = None
    advertised_status: str = HEALTHY
    service_health: dict[str, str] = field(default_factory=dict)
    capabilities_digest: str | None = None
    health_score: int = 0
    derived_status: str = UNREACHABLE
    route_cost: int = 10000
    quarantine_recommended: bool = False
    last_error: str | None = None

    @property
    def congestion_percent(self) -> int:
        if self.queue_capacity <= 0:
            return 0
        return min(100, max(0, round(self.queue_depth * 100 / self.queue_capacity)))

    def document(self) -> dict[str, Any]:
        return {
            "office_id": self.office_id,
            "sequence": self.sequence,
            "last_seen_at": self.last_seen_at,
            "last_issued_at": self.last_issued_at,
            "consecutive_failures": self.consecutive_failures,
            "latency_ms": self.latency_ms,
            "queue_depth": self.queue_depth,
            "queue_capacity": self.queue_capacity,
            "congestion_percent": self.congestion_percent,
            "active_workers": self.active_workers,
            "maintenance_until": self.maintenance_until,
            "advertised_status": self.advertised_status,
            "service_health": dict(sorted(self.service_health.items())),
            "capabilities_digest": self.capabilities_digest,
            "health_score": self.health_score,
            "derived_status": self.derived_status,
            "route_cost": self.route_cost,
            "quarantine_recommended": self.quarantine_recommended,
            "last_error": self.last_error,
        }


class TelegraphControlPlane:
    def __init__(self, office_id: str, policy: ControlPlanePolicy | None = None) -> None:
        if not office_id:
            raise ValueError("office_id is required")
        self.office_id = office_id
        self.policy = policy or ControlPlanePolicy()
        self.local_sequence = 0
        self.peers: dict[str, PeerObservation] = {}

    def heartbeat(
        self,
        signer: Callable[[dict[str, Any]], dict[str, str]],
        metrics: dict[str, Any],
        now: int | None = None,
    ) -> dict[str, Any]:
        timestamp = int(time.time()) if now is None else int(now)
        self.local_sequence += 1
        queue_depth = int(metrics.get("queue_depth", 0))
        queue_capacity = int(metrics.get("queue_capacity", 0))
        if queue_depth < 0 or queue_capacity < 0 or queue_depth > queue_capacity > 0:
            raise ValueError("invalid queue metrics")
        services = metrics.get("services", {})
        if not isinstance(services, dict):
            raise ValueError("services must be an object")
        document: dict[str, Any] = {
            "version": "1.0",
            "kind": "telegraph_control_heartbeat",
            "office_id": self.office_id,
            "sequence": self.local_sequence,
            "issued_at": timestamp,
            "valid_until": timestamp + self.policy.heartbeat_interval_seconds * 2,
            "status": str(metrics.get("status", HEALTHY)),
            "maintenance_until": metrics.get("maintenance_until"),
            "metrics": {
                "latency_ms": max(0, int(metrics.get("latency_ms", 0))),
                "queue_depth": queue_depth,
                "queue_capacity": queue_capacity,
                "active_workers": max(0, int(metrics.get("active_workers", 0))),
                "services": dict(sorted((str(key), str(value)) for key, value in services.items())),
            },
            "capabilities_digest": metrics.get("capabilities_digest"),
        }
        document["signature"] = signer(document)
        return document

    def ingest(
        self,
        heartbeat: dict[str, Any],
        identity: dict[str, Any],
        received_at: int | None = None,
        measured_latency_ms: int | None = None,
    ) -> PeerObservation:
        now = int(time.time()) if received_at is None else int(received_at)
        if heartbeat.get("kind") != "telegraph_control_heartbeat":
            raise ValueError("unsupported control-plane document")
        office_id = heartbeat.get("office_id")
        if not isinstance(office_id, str) or identity.get("office_id") != office_id:
            raise ValueError("heartbeat identity mismatch")
        if not verify_document(heartbeat, identity):
            raise ValueError("invalid heartbeat signature")
        issued_at = int(heartbeat.get("issued_at", 0))
        valid_until = int(heartbeat.get("valid_until", 0))
        if abs(now - issued_at) > self.policy.maximum_clock_skew_seconds:
            raise ValueError("heartbeat outside allowed clock skew")
        if valid_until < now:
            raise ValueError("heartbeat expired")
        sequence = int(heartbeat.get("sequence", 0))
        observation = self.peers.setdefault(office_id, PeerObservation(office_id=office_id))
        if sequence <= observation.sequence:
            raise ValueError("stale or replayed heartbeat")
        metrics = heartbeat.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ValueError("heartbeat metrics are invalid")
        queue_depth = max(0, int(metrics.get("queue_depth", 0)))
        queue_capacity = max(0, int(metrics.get("queue_capacity", 0)))
        if queue_capacity and queue_depth > queue_capacity:
            raise ValueError("queue depth exceeds advertised capacity")
        observation.sequence = sequence
        observation.last_seen_at = now
        observation.last_issued_at = issued_at
        observation.consecutive_failures = 0
        observation.latency_ms = (
            max(0, int(measured_latency_ms))
            if measured_latency_ms is not None
            else max(0, int(metrics.get("latency_ms", 0)))
        )
        observation.queue_depth = queue_depth
        observation.queue_capacity = queue_capacity
        observation.active_workers = max(0, int(metrics.get("active_workers", 0)))
        maintenance = heartbeat.get("maintenance_until")
        observation.maintenance_until = int(maintenance) if maintenance is not None else None
        observation.advertised_status = str(heartbeat.get("status", HEALTHY))
        services = metrics.get("services", {})
        observation.service_health = (
            {str(key): str(value) for key, value in services.items()} if isinstance(services, dict) else {}
        )
        digest = heartbeat.get("capabilities_digest")
        observation.capabilities_digest = str(digest) if digest is not None else None
        observation.last_error = None
        self._derive(observation, now)
        return observation

    def record_failure(self, office_id: str, error: str, now: int | None = None) -> PeerObservation:
        timestamp = int(time.time()) if now is None else int(now)
        observation = self.peers.setdefault(office_id, PeerObservation(office_id=office_id))
        observation.consecutive_failures += 1
        observation.last_error = error[:1000]
        self._derive(observation, timestamp)
        return observation

    def refresh(self, now: int | None = None) -> list[PeerObservation]:
        timestamp = int(time.time()) if now is None else int(now)
        for observation in self.peers.values():
            self._derive(observation, timestamp)
        return sorted(self.peers.values(), key=lambda item: item.office_id)

    def _derive(self, observation: PeerObservation, now: int) -> None:
        age = self.policy.unreachable_after_seconds + 1
        if observation.last_seen_at is not None:
            age = max(0, now - observation.last_seen_at)
        in_maintenance = observation.maintenance_until is not None and now < observation.maintenance_until
        if in_maintenance or observation.advertised_status == MAINTENANCE:
            status = MAINTENANCE
        elif age >= self.policy.unreachable_after_seconds:
            status = UNREACHABLE
        elif age >= self.policy.degraded_after_seconds:
            status = DEGRADED
        elif observation.advertised_status in {DEGRADED, UNREACHABLE}:
            status = observation.advertised_status
        elif any(value not in {"healthy", "ok", "ready"} for value in observation.service_health.values()):
            status = DEGRADED
        else:
            status = HEALTHY

        score = 100
        if status == MAINTENANCE:
            score = 40
        elif status == DEGRADED:
            score -= 35
        elif status == UNREACHABLE:
            score = 0
        score -= min(40, observation.consecutive_failures * 10)
        if observation.latency_ms is not None:
            score -= min(25, observation.latency_ms // 100)
        congestion = observation.congestion_percent
        if congestion >= self.policy.congestion_critical_percent:
            score -= 35
        elif congestion >= self.policy.congestion_warning_percent:
            score -= 15
        if observation.active_workers == 0 and observation.queue_depth > 0:
            score -= 20
        score = min(100, max(0, score))

        quarantine = (
            observation.consecutive_failures >= self.policy.quarantine_after_failures
            or (status == UNREACHABLE and score <= self.policy.quarantine_score_threshold)
        )
        if quarantine:
            status = QUARANTINE_RECOMMENDED

        route_cost = self.policy.base_route_cost
        route_cost += (100 - score) * 10
        route_cost += congestion * 3
        if observation.latency_ms is not None:
            route_cost += observation.latency_ms
        if status == MAINTENANCE:
            route_cost += 5000
        elif status in {UNREACHABLE, QUARANTINE_RECOMMENDED}:
            route_cost += 100000

        observation.health_score = score
        observation.derived_status = status
        observation.route_cost = route_cost
        observation.quarantine_recommended = quarantine

    def route_costs(self, now: int | None = None) -> dict[str, int]:
        self.refresh(now)
        return {office_id: item.route_cost for office_id, item in sorted(self.peers.items())}

    def quarantine_recommendations(self, now: int | None = None) -> list[dict[str, Any]]:
        self.refresh(now)
        return [
            {
                "office_id": item.office_id,
                "reason": "control_plane_health_threshold",
                "health_score": item.health_score,
                "consecutive_failures": item.consecutive_failures,
                "last_seen_at": item.last_seen_at,
                "last_error": item.last_error,
            }
            for item in sorted(self.peers.values(), key=lambda peer: peer.office_id)
            if item.quarantine_recommended
        ]

    def snapshot(self, now: int | None = None) -> dict[str, Any]:
        timestamp = int(time.time()) if now is None else int(now)
        self.refresh(timestamp)
        return {
            "version": "1.0",
            "kind": "telegraph_control_snapshot",
            "observer_office": self.office_id,
            "generated_at": timestamp,
            "peers": [peer.document() for peer in sorted(self.peers.values(), key=lambda item: item.office_id)],
        }
