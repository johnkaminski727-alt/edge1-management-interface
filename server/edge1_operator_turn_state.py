#!/usr/bin/env python3
"""Deterministic file-based turn-ownership state for Fen/Gus/Edge1 coordination.

Turn state is keyed by (task_id, conversation_id). Storage is a single JSON
file with atomic write-then-rename and a simple exclusive lock guarding the
read-modify-write critical section. This intentionally does not use a
database -- consistent with the existing audit.jsonl append pattern and the
bounded scope of this spike.

Atomicity note: the state-file commit and the audit-event append happen
sequentially while holding the lock, not as a single multi-file transaction.
If the process is killed between the two steps, the state file will reflect
the handoff but the audit record for it may be missing. This is a real,
documented limitation, not a hidden gap.

Task/conversation creation is out of scope for this spike. status() and
handoff() only operate on already-seeded state; seed() exists for that
purpose and for tests, and is not exposed as an MCP tool.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


class TurnStateError(Exception):
    """Base error for turn-state operations."""


class UnknownTurnError(TurnStateError):
    """Raised when a (task_id, conversation_id) pair has no existing turn state."""


class StaleEpochError(TurnStateError):
    """Raised when a handoff request's expected_epoch does not match current state."""


class UnauthorizedOwnerError(TurnStateError):
    """Raised when the requesting agent is not the current owner."""


def _key(task_id: str, conversation_id: str) -> str:
    return f"{task_id}::{conversation_id}"


@dataclass
class TurnRecord:
    task_id: str
    conversation_id: str
    owner_agent: str
    state: str
    turn_epoch: int
    started_at: float
    last_activity_at: float
    handed_off_at: float | None = None
    previous_owner: str | None = None
    handoff_reason: str | None = None
    handoff_evidence: str | None = None
    processed_idempotency_keys: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TurnRecord":
        return cls(**data)


class _FileLock:
    """Exclusive lock via atomic file creation. POSIX-only, matches this host."""

    def __init__(self, path: Path, timeout: float = 5.0, poll_interval: float = 0.02):
        self.path = path
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._fd: int | None = None

    def __enter__(self) -> "_FileLock":
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() > deadline:
                    raise TimeoutError(f"could not acquire lock {self.path}")
                time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


class TurnStateStore:
    def __init__(self, root: str, audit_writer: Callable[[str, dict], Any] | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "turn_state.json"
        self.lock_path = self.root / "turn_state.lock"
        self._audit_writer = audit_writer

    def _load_all(self) -> dict[str, TurnRecord]:
        if not self.state_path.exists():
            return {}
        with self.state_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {k: TurnRecord.from_dict(v) for k, v in raw.items()}

    def _save_all(self, records: dict[str, TurnRecord]) -> None:
        serializable = {k: v.to_dict() for k, v in records.items()}
        tmp_path = self.state_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(serializable, handle, sort_keys=True, indent=2)
        os.replace(tmp_path, self.state_path)

    def _lock(self) -> _FileLock:
        return _FileLock(self.lock_path)

    def seed(self, task_id: str, conversation_id: str, owner_agent: str, state: str = "ACTIVE") -> dict:
        with self._lock():
            records = self._load_all()
            key = _key(task_id, conversation_id)
            now = time.time()
            records[key] = TurnRecord(
                task_id=task_id,
                conversation_id=conversation_id,
                owner_agent=owner_agent,
                state=state,
                turn_epoch=0,
                started_at=now,
                last_activity_at=now,
            )
            self._save_all(records)
            return records[key].to_dict()

    def status(self, task_id: str, conversation_id: str) -> dict:
        records = self._load_all()
        record = records.get(_key(task_id, conversation_id))
        if record is None:
            raise UnknownTurnError(f"no turn state for {task_id}/{conversation_id}")
        result = record.to_dict()
        result.pop("processed_idempotency_keys", None)
        return result

    def handoff(
        self,
        task_id: str,
        conversation_id: str,
        requesting_agent: str,
        to_agent: str,
        expected_epoch: int,
        idempotency_key: str,
        reason: str | None = None,
        evidence: str | None = None,
    ) -> dict:
        with self._lock():
            records = self._load_all()
            key = _key(task_id, conversation_id)
            record = records.get(key)
            if record is None:
                raise UnknownTurnError(f"no turn state for {task_id}/{conversation_id}")

            # Idempotency check comes before the epoch check: a legitimate
            # replay of an already-applied request must succeed even though
            # the epoch has since advanced past what the caller originally
            # expected. Only a genuinely new request can be stale.
            prior = record.processed_idempotency_keys.get(idempotency_key)
            if prior is not None:
                return dict(prior)

            if record.owner_agent != requesting_agent:
                raise UnauthorizedOwnerError(
                    f"{requesting_agent} is not the current owner ({record.owner_agent})"
                )
            if record.turn_epoch != expected_epoch:
                raise StaleEpochError(
                    f"expected epoch {expected_epoch}, current epoch is {record.turn_epoch}"
                )

            now = time.time()
            record.previous_owner = record.owner_agent
            record.owner_agent = to_agent
            record.state = "HANDED_OFF"
            record.turn_epoch += 1
            record.last_activity_at = now
            record.handed_off_at = now
            record.handoff_reason = reason
            record.handoff_evidence = evidence

            result = record.to_dict()
            result.pop("processed_idempotency_keys", None)
            record.processed_idempotency_keys[idempotency_key] = result

            self._save_all(records)

            if self._audit_writer is not None:
                self._audit_writer(
                    str(self.root / "audit"),
                    {
                        "event": "turn.handed_off",
                        "task_id": task_id,
                        "conversation_id": conversation_id,
                        "from_agent": result["previous_owner"],
                        "to_agent": result["owner_agent"],
                        "turn_epoch": result["turn_epoch"],
                        "idempotency_key": idempotency_key,
                        "execution_id": uuid.uuid4().hex[:16],
                    },
                )

            return result
