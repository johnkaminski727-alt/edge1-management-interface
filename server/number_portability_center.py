#!/usr/bin/env python3
"""Durable fail-closed number portability workflow for WW.CX.

The service models and validates port requests, evidence, carrier milestones, and
readiness. It deliberately does not submit ports, alter routing, activate numbers,
or contact carriers. Those actions belong to separately commissioned control planes.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
PORT_DIRECTIONS = {"inbound", "outbound"}
PORT_STATES = {
    "draft", "collecting_documents", "ready_for_review", "awaiting_approval",
    "approved_for_submission", "submitted", "carrier_review", "foc_received",
    "cutover_scheduled", "completed", "rejected", "cancelled",
}
DOCUMENT_TYPES = {"loa", "csr", "bill", "account_record", "carrier_response", "foc", "other"}
RESTRICTED_STATES = {"submitted", "carrier_review", "foc_received", "cutover_scheduled", "completed"}
DIGITS = re.compile(r"\D+")
SAFE_REF = re.compile(r"^[A-Za-z0-9._:/+-]{1,512}$")


class PortabilityError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_nanp(value: str) -> str:
    digits = DIGITS.sub("", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        raise PortabilityError("invalid NANP telephone number")
    return digits


def _clean(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PortabilityError(f"{field} must be a string")
    value = value.strip()
    if not value or "\x00" in value or len(value.encode("utf-8")) > maximum:
        raise PortabilityError(f"{field} is empty or out of bounds")
    return value


def _optional(value: Any, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _clean(value, field, maximum)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class PortabilityStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.path.parent, 0o750)
            except OSError:
                pass
        self._initialize()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self.connect() as conn:
            if str(self.path) != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS port_cases(
                id TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                state TEXT NOT NULL,
                customer_ref TEXT NOT NULL,
                losing_carrier TEXT,
                gaining_carrier TEXT,
                account_ref TEXT,
                desired_due_date TEXT,
                foc_at_utc TEXT,
                scheduled_cutover_at_utc TEXT,
                external_reference TEXT,
                submission_authorized INTEGER NOT NULL DEFAULT 0,
                cutover_authorized INTEGER NOT NULL DEFAULT 0,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS port_numbers(
                case_id TEXT NOT NULL REFERENCES port_cases(id) ON DELETE CASCADE,
                number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(case_id,number)
            );
            CREATE TABLE IF NOT EXISTS port_documents(
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES port_cases(id) ON DELETE CASCADE,
                document_type TEXT NOT NULL,
                reference TEXT NOT NULL,
                sha256 TEXT,
                received_at_utc TEXT NOT NULL,
                UNIQUE(case_id,document_type,reference)
            );
            CREATE TABLE IF NOT EXISTS port_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES port_cases(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_port_cases_state ON port_cases(state,updated_at_utc);
            CREATE INDEX IF NOT EXISTS idx_port_events_case ON port_events(case_id,id);
            """)
        if str(self.path) != ":memory:" and self.path.exists():
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def _event(self, case_id: str, event_type: str, actor: str, detail: dict[str, Any]) -> None:
        now = utc_now()
        actor = _clean(actor, "actor", 128)
        event_type = _clean(event_type, "event_type", 128)
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT event_hash FROM port_events WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
            previous = str(row["event_hash"]) if row else "0" * 64
            record = {"case_id": case_id, "event_type": event_type, "actor": actor, "detail": detail, "created_at_utc": now, "previous_hash": previous}
            digest = hashlib.sha256(_canonical(record).encode("ascii")).hexdigest()
            conn.execute(
                "INSERT INTO port_events(case_id,event_type,actor,detail_json,created_at_utc,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
                (case_id, event_type, actor, _canonical(detail), now, previous, digest),
            )

    def create_case(self, *, direction: str, customer_ref: str, numbers: list[str], losing_carrier: str | None = None, gaining_carrier: str | None = None, account_ref: str | None = None, desired_due_date: str | None = None, actor: str = "operator") -> dict[str, Any]:
        if direction not in PORT_DIRECTIONS:
            raise PortabilityError("invalid port direction")
        if not isinstance(numbers, list) or not 1 <= len(numbers) <= 500:
            raise PortabilityError("port case must contain 1-500 numbers")
        normalized = sorted(set(normalize_nanp(number) for number in numbers))
        customer_ref = _clean(customer_ref, "customer_ref", 256)
        losing_carrier = _optional(losing_carrier, "losing_carrier", 256)
        gaining_carrier = _optional(gaining_carrier, "gaining_carrier", 256)
        account_ref = _optional(account_ref, "account_ref", 256)
        desired_due_date = _optional(desired_due_date, "desired_due_date", 32)
        case_id = "PORT-" + uuid.uuid4().hex[:16].upper()
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO port_cases(id,direction,state,customer_ref,losing_carrier,gaining_carrier,account_ref,desired_due_date,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (case_id, direction, "draft", customer_ref, losing_carrier, gaining_carrier, account_ref, desired_due_date, now, now),
            )
            conn.executemany("INSERT INTO port_numbers(case_id,number) VALUES(?,?)", [(case_id, number) for number in normalized])
        self._event(case_id, "case.created", actor, {"direction": direction, "number_count": len(normalized)})
        return self.get_case(case_id)

    def add_document(self, case_id: str, *, document_type: str, reference: str, sha256: str | None = None, actor: str = "operator") -> dict[str, Any]:
        self.get_case(case_id)
        if document_type not in DOCUMENT_TYPES:
            raise PortabilityError("invalid document type")
        reference = _clean(reference, "reference", 512)
        if not SAFE_REF.fullmatch(reference):
            raise PortabilityError("document reference contains unsupported characters")
        if sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise PortabilityError("sha256 must be lowercase hexadecimal")
        doc_id = "PDOC-" + uuid.uuid4().hex[:16].upper()
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute("INSERT INTO port_documents(id,case_id,document_type,reference,sha256,received_at_utc) VALUES(?,?,?,?,?,?)", (doc_id, case_id, document_type, reference, sha256, now))
            conn.execute("UPDATE port_cases SET updated_at_utc=? WHERE id=?", (now, case_id))
        self._event(case_id, "document.added", actor, {"document_id": doc_id, "document_type": document_type, "sha256_present": sha256 is not None})
        return {"id": doc_id, "case_id": case_id, "document_type": document_type, "reference": reference, "sha256": sha256, "received_at_utc": now}

    def readiness(self, case_id: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        document_types = {row["document_type"] for row in case["documents"]}
        required = {"loa", "csr"} if case["direction"] == "inbound" else {"csr"}
        missing = sorted(required - document_types)
        checks = {
            "numbers_present": bool(case["numbers"]),
            "customer_reference_present": bool(case["customer_ref"]),
            "carrier_context_present": bool(case["losing_carrier"] or case["gaining_carrier"]),
            "required_documents_present": not missing,
            "submission_not_yet_authorized": not bool(case["submission_authorized"]),
            "cutover_not_yet_authorized": not bool(case["cutover_authorized"]),
        }
        return {"case_id": case_id, "ready_for_internal_review": all([checks["numbers_present"], checks["customer_reference_present"], checks["carrier_context_present"], checks["required_documents_present"]]), "missing_documents": missing, "checks": checks}

    def transition(self, case_id: str, state: str, *, actor: str = "operator", external_reference: str | None = None, foc_at_utc: str | None = None, scheduled_cutover_at_utc: str | None = None) -> dict[str, Any]:
        current = self.get_case(case_id)
        if state not in PORT_STATES:
            raise PortabilityError("invalid port state")
        if state in RESTRICTED_STATES:
            raise PortabilityError("live carrier submission/cutover states require the separate commissioned porting control plane")
        allowed = {
            "draft": {"collecting_documents", "cancelled"},
            "collecting_documents": {"ready_for_review", "cancelled"},
            "ready_for_review": {"awaiting_approval", "collecting_documents", "cancelled"},
            "awaiting_approval": {"approved_for_submission", "collecting_documents", "cancelled"},
            "approved_for_submission": {"cancelled"},
            "rejected": {"collecting_documents", "cancelled"},
            "cancelled": set(),
        }
        if state not in allowed.get(current["state"], set()):
            raise PortabilityError(f"invalid transition {current['state']} -> {state}")
        if state in {"ready_for_review", "awaiting_approval", "approved_for_submission"} and not self.readiness(case_id)["ready_for_internal_review"]:
            raise PortabilityError("port case is not ready for internal review")
        external_reference = _optional(external_reference, "external_reference", 256)
        foc_at_utc = _optional(foc_at_utc, "foc_at_utc", 64)
        scheduled_cutover_at_utc = _optional(scheduled_cutover_at_utc, "scheduled_cutover_at_utc", 64)
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute("UPDATE port_cases SET state=?,external_reference=COALESCE(?,external_reference),foc_at_utc=COALESCE(?,foc_at_utc),scheduled_cutover_at_utc=COALESCE(?,scheduled_cutover_at_utc),updated_at_utc=? WHERE id=?", (state, external_reference, foc_at_utc, scheduled_cutover_at_utc, now, case_id))
        self._event(case_id, "case.transition", actor, {"from": current["state"], "to": state})
        return self.get_case(case_id)

    def get_case(self, case_id: str) -> dict[str, Any]:
        case_id = _clean(case_id, "case_id", 64)
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM port_cases WHERE id=?", (case_id,)).fetchone()
            if not row:
                raise PortabilityError("port case not found")
            numbers = conn.execute("SELECT number,status FROM port_numbers WHERE case_id=? ORDER BY number", (case_id,)).fetchall()
            docs = conn.execute("SELECT id,document_type,reference,sha256,received_at_utc FROM port_documents WHERE case_id=? ORDER BY received_at_utc,id", (case_id,)).fetchall()
        out = dict(row)
        out["submission_authorized"] = bool(out["submission_authorized"])
        out["cutover_authorized"] = bool(out["cutover_authorized"])
        out["numbers"] = [dict(item) for item in numbers]
        out["documents"] = [dict(item) for item in docs]
        return out

    def list_cases(self, *, state: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if state is not None and state not in PORT_STATES:
            raise PortabilityError("invalid state filter")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
            raise PortabilityError("invalid limit")
        sql = "SELECT id,direction,state,customer_ref,losing_carrier,gaining_carrier,desired_due_date,foc_at_utc,scheduled_cutover_at_utc,external_reference,submission_authorized,cutover_authorized,created_at_utc,updated_at_utc FROM port_cases"
        params: list[Any] = []
        if state:
            sql += " WHERE state=?"
            params.append(state)
        sql += " ORDER BY updated_at_utc DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["submission_authorized"] = bool(item["submission_authorized"])
            item["cutover_authorized"] = bool(item["cutover_authorized"])
            output.append(item)
        return output
