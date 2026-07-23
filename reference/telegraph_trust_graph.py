#!/usr/bin/env python3
"""Policy-aware multi-hop path selection for Telegraph federation.

The graph is deliberately deterministic and transport-neutral. It excludes
restricted, quarantined, withdrawn, and revoked offices; enforces media and
security requirements at every hop; and ranks eligible paths by trust,
latency, hop count, and operator preference.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Any, Iterable


TRUST_WEIGHT = {
    "trusted": 100,
    "observed": 60,
    "unknown": 10,
    "restricted": -1000,
}

BLOCKED_STATES = {"restricted", "quarantined", "withdrawn", "revoked"}


@dataclass(frozen=True)
class FederationNode:
    office_id: str
    trust_status: str = "unknown"
    operational_status: str = "active"
    media: frozenset[str] = frozenset()
    security: frozenset[str] = frozenset()
    relay_allowed: bool = True
    preference: int = 0

    @property
    def blocked(self) -> bool:
        return self.trust_status == "restricted" or self.operational_status in BLOCKED_STATES


@dataclass(frozen=True)
class FederationLink:
    source: str
    destination: str
    latency_ms: int = 100
    security: frozenset[str] = frozenset()
    media: frozenset[str] = frozenset()
    enabled: bool = True
    cost: int = 0


@dataclass
class RoutePolicy:
    minimum_trust: str = "observed"
    required_security: set[str] = field(default_factory=set)
    required_media: set[str] = field(default_factory=set)
    max_hops: int = 4
    max_latency_ms: int | None = None
    forbidden_offices: set[str] = field(default_factory=set)
    required_offices: set[str] = field(default_factory=set)
    allow_unknown_destination: bool = False

    def __post_init__(self) -> None:
        if self.minimum_trust not in TRUST_WEIGHT:
            raise ValueError("unknown minimum trust")
        if self.max_hops < 1:
            raise ValueError("max_hops must be positive")
        if self.max_latency_ms is not None and self.max_latency_ms < 0:
            raise ValueError("max_latency_ms cannot be negative")


@dataclass(frozen=True)
class PathCandidate:
    offices: tuple[str, ...]
    latency_ms: int
    trust_floor: str
    score: int
    security: frozenset[str]
    media: frozenset[str]

    def document(self) -> dict[str, Any]:
        return {
            "offices": list(self.offices),
            "hop_count": len(self.offices) - 1,
            "estimated_latency_ms": self.latency_ms,
            "trust_floor": self.trust_floor,
            "score": self.score,
            "security": sorted(self.security),
            "media": sorted(self.media),
        }


class TelegraphTrustGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, FederationNode] = {}
        self.links: dict[str, list[FederationLink]] = {}

    def upsert_node(self, node: FederationNode) -> None:
        if not node.office_id:
            raise ValueError("office_id is required")
        self.nodes[node.office_id] = node
        self.links.setdefault(node.office_id, [])

    def add_link(self, link: FederationLink, bidirectional: bool = False) -> None:
        if link.source not in self.nodes or link.destination not in self.nodes:
            raise KeyError("both offices must exist before adding a link")
        if link.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        self.links.setdefault(link.source, []).append(link)
        self.links[link.source].sort(key=lambda item: (item.destination, item.latency_ms, item.cost))
        if bidirectional:
            reverse = FederationLink(
                source=link.destination,
                destination=link.source,
                latency_ms=link.latency_ms,
                security=link.security,
                media=link.media,
                enabled=link.enabled,
                cost=link.cost,
            )
            self.links.setdefault(reverse.source, []).append(reverse)
            self.links[reverse.source].sort(key=lambda item: (item.destination, item.latency_ms, item.cost))

    def quarantine(self, office_id: str) -> None:
        node = self.nodes[office_id]
        self.nodes[office_id] = FederationNode(
            office_id=node.office_id,
            trust_status=node.trust_status,
            operational_status="quarantined",
            media=node.media,
            security=node.security,
            relay_allowed=False,
            preference=node.preference,
        )

    def restore(self, office_id: str) -> None:
        node = self.nodes[office_id]
        self.nodes[office_id] = FederationNode(
            office_id=node.office_id,
            trust_status=node.trust_status,
            operational_status="active",
            media=node.media,
            security=node.security,
            relay_allowed=node.relay_allowed,
            preference=node.preference,
        )

    def _trust_allowed(self, node: FederationNode, policy: RoutePolicy, destination: bool = False) -> bool:
        if node.blocked or node.office_id in policy.forbidden_offices:
            return False
        if destination and policy.allow_unknown_destination and node.trust_status == "unknown":
            return True
        return TRUST_WEIGHT[node.trust_status] >= TRUST_WEIGHT[policy.minimum_trust]

    def _path_capabilities(
        self,
        path: tuple[str, ...],
        links: tuple[FederationLink, ...],
    ) -> tuple[frozenset[str], frozenset[str]]:
        node_security = [self.nodes[office].security for office in path]
        node_media = [self.nodes[office].media for office in path]
        security_sets: list[frozenset[str]] = node_security + [link.security for link in links]
        media_sets: list[frozenset[str]] = node_media + [link.media for link in links]
        security = frozenset.intersection(*security_sets) if security_sets else frozenset()
        media = frozenset.intersection(*media_sets) if media_sets else frozenset()
        return security, media

    def _score(
        self,
        path: tuple[str, ...],
        links: tuple[FederationLink, ...],
        latency_ms: int,
    ) -> tuple[int, str]:
        trust_floor_node = min(path, key=lambda office: TRUST_WEIGHT[self.nodes[office].trust_status])
        trust_floor = self.nodes[trust_floor_node].trust_status
        trust_score = TRUST_WEIGHT[trust_floor] * 100
        preference_score = sum(self.nodes[office].preference for office in path[1:])
        link_cost = sum(link.cost for link in links)
        hop_penalty = (len(path) - 1) * 100
        score = trust_score + preference_score - latency_ms - hop_penalty - link_cost
        return score, trust_floor

    def candidates(
        self,
        origin: str,
        destination: str,
        policy: RoutePolicy,
        limit: int = 5,
    ) -> list[PathCandidate]:
        if origin not in self.nodes or destination not in self.nodes:
            return []
        if limit < 1:
            raise ValueError("limit must be positive")
        if not self._trust_allowed(self.nodes[origin], policy):
            return []
        if not self._trust_allowed(self.nodes[destination], policy, destination=True):
            return []

        queue: list[tuple[int, tuple[str, ...], tuple[FederationLink, ...], int]] = []
        heapq.heappush(queue, (0, (origin,), (), 0))
        results: list[PathCandidate] = []

        while queue and len(results) < limit:
            _priority, path, traversed, latency = heapq.heappop(queue)
            current = path[-1]
            if current == destination:
                if not policy.required_offices.issubset(path):
                    continue
                security, media = self._path_capabilities(path, traversed)
                if not policy.required_security.issubset(security):
                    continue
                if not policy.required_media.issubset(media):
                    continue
                score, trust_floor = self._score(path, traversed, latency)
                results.append(PathCandidate(path, latency, trust_floor, score, security, media))
                continue
            if len(path) - 1 >= policy.max_hops:
                continue

            for link in self.links.get(current, []):
                if not link.enabled or link.destination in path:
                    continue
                node = self.nodes[link.destination]
                is_destination = link.destination == destination
                if not self._trust_allowed(node, policy, destination=is_destination):
                    continue
                if not is_destination and not node.relay_allowed:
                    continue
                next_latency = latency + link.latency_ms
                if policy.max_latency_ms is not None and next_latency > policy.max_latency_ms:
                    continue
                next_path = path + (link.destination,)
                next_links = traversed + (link,)
                heuristic = next_latency + len(next_links) * 100 + sum(item.cost for item in next_links)
                heapq.heappush(queue, (heuristic, next_path, next_links, next_latency))

        results.sort(key=lambda candidate: (-candidate.score, candidate.latency_ms, candidate.offices))
        return results[:limit]

    def route_decision(
        self,
        origin: str,
        destination: str,
        policy: RoutePolicy,
        message_id: str,
    ) -> dict[str, Any]:
        candidates = self.candidates(origin, destination, policy)
        selected = candidates[0] if candidates else None
        rejection_reasons: list[str] = []
        if selected is None:
            if destination not in self.nodes:
                rejection_reasons.append("destination_unknown")
            elif self.nodes[destination].blocked:
                rejection_reasons.append("destination_blocked")
            else:
                rejection_reasons.append("no_policy_compliant_path")
        return {
            "version": "1.0",
            "message_id": message_id,
            "evaluated_at": int(time.time()),
            "origin_office": origin,
            "destination_office": destination,
            "requirements": {
                "minimum_trust": policy.minimum_trust,
                "security": sorted(policy.required_security),
                "media": sorted(policy.required_media),
                "max_hops": policy.max_hops,
                "max_latency_ms": policy.max_latency_ms,
                "forbidden_offices": sorted(policy.forbidden_offices),
                "required_offices": sorted(policy.required_offices),
            },
            "selected_path": selected.document() if selected else None,
            "candidate_paths": [candidate.document() for candidate in candidates],
            "result": "selected" if selected else "rejected",
            "reason_codes": rejection_reasons,
        }

    @classmethod
    def from_directory(cls, records: Iterable[dict[str, Any]]) -> "TelegraphTrustGraph":
        graph = cls()
        pending_links: list[FederationLink] = []
        for record in records:
            office_id = record.get("office_id")
            if not isinstance(office_id, str):
                continue
            capabilities = record.get("capabilities", {})
            graph.upsert_node(FederationNode(
                office_id=office_id,
                trust_status=str(record.get("trust_status", "unknown")),
                operational_status=str(record.get("federation_status", "active")),
                media=frozenset(capabilities.get("media", [])),
                security=frozenset(capabilities.get("security", [])),
                relay_allowed=bool(capabilities.get("relay_allowed", True)),
                preference=int(record.get("route_preference", 0)),
            ))
            for link in record.get("links", []):
                if not isinstance(link, dict) or not isinstance(link.get("destination"), str):
                    continue
                pending_links.append(FederationLink(
                    source=office_id,
                    destination=link["destination"],
                    latency_ms=int(link.get("latency_ms", 100)),
                    security=frozenset(link.get("security", [])),
                    media=frozenset(link.get("media", [])),
                    enabled=bool(link.get("enabled", True)),
                    cost=int(link.get("cost", 0)),
                ))
        for link in pending_links:
            if link.source in graph.nodes and link.destination in graph.nodes:
                graph.add_link(link)
        return graph
