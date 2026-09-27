#!/usr/bin/env python3
"""G2 local-only SQLite candidate store. Demo display preferences; NEVER applies settings.

All writes use BEGIN IMMEDIATE and require an exact candidate revision, so two
browser tabs cannot silently overwrite one another. This module does not read
or change production configurations and has no command execution capability.
"""
from __future__ import annotations
import copy
from contextlib import contextmanager
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edge1_candidate_workspace import (CandidateError, Workspace, canonical,
                                        initial_settings, revision, validate)

SCHEMA = "edge1-candidate-workspace-g2"
MAX_DB_BYTES = 8 * 1024 * 1024


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ConflictError(CandidateError):
    pass


class CandidateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise CandidateError("Refusing symlinked candidate database")
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            raise CandidateError("Candidate data directory missing or symlinked")
        self._setup()

    @contextmanager
    def _connect(self):
        if self.path.is_symlink():
            raise CandidateError("Refusing symlinked candidate database")
        if self.path.exists() and (not self.path.is_file() or self.path.stat().st_size > MAX_DB_BYTES):
            raise CandidateError("Candidate data storage is invalid or oversized")
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _setup(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS workspace (
               id INTEGER PRIMARY KEY CHECK(id=1), running TEXT NOT NULL,
               candidate TEXT NOT NULL, candidate_revision TEXT NOT NULL,
               sequence INTEGER NOT NULL DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit (
               sequence INTEGER PRIMARY KEY AUTOINCREMENT, observed_utc TEXT NOT NULL,
               action TEXT NOT NULL, path TEXT, old_revision TEXT NOT NULL,
               new_revision TEXT NOT NULL)""")
            if db.execute("SELECT id FROM workspace WHERE id=1").fetchone() is None:
                running = validate(initial_settings())
                db.execute("INSERT INTO workspace (id,running,candidate,candidate_revision) VALUES (1,?,?,?)",
                           (canonical(running), canonical(running), revision(running)))
            db.commit()
        os.chmod(self.path, 0o600)

    @staticmethod
    def _state(row: sqlite3.Row) -> dict:
        running = validate(json.loads(row["running"]))
        candidate = validate(json.loads(row["candidate"]))
        if revision(candidate) != row["candidate_revision"]:
            raise CandidateError("Stored candidate revision mismatch")
        w = Workspace(running)
        # Rehydrate the separately validated stored overlay for read-only diff.
        w._candidate = copy.deepcopy(candidate)
        preview = w.preview()
        preview["schema"] = SCHEMA
        preview["running"] = running
        preview["candidate"] = candidate
        preview["sequence"] = row["sequence"]
        preview["source"] = "local demonstration settings, not live Edge1 configuration"
        preview["persistence"] = "local candidate only"
        return preview

    def read(self) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workspace WHERE id=1").fetchone()
            if row is None:
                raise CandidateError("Candidate workspace missing")
            return self._state(row)

    def _change(self, action: str, expected_candidate_revision: str,
                section: str | None = None, field: str | None = None,
                value: Any = None) -> dict:
        if not isinstance(expected_candidate_revision, str) or len(expected_candidate_revision) != 64:
            raise CandidateError("Exact candidate revision is required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM workspace WHERE id=1").fetchone()
            previous = self._state(row)
            if previous["candidate_revision"] != expected_candidate_revision:
                raise ConflictError("Another session changed the candidate; refresh before editing")
            if action == "propose":
                # Validate before changing persistent state or audit rows.
                if section not in ("dashboard", "inventory", "alerts"):
                    raise CandidateError("Unknown display settings section")
                if not isinstance(field, str):
                    raise CandidateError("Invalid setting name")
                w = Workspace(previous["running"])
                w._candidate = copy.deepcopy(previous["candidate"])
                w.propose(section, field, value, expected_revision=w.base_revision)
                candidate = w.candidate
                path = section + "." + field
            elif action == "discard":
                candidate = copy.deepcopy(previous["running"])
                path = None
            else:
                raise CandidateError("Unsupported candidate operation")
            new_revision = revision(candidate)
            db.execute("UPDATE workspace SET candidate=?, candidate_revision=?, sequence=sequence+1 WHERE id=1",
                       (canonical(candidate), new_revision))
            db.execute("INSERT INTO audit (observed_utc,action,path,old_revision,new_revision) VALUES (?,?,?,?,?)",
                       (utcnow(), action, path, previous["candidate_revision"], new_revision))
            updated = db.execute("SELECT * FROM workspace WHERE id=1").fetchone()
            db.commit()
            return self._state(updated)

    def propose(self, section: str, field: str, value: Any, *, expected_candidate_revision: str) -> dict:
        return self._change("propose", expected_candidate_revision, section, field, value)

    def discard(self, *, expected_candidate_revision: str) -> dict:
        return self._change("discard", expected_candidate_revision)

    def audit(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise CandidateError("Invalid audit limit")
        with self._connect() as db:
            rows = db.execute("SELECT sequence,observed_utc,action,path,old_revision,new_revision FROM audit ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]
