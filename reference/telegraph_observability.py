#!/usr/bin/env python3
"""Operator-facing observability model for Telegraph federation components.

The service composes control-plane, routing, and store-and-forward state into
stable dashboard documents. It stores normalized operational events, derives
alerts without mutating production state, and emits privacy-conscious diagnostic
bundles that exclude encrypted envelope bodies and private key material.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


@dataclass(frozen=True)
class AlertThresholds:
    queue_warning_percent: int = 75
    queue_critical_percent: int = 95
    peer_health_warning: int = 60
    peer_health_critical: int = 20
    retry_warning_count: int = 5
    stale_seconds: int = 180

    def __post_init__(self) -> None:
        if not 0 <= self.queue_warning_percent < self.queue_critical_percent <= 100:
            raise ValueError("invalid queue thresholds")
        if not 0 <= self.peer_health_critical < self.peer_health_warning <= 100:
            raise ValueError("invalid peer health thresholds")
        if self.retry_warning_count < 1 or self.stale_seconds < 1:
            raise ValueError("retry and stale thresholds must be positive")


class TelegraphObservability:
    def __init__(
        self,
        database: str | Path,
        office_id: str,
        thresholds: AlertThresholds | None = None,
    ) -> None:
        self.database = str(database)
        self.office_id = office_id
        self.thresholds = thresholds or AlertThresholds()
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "TelegraphObservability":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telegraph_observation_events (
                event_id TEXT PRIMARY KEY,
                recorded_at INTEGER NOT NULL,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                office_id TEXT,
                message_id TEXT,
                summary TEXT NOT NULL,
                detail_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS telegraph_observation_events_time
              ON telegraph_observation_events(recorded_at DESC);
            CREATE INDEX IF NOT EXISTS telegraph_observation_events_message
              ON telegraph_observation_events(message_id, recorded_at DESC);
            CREATE TABLE IF NOT EXISTS telegraph_alert_state (
                alert_key TEXT PRIMARY KEY,
                first_seen_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                acknowledged_at INTEGER,
                acknowledged_by TEXT
            );
            """
        )
        self.connection.commit()

    def record_event(
        self,
        source: str,
        event_type: str,
        summary: str,
        severity: str = "info",
        office_id: str | None = None,
        message_id: str | None = None,
        detail: dict[str, Any] | None = None,
        recorded_at: int | None = None,
    ) -> str:
        if severity not in SEVERITY_ORDER:
            raise ValueError("invalid severity")
        timestamp = int(time.time()) if recorded_at is None else int(recorded_at)
        event_id = str(uuid.uuid4())
        safe_detail = self._redact(detail or {})
        with self.connection:
            self.connection.execute(
                """INSERT INTO telegraph_observation_events(
                    event_id,recorded_at,source,event_type,severity,office_id,
                    message_id,summary,detail_json
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    timestamp,
                    source,
                    event_type,
                    severity,
                    office_id,
                    message_id,
                    summary[:500],
                    json.dumps(safe_detail, sort_keys=True, separators=(",", ":")),
                ),
            )
        return event_id

    @staticmethod
    def _redact(value: Any) -> Any:
        sensitive = {
            "private_key", "private_key_pem", "secret", "token", "authorization",
            "ciphertext", "encrypted_payload", "envelope", "payload",
        }
        if isinstance(value, dict):
            return {
                str(key): "[redacted]" if str(key).lower() in sensitive else TelegraphObservability._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [TelegraphObservability._redact(item) for item in value]
        return value

    def timeline(
        self,
        limit: int = 100,
        minimum_severity: str = "info",
        office_id: str | None = None,
        message_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if minimum_severity not in SEVERITY_ORDER:
            raise ValueError("invalid minimum severity")
        clauses = []
        parameters: list[Any] = []
        if office_id is not None:
            clauses.append("office_id=?")
            parameters.append(office_id)
        if message_id is not None:
            clauses.append("message_id=?")
            parameters.append(message_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT * FROM telegraph_observation_events" + where + " ORDER BY recorded_at DESC,event_id DESC LIMIT ?",
            (*parameters, limit),
        ).fetchall()
        floor = SEVERITY_ORDER[minimum_severity]
        return [
            {
                "event_id": row["event_id"],
                "recorded_at": int(row["recorded_at"]),
                "source": row["source"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "office_id": row["office_id"],
                "message_id": row["message_id"],
                "summary": row["summary"],
                "detail": json.loads(row["detail_json"]),
            }
            for row in rows
            if SEVERITY_ORDER[row["severity"]] >= floor
        ]

    def queue_summary(self, queue_connection: sqlite3.Connection) -> dict[str, Any]:
        queue_connection.row_factory = sqlite3.Row
        state_rows = queue_connection.execute(
            "SELECT state,COUNT(*) AS count,COALESCE(SUM(size_bytes),0) AS bytes FROM telegraph_queue GROUP BY state"
        ).fetchall()
        priority_rows = queue_connection.execute(
            """SELECT priority,COUNT(*) AS count FROM telegraph_queue
               WHERE state IN ('queued','retry_wait','in_flight') GROUP BY priority"""
        ).fetchall()
        retry_row = queue_connection.execute(
            """SELECT COUNT(*) AS count,COALESCE(MAX(attempt_count),0) AS maximum
               FROM telegraph_queue WHERE state='retry_wait'"""
        ).fetchone()
        states = {row["state"]: {"messages": int(row["count"]), "bytes": int(row["bytes"])} for row in state_rows}
        active_messages = sum(states.get(state, {}).get("messages", 0) for state in ("queued", "retry_wait", "in_flight"))
        active_bytes = sum(states.get(state, {}).get("bytes", 0) for state in ("queued", "retry_wait", "in_flight"))
        return {
            "active_messages": active_messages,
            "active_bytes": active_bytes,
            "states": states,
            "priorities": {row["priority"]: int(row["count"]) for row in priority_rows},
            "retry_wait_messages": int(retry_row["count"]),
            "maximum_attempt_count": int(retry_row["maximum"]),
        }

    def peer_summary(self, control_snapshot: dict[str, Any]) -> dict[str, Any]:
        peers = list(control_snapshot.get("peers", []))
        status_counts: dict[str, int] = {}
        for peer in peers:
            status = str(peer.get("derived_status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
        ordered = sorted(peers, key=lambda item: (int(item.get("health_score", 0)), str(item.get("office_id", ""))))
        return {
            "peer_count": len(peers),
            "status_counts": status_counts,
            "lowest_health": ordered[:10],
            "quarantine_recommendations": [
                peer for peer in peers if bool(peer.get("quarantine_recommended", False))
            ],
        }

    def route_summary(self, decisions: Iterable[dict[str, Any]]) -> dict[str, Any]:
        selected = rejected = 0
        reasons: dict[str, int] = {}
        hop_total = latency_total = 0
        for decision in decisions:
            if decision.get("result") == "selected":
                selected += 1
                path = decision.get("selected_path") or {}
                hop_total += int(path.get("hop_count", 0))
                latency_total += int(path.get("estimated_latency_ms", 0))
            else:
                rejected += 1
                for reason in decision.get("reason_codes", []):
                    reasons[str(reason)] = reasons.get(str(reason), 0) + 1
        return {
            "selected": selected,
            "rejected": rejected,
            "rejection_reasons": reasons,
            "average_hops": round(hop_total / selected, 2) if selected else None,
            "average_latency_ms": round(latency_total / selected, 2) if selected else None,
        }

    def evaluate_alerts(
        self,
        queue: dict[str, Any],
        peers: dict[str, Any],
        queue_capacity_messages: int | None = None,
        now: int | None = None,
    ) -> list[dict[str, Any]]:
        timestamp = int(time.time()) if now is None else int(now)
        observed: dict[str, tuple[str, str, dict[str, Any]]] = {}
        if queue_capacity_messages and queue_capacity_messages > 0:
            utilization = min(100, round(queue["active_messages"] * 100 / queue_capacity_messages))
            if utilization >= self.thresholds.queue_critical_percent:
                observed["queue.capacity"] = ("critical", "Store-and-forward queue nearly full", {"utilization_percent": utilization})
            elif utilization >= self.thresholds.queue_warning_percent:
                observed["queue.capacity"] = ("warning", "Store-and-forward queue filling", {"utilization_percent": utilization})
        if int(queue.get("maximum_attempt_count", 0)) >= self.thresholds.retry_warning_count:
            observed["queue.retries"] = (
                "warning", "Messages are experiencing repeated delivery failures",
                {"maximum_attempt_count": int(queue["maximum_attempt_count"])},
            )
        for peer in peers.get("lowest_health", []):
            office = str(peer.get("office_id", "unknown"))
            score = int(peer.get("health_score", 0))
            if score <= self.thresholds.peer_health_critical:
                observed[f"peer.{office}.health"] = ("critical", f"Federation office {office} is critically unhealthy", {"peer": peer})
            elif score <= self.thresholds.peer_health_warning:
                observed[f"peer.{office}.health"] = ("warning", f"Federation office {office} is degraded", {"peer": peer})

        with self.connection:
            active_keys = {row["alert_key"] for row in self.connection.execute("SELECT alert_key FROM telegraph_alert_state WHERE status='active'")}
            for key, (severity, title, detail) in observed.items():
                existing = self.connection.execute("SELECT first_seen_at FROM telegraph_alert_state WHERE alert_key=?", (key,)).fetchone()
                first_seen = int(existing["first_seen_at"]) if existing else timestamp
                self.connection.execute(
                    """INSERT INTO telegraph_alert_state(
                        alert_key,first_seen_at,last_seen_at,severity,status,title,detail_json
                    ) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(alert_key) DO UPDATE SET
                        last_seen_at=excluded.last_seen_at,severity=excluded.severity,status='active',
                        title=excluded.title,detail_json=excluded.detail_json""",
                    (key, first_seen, timestamp, severity, "active", title, json.dumps(self._redact(detail), sort_keys=True)),
                )
            for key in active_keys - set(observed):
                self.connection.execute(
                    "UPDATE telegraph_alert_state SET status='resolved',last_seen_at=? WHERE alert_key=?",
                    (timestamp, key),
                )
        return self.alerts(status="active")

    def acknowledge_alert(self, alert_key: str, operator: str, now: int | None = None) -> None:
        timestamp = int(time.time()) if now is None else int(now)
        with self.connection:
            changed = self.connection.execute(
                "UPDATE telegraph_alert_state SET acknowledged_at=?,acknowledged_by=? WHERE alert_key=? AND status='active'",
                (timestamp, operator, alert_key),
            ).rowcount
        if not changed:
            raise KeyError(alert_key)

    def alerts(self, status: str | None = None) -> list[dict[str, Any]]:
        if status not in {None, "active", "resolved"}:
            raise ValueError("invalid alert status")
        rows = self.connection.execute(
            "SELECT * FROM telegraph_alert_state" + (" WHERE status=?" if status else "") + " ORDER BY severity DESC,last_seen_at DESC,alert_key",
            (status,) if status else (),
        ).fetchall()
        alerts = [
            {
                "alert_key": row["alert_key"],
                "first_seen_at": int(row["first_seen_at"]),
                "last_seen_at": int(row["last_seen_at"]),
                "severity": row["severity"],
                "status": row["status"],
                "title": row["title"],
                "detail": json.loads(row["detail_json"]),
                "acknowledged_at": row["acknowledged_at"],
                "acknowledged_by": row["acknowledged_by"],
            }
            for row in rows
        ]
        alerts.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], -item["last_seen_at"], item["alert_key"]))
        return alerts

    def dashboard_snapshot(
        self,
        queue_summary: dict[str, Any],
        peer_summary: dict[str, Any],
        route_summary: dict[str, Any],
        now: int | None = None,
    ) -> dict[str, Any]:
        timestamp = int(time.time()) if now is None else int(now)
        active_alerts = self.alerts(status="active")
        overall = "healthy"
        if any(alert["severity"] == "critical" for alert in active_alerts):
            overall = "critical"
        elif active_alerts:
            overall = "degraded"
        return {
            "version": "1.0",
            "kind": "telegraph_operator_dashboard",
            "office_id": self.office_id,
            "generated_at": timestamp,
            "overall_status": overall,
            "queue": queue_summary,
            "federation": peer_summary,
            "routing": route_summary,
            "alerts": active_alerts,
            "recent_events": self.timeline(limit=50),
        }

    def diagnostic_bundle(
        self,
        dashboard: dict[str, Any],
        configuration: dict[str, Any] | None = None,
        now: int | None = None,
    ) -> dict[str, Any]:
        timestamp = int(time.time()) if now is None else int(now)
        return {
            "version": "1.0",
            "kind": "telegraph_diagnostic_bundle",
            "generated_at": timestamp,
            "office_id": self.office_id,
            "privacy": {
                "message_payloads_included": False,
                "private_keys_included": False,
                "credentials_included": False,
            },
            "dashboard": self._redact(dashboard),
            "configuration": self._redact(configuration or {}),
            "event_timeline": self.timeline(limit=500),
            "alerts": self.alerts(),
        }
