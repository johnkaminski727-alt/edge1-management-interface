#!/usr/bin/env python3
"""Signed incremental directory synchronization for Telegraph federation.

The journal is intentionally transport-neutral. It provides monotonic sequence
numbers, bounded delta generation, checkpoints, and tombstones while preserving
local trust decisions at the receiving office.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from reference.telegraph_crypto import verify_document, verify_identity
from reference.telegraph_office_service import TelegraphOfficeState


@dataclass
class DirectoryChange:
    sequence: int
    operation: str
    office_id: str
    changed_at: int
    record: dict[str, Any] | None = None
    reason: str | None = None

    def document(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "sequence": self.sequence,
            "operation": self.operation,
            "office_id": self.office_id,
            "changed_at": self.changed_at,
        }
        if self.record is not None:
            value["record"] = self.record
        if self.reason is not None:
            value["reason"] = self.reason
        return value


@dataclass
class IncrementalDirectoryJournal:
    state: TelegraphOfficeState
    max_changes: int = 1000
    sequence: int = 0
    changes: list[DirectoryChange] = field(default_factory=list)
    peer_checkpoints: dict[str, int] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        if self.max_changes < 1:
            raise ValueError("max_changes must be positive")

    def _append(
        self,
        operation: str,
        office_id: str,
        record: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> DirectoryChange:
        with self.lock:
            self.sequence += 1
            change = DirectoryChange(
                sequence=self.sequence,
                operation=operation,
                office_id=office_id,
                changed_at=int(time.time()),
                record=record,
                reason=reason,
            )
            self.changes.append(change)
            if len(self.changes) > self.max_changes:
                self.changes = self.changes[-self.max_changes :]
            return change

    def record_upsert(self, office_id: str) -> DirectoryChange:
        with self.state.lock:
            record = self.state.peers.get(office_id)
            if record is None:
                raise KeyError(office_id)
            snapshot = dict(record)
        return self._append("upsert", office_id, record=snapshot)

    def record_tombstone(self, office_id: str, reason: str = "withdrawn") -> DirectoryChange:
        if not reason:
            raise ValueError("reason is required")
        return self._append("tombstone", office_id, reason=reason)

    def oldest_available_sequence(self) -> int:
        with self.lock:
            return self.changes[0].sequence if self.changes else self.sequence + 1

    def manifest_since(self, since: int, limit: int = 250) -> tuple[HTTPStatus, dict[str, Any]]:
        if since < 0 or limit < 1 or limit > self.max_changes:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_delta_request"}
        with self.lock:
            oldest = self.oldest_available_sequence()
            if self.changes and since < oldest - 1:
                return HTTPStatus.GONE, {
                    "error": "checkpoint_expired",
                    "oldest_available_sequence": oldest,
                    "current_sequence": self.sequence,
                    "full_sync_required": True,
                }
            selected = [change.document() for change in self.changes if change.sequence > since][:limit]
            to_sequence = selected[-1]["sequence"] if selected else since
            more = any(change.sequence > to_sequence for change in self.changes)
            document = {
                "version": "1.0",
                "kind": "directory_delta",
                "office_id": self.state.office.office_id,
                "generated_at": int(time.time()),
                "from_sequence": since,
                "to_sequence": to_sequence,
                "current_sequence": self.sequence,
                "changes": selected,
                "count": len(selected),
                "more": more,
            }
            document["signature"] = self.state.office.sign(document)
            return HTTPStatus.OK, document

    def checkpoint(self, peer_office_id: str) -> int:
        return self.peer_checkpoints.get(peer_office_id, 0)

    def apply_manifest(self, document: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
        source_office = document.get("office_id")
        changes = document.get("changes")
        from_sequence = document.get("from_sequence")
        to_sequence = document.get("to_sequence")
        if (
            document.get("kind") != "directory_delta"
            or not isinstance(source_office, str)
            or not isinstance(changes, list)
            or not isinstance(from_sequence, int)
            or not isinstance(to_sequence, int)
        ):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_delta_manifest"}
        if len(changes) > self.max_changes or to_sequence < from_sequence:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_delta_range"}

        with self.state.lock:
            source = self.state.peers.get(source_office)
        if source is None:
            return HTTPStatus.FORBIDDEN, {"error": "unknown_directory_source"}
        if source.get("trust_status") == "restricted":
            return HTTPStatus.FORBIDDEN, {"error": "restricted_directory_source"}
        if not verify_document(document, source["identity"]):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid_delta_signature"}

        expected = self.checkpoint(source_office)
        if from_sequence != expected:
            return HTTPStatus.CONFLICT, {
                "error": "checkpoint_mismatch",
                "expected_from_sequence": expected,
                "received_from_sequence": from_sequence,
            }

        applied = skipped = rejected = tombstoned = 0
        last_sequence = from_sequence
        with self.state.lock:
            for change in changes:
                if not isinstance(change, dict):
                    rejected += 1
                    continue
                sequence = change.get("sequence")
                office_id = change.get("office_id")
                operation = change.get("operation")
                if not isinstance(sequence, int) or sequence <= last_sequence or not isinstance(office_id, str):
                    rejected += 1
                    continue
                last_sequence = sequence
                if office_id == self.state.office.office_id:
                    skipped += 1
                    continue
                existing = self.state.peers.get(office_id)
                if operation == "upsert":
                    record = change.get("record")
                    identity = record.get("identity") if isinstance(record, dict) else None
                    if not isinstance(identity, dict) or identity.get("office_id") != office_id or not verify_identity(identity):
                        rejected += 1
                        continue
                    remote_updated = int(record.get("updated_at", 0))
                    if existing is not None and remote_updated <= int(existing.get("updated_at", 0)):
                        skipped += 1
                        continue
                    trust_status = existing["trust_status"] if existing is not None else "observed"
                    imported = {
                        "office_id": office_id,
                        "identity": identity,
                        "trust_status": trust_status,
                        "updated_at": remote_updated,
                        "identity_verified": True,
                        "directory_source": source_office,
                        "directory_sequence": sequence,
                    }
                    self.state._save_peer(imported)
                    applied += 1
                elif operation == "tombstone":
                    if existing is None:
                        skipped += 1
                        continue
                    retired = dict(existing)
                    retired["federation_status"] = "withdrawn"
                    retired["withdrawn_at"] = int(change.get("changed_at", time.time()))
                    retired["withdrawal_reason"] = str(change.get("reason", "withdrawn"))
                    retired["directory_source"] = source_office
                    retired["directory_sequence"] = sequence
                    self.state._save_peer(retired)
                    tombstoned += 1
                else:
                    rejected += 1

        if changes and last_sequence != to_sequence:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "delta_sequence_mismatch"}
        self.peer_checkpoints[source_office] = to_sequence
        return HTTPStatus.ACCEPTED, {
            "status": "directory_delta_applied",
            "source_office": source_office,
            "checkpoint": to_sequence,
            "applied": applied,
            "tombstoned": tombstoned,
            "skipped": skipped,
            "rejected": rejected,
            "more": bool(document.get("more")),
            "signature_verified": True,
        }
