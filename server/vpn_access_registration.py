#!/usr/bin/env python3
"""Local policy-state store for Edge1 VPN access registration.

This module deliberately does not inspect or change WireGuard, nftables,
Unbound, Squid, routes, or interfaces.  It records the state that a future
enforcement adapter may consume after a separate production review.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


REGISTRATION_DAYS = 30
EXEMPTION_TYPES = {
    "registration",
    "cache",
    "proxy",
    "dns_filtering",
    "detailed_logging",
}
POLICY_FLAG_NAMES = {
    "dns_filtering_enabled",
    "proxy_required",
    "cache_eligible",
    "detailed_logging_permitted",
    "spamhaus_enabled",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return as_utc(value).isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return as_utc(parsed)


def fingerprint_peer_key(peer_public_key: str) -> str:
    value = peer_public_key.strip()
    if len(value) < 16 or len(value) > 4096:
        raise ValueError("invalid WireGuard public key")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_addresses(addresses: Iterable[str]) -> list[str]:
    if isinstance(addresses, (str, bytes)) or not isinstance(addresses, Iterable):
        raise ValueError("assigned addresses must be a list")
    normalized = []
    for address in addresses:
        text = str(address).strip()
        if not text:
            continue
        normalized.append(str(ipaddress.ip_interface(text)))
    return sorted(set(normalized))


class RegistrationStore:
    """SQLite-backed VPN registration and policy state."""

    def __init__(
        self,
        db_path: Path | str,
        registration_days: int = REGISTRATION_DAYS,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.db_path = Path(db_path)
        if registration_days < 1 or registration_days > 365:
            raise ValueError("registration_days must be between 1 and 365")
        self.registration_days = registration_days
        self.clock = clock
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS vpn_policy_versions (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    notice TEXT NOT NULL,
                    privacy_url TEXT NOT NULL DEFAULT '',
                    terms_url TEXT NOT NULL DEFAULT '',
                    effective_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS vpn_devices (
                    id TEXT PRIMARY KEY,
                    peer_key_sha256 TEXT NOT NULL UNIQUE,
                    assigned_addresses_json TEXT NOT NULL DEFAULT '[]',
                    display_name TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    quarantined_at TEXT,
                    quarantined_by TEXT NOT NULL DEFAULT '',
                    quarantine_reason TEXT NOT NULL DEFAULT '',
                    dns_filtering_enabled INTEGER NOT NULL DEFAULT 1 CHECK(dns_filtering_enabled IN (0, 1)),
                    proxy_required INTEGER NOT NULL DEFAULT 0 CHECK(proxy_required IN (0, 1)),
                    cache_eligible INTEGER NOT NULL DEFAULT 0 CHECK(cache_eligible IN (0, 1)),
                    detailed_logging_permitted INTEGER NOT NULL DEFAULT 0 CHECK(detailed_logging_permitted IN (0, 1)),
                    spamhaus_enabled INTEGER NOT NULL DEFAULT 1 CHECK(spamhaus_enabled IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vpn_acceptance_records (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES vpn_devices(id),
                    policy_id TEXT NOT NULL REFERENCES vpn_policy_versions(id),
                    accepted_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'portal'
                );

                CREATE INDEX IF NOT EXISTS vpn_acceptance_device_time
                    ON vpn_acceptance_records(device_id, accepted_at DESC);

                CREATE TABLE IF NOT EXISTS vpn_device_exemptions (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES vpn_devices(id),
                    exemption_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked_at TEXT,
                    revoked_by TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS vpn_exemption_device_type
                    ON vpn_device_exemptions(device_id, exemption_type, created_at DESC);

                CREATE TABLE IF NOT EXISTS vpn_registration_audit (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    device_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS vpn_audit_created
                    ON vpn_registration_audit(created_at DESC);
                """
            )

    def _now(self) -> datetime:
        return as_utc(self.clock())

    def _audit(
        self,
        conn: sqlite3.Connection,
        actor: str,
        event_type: str,
        device_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO vpn_registration_audit VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_id,
                iso(self._now()),
                actor.strip() or "system",
                event_type,
                device_id,
                json.dumps(details or {}, sort_keys=True, separators=(",", ":")),
            ),
        )
        return event_id

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def create_policy(
        self,
        version: str,
        title: str,
        notice: str,
        actor: str,
        privacy_url: str = "",
        terms_url: str = "",
        effective_at: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        version = version.strip()
        title = title.strip()
        notice = notice.strip()
        if not isinstance(activate, bool):
            raise ValueError("activate must be a boolean")
        if not version or len(version) > 80:
            raise ValueError("policy version is required and must be at most 80 characters")
        if not title or len(title) > 200:
            raise ValueError("policy title is required and must be at most 200 characters")
        if not notice or len(notice) > 12000:
            raise ValueError("policy notice is required and must be at most 12000 characters")
        now = iso(self._now())
        effective = iso(parse_time(effective_at)) if effective_at else now
        policy_id = str(uuid.uuid4())
        with self.transaction() as conn:
            if activate:
                conn.execute("UPDATE vpn_policy_versions SET active=0")
            conn.execute(
                """
                INSERT INTO vpn_policy_versions
                (id, version, title, notice, privacy_url, terms_url, effective_at, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    version,
                    title,
                    notice,
                    privacy_url.strip(),
                    terms_url.strip(),
                    effective,
                    now,
                    int(activate),
                ),
            )
            self._audit(conn, actor, "policy.created", details={"version": version, "active": activate})
            row = conn.execute("SELECT * FROM vpn_policy_versions WHERE id=?", (policy_id,)).fetchone()
        return self._row(row) or {}

    def list_policies(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM vpn_policy_versions
                ORDER BY active DESC, effective_at DESC, created_at DESC, rowid DESC
                """
            ).fetchall()
        return [self._row(row) or {} for row in rows]

    def upsert_device(
        self,
        peer_public_key: str,
        assigned_addresses: Iterable[str],
        actor: str,
        display_name: str = "",
        owner: str = "",
    ) -> dict[str, Any]:
        fingerprint = fingerprint_peer_key(peer_public_key)
        addresses = normalize_addresses(assigned_addresses)
        display_name = display_name.strip()
        owner = owner.strip()
        if len(display_name) > 200 or len(owner) > 200:
            raise ValueError("device name and owner must be at most 200 characters")
        now = iso(self._now())
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT id, display_name, owner
                FROM vpn_devices WHERE peer_key_sha256=?
                """,
                (fingerprint,),
            ).fetchone()
            if row is None:
                device_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO vpn_devices
                    (id, peer_key_sha256, assigned_addresses_json, display_name, owner,
                     first_seen_at, last_seen_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_id,
                        fingerprint,
                        json.dumps(addresses),
                        display_name,
                        owner,
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                event_type = "device.discovered"
            else:
                device_id = row["id"]
                display_name = display_name or row["display_name"]
                owner = owner or row["owner"]
                conn.execute(
                    """
                    UPDATE vpn_devices
                    SET assigned_addresses_json=?, display_name=?, owner=?,
                        last_seen_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (json.dumps(addresses), display_name, owner, now, now, device_id),
                )
                event_type = "device.seen"
            self._audit(
                conn,
                actor,
                event_type,
                device_id,
                {"assigned_addresses": addresses, "peer_key_sha256": fingerprint},
            )
        return self.get_device(device_id)

    def _active_exemptions(
        self, conn: sqlite3.Connection, device_id: str, at: datetime
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM vpn_device_exemptions
            WHERE device_id=? AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC
            """,
            (device_id, iso(at)),
        ).fetchall()
        return [self._row(row) or {} for row in rows]

    def _latest_acceptance(
        self, conn: sqlite3.Connection, device_id: str
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT a.*, p.version AS policy_version, p.title AS policy_title
            FROM vpn_acceptance_records a
            JOIN vpn_policy_versions p ON p.id=a.policy_id
            WHERE a.device_id=?
            ORDER BY a.accepted_at DESC, a.rowid DESC LIMIT 1
            """,
            (device_id,),
        ).fetchone()
        return self._row(row)

    def _enrich_device(
        self, conn: sqlite3.Connection, row: sqlite3.Row, at: datetime
    ) -> dict[str, Any]:
        device = self._row(row) or {}
        device["assigned_addresses"] = json.loads(device.pop("assigned_addresses_json"))
        exemptions = self._active_exemptions(conn, device["id"], at)
        acceptance = self._latest_acceptance(conn, device["id"])
        active_policy = conn.execute(
            "SELECT id, version FROM vpn_policy_versions WHERE active=1 ORDER BY effective_at DESC LIMIT 1"
        ).fetchone()
        types = sorted({item["exemption_type"] for item in exemptions})
        if device["quarantined_at"]:
            status = "quarantined"
        elif "registration" in types:
            status = "exempt"
        elif acceptance is None:
            status = "pending"
        elif active_policy is not None and acceptance["policy_id"] != active_policy["id"]:
            status = "policy_update_required"
        elif parse_time(acceptance["expires_at"]) <= at:
            status = "expired"
        else:
            status = "registered"
        for flag in POLICY_FLAG_NAMES:
            device[flag] = bool(device[flag])
        device["status"] = status
        device["active_exemptions"] = exemptions
        device["active_exemption_types"] = types
        device["latest_acceptance"] = acceptance
        return device

    def get_device(self, device_id: str) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM vpn_devices WHERE id=?", (device_id,)).fetchone()
            if row is None:
                raise KeyError("unknown device")
            return self._enrich_device(conn, row, self._now())

    def list_devices(self) -> list[dict[str, Any]]:
        at = self._now()
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM vpn_devices ORDER BY last_seen_at DESC, id"
            ).fetchall()
            return [self._enrich_device(conn, row, at) for row in rows]

    def accept_policy(
        self,
        device_id: str,
        actor: str,
        policy_version: str | None = None,
        source: str = "portal",
    ) -> dict[str, Any]:
        now = self._now()
        expires = now + timedelta(days=self.registration_days)
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM vpn_devices WHERE id=?", (device_id,)).fetchone() is None:
                raise KeyError("unknown device")
            if policy_version:
                policy = conn.execute(
                    "SELECT * FROM vpn_policy_versions WHERE version=? AND active=1",
                    (policy_version.strip(),),
                ).fetchone()
            else:
                policy = conn.execute(
                    "SELECT * FROM vpn_policy_versions WHERE active=1 ORDER BY effective_at DESC LIMIT 1"
                ).fetchone()
            if policy is None:
                raise ValueError("no matching active policy")
            acceptance_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO vpn_acceptance_records
                (id, device_id, policy_id, accepted_at, expires_at, actor, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    acceptance_id,
                    device_id,
                    policy["id"],
                    iso(now),
                    iso(expires),
                    actor,
                    source.strip() or "portal",
                ),
            )
            self._audit(
                conn,
                actor,
                "policy.accepted",
                device_id,
                {"policy_version": policy["version"], "expires_at": iso(expires), "source": source},
            )
            row = conn.execute(
                "SELECT * FROM vpn_acceptance_records WHERE id=?", (acceptance_id,)
            ).fetchone()
        return self._row(row) or {}

    def add_exemption(
        self,
        device_id: str,
        exemption_type: str,
        reason: str,
        approved_by: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        exemption_type = exemption_type.strip()
        reason = reason.strip()
        if exemption_type not in EXEMPTION_TYPES:
            raise ValueError("invalid exemption type")
        if not reason or len(reason) > 1000:
            raise ValueError("exemption reason is required and must be at most 1000 characters")
        expiry = iso(parse_time(expires_at)) if expires_at else None
        if expiry and parse_time(expiry) <= self._now():
            raise ValueError("exemption expiry must be in the future")
        exemption_id = str(uuid.uuid4())
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM vpn_devices WHERE id=?", (device_id,)).fetchone() is None:
                raise KeyError("unknown device")
            conn.execute(
                """
                INSERT INTO vpn_device_exemptions
                (id, device_id, exemption_type, reason, approved_by, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exemption_id,
                    device_id,
                    exemption_type,
                    reason,
                    approved_by,
                    iso(self._now()),
                    expiry,
                ),
            )
            self._audit(
                conn,
                approved_by,
                "exemption.added",
                device_id,
                {"exemption_type": exemption_type, "reason": reason, "expires_at": expiry},
            )
            row = conn.execute(
                "SELECT * FROM vpn_device_exemptions WHERE id=?", (exemption_id,)
            ).fetchone()
        return self._row(row) or {}

    def revoke_exemption(self, exemption_id: str, actor: str) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM vpn_device_exemptions WHERE id=?", (exemption_id,)
            ).fetchone()
            if row is None:
                raise KeyError("unknown exemption")
            if row["revoked_at"] is None:
                conn.execute(
                    "UPDATE vpn_device_exemptions SET revoked_at=?, revoked_by=? WHERE id=?",
                    (iso(self._now()), actor, exemption_id),
                )
                self._audit(
                    conn,
                    actor,
                    "exemption.revoked",
                    row["device_id"],
                    {"exemption_id": exemption_id, "exemption_type": row["exemption_type"]},
                )
            updated = conn.execute(
                "SELECT * FROM vpn_device_exemptions WHERE id=?", (exemption_id,)
            ).fetchone()
        return self._row(updated) or {}

    def set_quarantine(
        self, device_id: str, quarantined: bool, actor: str, reason: str = ""
    ) -> dict[str, Any]:
        if not isinstance(quarantined, bool):
            raise ValueError("quarantined must be a boolean")
        reason = reason.strip()
        if quarantined and not reason:
            raise ValueError("quarantine reason is required")
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM vpn_devices WHERE id=?", (device_id,)).fetchone() is None:
                raise KeyError("unknown device")
            conn.execute(
                """
                UPDATE vpn_devices
                SET quarantined_at=?, quarantined_by=?, quarantine_reason=?, updated_at=?
                WHERE id=?
                """,
                (
                    iso(self._now()) if quarantined else None,
                    actor if quarantined else "",
                    reason if quarantined else "",
                    iso(self._now()),
                    device_id,
                ),
            )
            self._audit(
                conn,
                actor,
                "device.quarantined" if quarantined else "device.quarantine_cleared",
                device_id,
                {"reason": reason} if quarantined else {},
            )
        return self.get_device(device_id)

    def set_policy_flags(
        self, device_id: str, flags: dict[str, bool], actor: str
    ) -> dict[str, Any]:
        if not flags or set(flags).difference(POLICY_FLAG_NAMES):
            raise ValueError("one or more policy flags are invalid")
        if not all(isinstance(value, bool) for value in flags.values()):
            raise ValueError("policy flag values must be booleans")
        assignments = ", ".join(f"{name}=?" for name in sorted(flags))
        values = [int(flags[name]) for name in sorted(flags)]
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM vpn_devices WHERE id=?", (device_id,)).fetchone() is None:
                raise KeyError("unknown device")
            conn.execute(
                f"UPDATE vpn_devices SET {assignments}, updated_at=? WHERE id=?",
                values + [iso(self._now()), device_id],
            )
            self._audit(conn, actor, "device.policy_flags_changed", device_id, {"flags": flags})
        return self.get_device(device_id)

    def audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM vpn_registration_audit ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        events = []
        for row in rows:
            event = self._row(row) or {}
            event["details"] = json.loads(event.pop("details_json"))
            events.append(event)
        return events

    def record_event(
        self,
        actor: str,
        event_type: str,
        device_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        with self.transaction() as conn:
            return self._audit(conn, actor, event_type, device_id, details)

    def summary(self) -> dict[str, Any]:
        devices = self.list_devices()
        counts = {
            status: 0
            for status in (
                "pending",
                "registered",
                "expired",
                "policy_update_required",
                "exempt",
                "quarantined",
            )
        }
        for device in devices:
            counts[device["status"]] += 1
        policies = self.list_policies()
        active = next((policy for policy in policies if policy["active"]), None)
        next_expiries = sorted(
            device["latest_acceptance"]["expires_at"]
            for device in devices
            if device["status"] == "registered" and device["latest_acceptance"]
        )
        return {
            "generated_at": iso(self._now()),
            "enforcement_active": False,
            "registration_period_days": self.registration_days,
            "device_counts": counts,
            "total_devices": len(devices),
            "active_policy": (
                {"version": active["version"], "title": active["title"], "effective_at": active["effective_at"]}
                if active
                else None
            ),
            "next_registration_expiry": next_expiries[0] if next_expiries else None,
        }
