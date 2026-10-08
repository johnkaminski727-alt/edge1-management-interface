#!/usr/bin/env python3
"""Durable workflow and fail-closed authority core for the WW.CX Ava office manager.

This module deliberately performs no provider or PBX side effects. It stores work,
standing instructions, linked cross-channel artifacts and proposed actions. External
execution belongs to separately commissioned adapters/control planes.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 2
WORK_STATES = {"new", "working", "waiting_external", "needs_owner", "scheduled", "completed", "cancelled"}
WORK_PRIORITIES = {"low", "normal", "high", "urgent"}
INSTRUCTION_EFFECTS = {"deny", "require_confirmation", "prefer"}
AUTHORITY_ORDER = {"observe": 1, "prepare": 2, "routine": 3, "conditional": 4, "restricted": 5}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{7,127}$")
CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
FORBIDDEN_KEYS = {
    "password", "passwd", "secret", "api_key", "apikey", "token", "authorization",
    "private_key", "credential", "credentials",
}

DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    "autonomy_level": "routine",
    "execution_enabled": False,
    "capability_rules": [
        {"prefix": "calendar.read", "authority": "observe"},
        {"prefix": "calendar.event.prepare", "authority": "prepare"},
        {"prefix": "calendar.event.create", "authority": "routine"},
        {"prefix": "calendar.event.update", "authority": "routine"},
        {"prefix": "calendar.event.cancel", "authority": "conditional"},
        {"prefix": "communication.read", "authority": "observe"},
        {"prefix": "communication.draft", "authority": "prepare"},
        {"prefix": "communication.send", "authority": "routine"},
        {"prefix": "telephony.read", "authority": "observe"},
        {"prefix": "telephony.receptionist", "authority": "routine"},
        {"prefix": "telephony.transfer", "authority": "routine"},
        {"prefix": "telephony.originate", "authority": "conditional"},
        {"prefix": "purchasing.quote", "authority": "prepare"},
        {"prefix": "purchasing.commit", "authority": "conditional"},
        {"prefix": "travel.research", "authority": "prepare"},
        {"prefix": "travel.book", "authority": "conditional"},
        {"prefix": "financial", "authority": "restricted"},
        {"prefix": "legal", "authority": "restricted"},
        {"prefix": "contract", "authority": "restricted"},
        {"prefix": "credential", "authority": "restricted"},
        {"prefix": "destructive", "authority": "restricted"},
        {"prefix": "emergency", "authority": "restricted"},
    ],
    "always_confirm_prefixes": [
        "calendar.event.cancel", "telephony.originate", "purchasing.commit", "travel.book",
    ],
    "blocked_prefixes": [
        "financial", "legal", "contract", "credential", "destructive", "emergency",
        "telephony.route.change", "telephony.number.port", "telephony.stir_shaken.sign",
    ],
}


class OfficeManagerError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorityDecision:
    capability: str
    authority: str
    authorization: str
    executable: bool
    reason: str

    def public(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "authority": self.authority,
            "authorization": self.authorization,
            "executable": self.executable,
            "reason": self.reason,
        }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _clean_text(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise OfficeManagerError(f"{field} must be a string")
    clean = value.strip()
    if not clean or "\x00" in clean or len(clean.encode("utf-8")) > maximum:
        raise OfficeManagerError(f"{field} is empty or out of bounds")
    return clean


def _optional_text(value: Any, field: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _clean_text(value, field, maximum=maximum)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _prefix_match(capability: str, prefix: str) -> bool:
    return capability == prefix or capability.startswith(prefix + ".")


def _reject_sensitive(value: Any, path: str = "parameters") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).strip().lower()
            if lowered in FORBIDDEN_KEYS or lowered.endswith("_password") or lowered.endswith("_secret"):
                raise OfficeManagerError(f"sensitive field is not eligible for office-manager storage: {path}.{lowered}")
            _reject_sensitive(child, f"{path}.{lowered}")
    elif isinstance(value, list):
        if len(value) > 100:
            raise OfficeManagerError(f"{path} contains too many items")
        for index, child in enumerate(value):
            _reject_sensitive(child, f"{path}[{index}]")
    elif isinstance(value, str) and len(value.encode("utf-8")) > 16000:
        raise OfficeManagerError(f"{path} contains an oversized string")


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict) or policy.get("version") != 1:
        raise OfficeManagerError("office-manager policy version must be 1")
    autonomy = policy.get("autonomy_level")
    if autonomy not in AUTHORITY_ORDER:
        raise OfficeManagerError("office-manager autonomy_level is invalid")
    if not isinstance(policy.get("execution_enabled"), bool):
        raise OfficeManagerError("office-manager execution_enabled must be boolean")
    rules = policy.get("capability_rules")
    if not isinstance(rules, list) or not rules:
        raise OfficeManagerError("office-manager capability_rules must be a non-empty list")
    normalized: list[dict[str, str]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise OfficeManagerError("office-manager capability rule must be an object")
        prefix = rule.get("prefix")
        authority = rule.get("authority")
        if not isinstance(prefix, str) or not CAPABILITY_RE.fullmatch(prefix):
            raise OfficeManagerError("office-manager capability rule prefix is invalid")
        if authority not in AUTHORITY_ORDER:
            raise OfficeManagerError("office-manager capability rule authority is invalid")
        normalized.append({"prefix": prefix, "authority": authority})
    for name in ("always_confirm_prefixes", "blocked_prefixes"):
        values = policy.get(name, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not CAPABILITY_RE.fullmatch(v) for v in values):
            raise OfficeManagerError(f"office-manager {name} is invalid")
    return {
        "version": 1,
        "autonomy_level": autonomy,
        "execution_enabled": bool(policy["execution_enabled"]),
        "capability_rules": normalized,
        "always_confirm_prefixes": list(policy.get("always_confirm_prefixes", [])),
        "blocked_prefixes": list(policy.get("blocked_prefixes", [])),
    }


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        return validate_policy(dict(DEFAULT_POLICY))
    return validate_policy(json.loads(Path(path).read_text(encoding="utf-8")))


def _required_authority(capability: str, policy: dict[str, Any]) -> tuple[str, bool]:
    matches = [rule for rule in policy["capability_rules"] if _prefix_match(capability, rule["prefix"])]
    if not matches:
        return "restricted", False
    matches.sort(key=lambda rule: len(rule["prefix"]), reverse=True)
    return str(matches[0]["authority"]), True


class OfficeManagerStore:
    def __init__(self, path: str | Path, *, policy: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.policy = validate_policy(dict(DEFAULT_POLICY) if policy is None else policy)
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
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
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
                # The companion read API is intentionally sandboxed against filesystem
                # writes. WAL mode requires writable -wal/-shm sidecars for real reads,
                # so use the rollback journal for these low-volume administrative stores.
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS work_items(
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    desired_outcome TEXT NOT NULL,
                    state TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    source_ref TEXT,
                    owner TEXT NOT NULL,
                    due_at_utc TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_work_items_state_updated ON work_items(state,updated_at_utc);
                CREATE TABLE IF NOT EXISTS artifacts(
                    id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    ref TEXT NOT NULL,
                    label TEXT,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(work_item_id,kind,ref)
                );
                CREATE TABLE IF NOT EXISTS standing_instructions(
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_standing_instructions_domain ON standing_instructions(domain,enabled,priority);
                CREATE TABLE IF NOT EXISTS action_proposals(
                    id TEXT PRIMARY KEY,
                    work_item_id TEXT REFERENCES work_items(id) ON DELETE SET NULL,
                    capability TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    authority_class TEXT NOT NULL,
                    authorization TEXT NOT NULL,
                    executable INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_action_proposals_status ON action_proposals(status,updated_at_utc);
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS executive_team_members(
                    member_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    role TEXT NOT NULL,
                    service_unit TEXT,
                    timer_unit TEXT,
                    action_level TEXT NOT NULL,
                    authority_ceiling TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    health_state TEXT NOT NULL DEFAULT 'unknown',
                    last_checkin_at_utc TEXT,
                    last_report_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_team_department_health ON executive_team_members(department,health_state,active);
                CREATE TABLE IF NOT EXISTS executive_assignments(
                    id TEXT PRIMARY KEY,
                    work_item_id TEXT REFERENCES work_items(id) ON DELETE SET NULL,
                    member_id TEXT NOT NULL REFERENCES executive_team_members(member_id) ON DELETE RESTRICT,
                    objective TEXT NOT NULL,
                    state TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL DEFAULT '[]',
                    requested_by TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_assignments_member_state ON executive_assignments(member_id,state,updated_at_utc);
                CREATE TABLE IF NOT EXISTS executive_reports(
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL REFERENCES executive_team_members(member_id) ON DELETE RESTRICT,
                    assignment_id TEXT REFERENCES executive_assignments(id) ON DELETE SET NULL,
                    report_type TEXT NOT NULL,
                    health_state TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    needs_attention INTEGER NOT NULL DEFAULT 0,
                    severity TEXT NOT NULL DEFAULT 'info',
                    source_ref TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(member_id,source_ref)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_reports_attention ON executive_reports(needs_attention,severity,created_at_utc);
                CREATE TABLE IF NOT EXISTS executive_workflow_runs(
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_ref TEXT NOT NULL,
                    state TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    work_item_id TEXT REFERENCES work_items(id) ON DELETE SET NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT,
                    error_summary TEXT,
                    UNIQUE(workflow_id,trigger_ref)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_workflow_runs_state ON executive_workflow_runs(state,updated_at_utc);
                CREATE TABLE IF NOT EXISTS executive_workflow_steps(
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES executive_workflow_runs(id) ON DELETE CASCADE,
                    step_key TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    member_id TEXT REFERENCES executive_team_members(member_id) ON DELETE SET NULL,
                    state TEXT NOT NULL,
                    depends_on_json TEXT NOT NULL DEFAULT '[]',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    started_at_utc TEXT,
                    finished_at_utc TEXT,
                    result_json TEXT,
                    error_summary TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    UNIQUE(run_id,step_key)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_workflow_steps_run_state ON executive_workflow_steps(run_id,state,step_key);
                CREATE TABLE IF NOT EXISTS executive_reviews(
                    id TEXT PRIMARY KEY, source_system TEXT NOT NULL, source_ref TEXT NOT NULL, category TEXT NOT NULL,
                    title TEXT NOT NULL, summary TEXT NOT NULL, severity TEXT NOT NULL, state TEXT NOT NULL,
                    owner_required INTEGER NOT NULL DEFAULT 1, recommended_action TEXT, evidence_json TEXT NOT NULL DEFAULT '[]',
                    first_seen_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL, resolved_at_utc TEXT, UNIQUE(source_system,source_ref)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_reviews_state ON executive_reviews(state,owner_required,severity,updated_at_utc);
                CREATE TABLE IF NOT EXISTS executive_briefings(
                    id TEXT PRIMARY KEY, briefing_type TEXT NOT NULL, period_start_utc TEXT NOT NULL, period_end_utc TEXT NOT NULL,
                    title TEXT NOT NULL, summary_json TEXT NOT NULL, owner_action_count INTEGER NOT NULL DEFAULT 0, created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_team_run_observations(
                    member_id TEXT NOT NULL REFERENCES executive_team_members(member_id) ON DELETE CASCADE,
                    run_ref TEXT NOT NULL, result TEXT NOT NULL, observed_at_utc TEXT NOT NULL,
                    PRIMARY KEY(member_id,run_ref)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_team_run_result ON executive_team_run_observations(member_id,result,observed_at_utc);
                CREATE TABLE IF NOT EXISTS executive_team_metrics(
                    member_id TEXT PRIMARY KEY REFERENCES executive_team_members(member_id) ON DELETE CASCADE, maturity_level TEXT NOT NULL,
                    run_count INTEGER NOT NULL DEFAULT 0, success_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0, success_rate REAL, last_success_at_utc TEXT, last_failure_at_utc TEXT,
                    recommendation TEXT, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_source_health(
                    source_id TEXT PRIMARY KEY, provider TEXT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL, last_sync_at_utc TEXT,
                    age_hours REAL, expected_hours REAL, issue TEXT, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_accounting_completeness(
                    key TEXT PRIMARY KEY, vendor_name TEXT NOT NULL, document_kind TEXT NOT NULL, observed_periods INTEGER NOT NULL,
                    first_period TEXT, last_period TEXT, missing_periods_json TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_entity_profiles(
                    entity_key TEXT PRIMARY KEY, entity_id INTEGER NOT NULL, entity_type TEXT NOT NULL, canonical_name TEXT NOT NULL,
                    verification_status TEXT NOT NULL, lifecycle_status TEXT NOT NULL, contact_points INTEGER NOT NULL DEFAULT 0,
                    relationships INTEGER NOT NULL DEFAULT 0, provenance_count INTEGER NOT NULL DEFAULT 0, document_count INTEGER NOT NULL DEFAULT 0,
                    accounting_documents INTEGER NOT NULL DEFAULT 0, detail_json TEXT NOT NULL DEFAULT '{}', updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_automation_hygiene(
                    id TEXT PRIMARY KEY, category TEXT NOT NULL, subject TEXT NOT NULL, state TEXT NOT NULL, rationale TEXT NOT NULL,
                    recommended_action TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_why_events(
                    id TEXT PRIMARY KEY, object_type TEXT NOT NULL, object_id TEXT NOT NULL, trigger_text TEXT NOT NULL, policy_text TEXT NOT NULL,
                    action_text TEXT NOT NULL, outcome_text TEXT NOT NULL, owner_approval TEXT NOT NULL, created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_why_object ON executive_why_events(object_type,object_id,created_at_utc);
                CREATE TABLE IF NOT EXISTS executive_workflow_templates(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
                    workflow_id TEXT, trigger_examples_json TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL,
                    owner_gate TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executive_automation_lifecycle(
                    object_type TEXT NOT NULL, object_id TEXT NOT NULL, stage TEXT NOT NULL, version TEXT,
                    validation_state TEXT NOT NULL, rollback_ref TEXT, notes TEXT, updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY(object_type,object_id)
                );
                """
            )
        if str(self.path) != ":memory:" and self.path.exists():
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def _audit(self, actor: str, event_type: str, object_type: str, object_id: str, detail: dict[str, Any]) -> str:
        _reject_sensitive(detail, "audit")
        now = utc_now()
        actor = _clean_text(actor, "actor", maximum=128)
        event_type = _clean_text(event_type, "event_type", maximum=128)
        object_type = _clean_text(object_type, "object_type", maximum=64)
        object_id = _clean_text(object_id, "object_id", maximum=128)
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT event_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            previous = str(row["event_hash"]) if row else "0" * 64
            record = {"created_at_utc": now, "actor": actor, "event_type": event_type, "object_type": object_type, "object_id": object_id, "detail": detail, "previous_hash": previous}
            event_hash = hashlib.sha256(_canonical(record).encode("ascii")).hexdigest()
            conn.execute(
                "INSERT INTO audit(created_at_utc,actor,event_type,object_type,object_id,detail_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)",
                (now, actor, event_type, object_type, object_id, _canonical(detail), previous, event_hash),
            )
        return event_hash

    def verify_audit_chain(self) -> bool:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM audit ORDER BY id").fetchall()
        previous = "0" * 64
        for row in rows:
            if row["previous_hash"] != previous:
                return False
            try:
                detail = json.loads(row["detail_json"])
            except json.JSONDecodeError:
                return False
            record = {"created_at_utc": row["created_at_utc"], "actor": row["actor"], "event_type": row["event_type"], "object_type": row["object_type"], "object_id": row["object_id"], "detail": detail, "previous_hash": previous}
            expected = hashlib.sha256(_canonical(record).encode("ascii")).hexdigest()
            if expected != row["event_hash"]:
                return False
            previous = expected
        return True

    def create_work_item(self, *, title: str, desired_outcome: str, source_channel: str, source_ref: str | None = None, priority: str = "normal", owner: str = "john", due_at_utc: str | None = None, actor: str = "ava") -> dict[str, Any]:
        title = _clean_text(title, "title", maximum=512)
        desired_outcome = _clean_text(desired_outcome, "desired_outcome", maximum=4000)
        source_channel = _clean_text(source_channel, "source_channel", maximum=64).lower()
        source_ref = _optional_text(source_ref, "source_ref", maximum=512)
        owner = _clean_text(owner, "owner", maximum=128)
        due_at_utc = _optional_text(due_at_utc, "due_at_utc", maximum=64)
        if priority not in WORK_PRIORITIES:
            raise OfficeManagerError("work item priority is invalid")
        item_id = _new_id("work")
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO work_items(id,title,desired_outcome,state,priority,source_channel,source_ref,owner,due_at_utc,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, title, desired_outcome, "new", priority, source_channel, source_ref, owner, due_at_utc, now, now),
            )
        self._audit(actor, "work.created", "work_item", item_id, {"source_channel": source_channel, "priority": priority})
        return self.get_work_item(item_id)

    def get_work_item(self, item_id: str) -> dict[str, Any]:
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            raise OfficeManagerError("work item id is invalid")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
            artifacts = conn.execute("SELECT id,kind,ref,label,created_at_utc FROM artifacts WHERE work_item_id=? ORDER BY created_at_utc,id", (item_id,)).fetchall()
        if not row:
            raise OfficeManagerError("work item was not found")
        item = dict(row)
        item["artifacts"] = [dict(a) for a in artifacts]
        return item

    def list_work_items(self, *, states: list[str] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
            raise OfficeManagerError("work item list limit is invalid")
        params: list[Any] = []
        sql = "SELECT * FROM work_items"
        if states:
            clean_states = sorted(set(states))
            if any(state not in WORK_STATES for state in clean_states):
                raise OfficeManagerError("work item state filter is invalid")
            sql += " WHERE state IN (" + ",".join("?" for _ in clean_states) + ")"
            params.extend(clean_states)
        sql += " ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, updated_at_utc DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def transition_work_item(self, item_id: str, new_state: str, *, actor: str = "ava", note: str | None = None) -> dict[str, Any]:
        current = self.get_work_item(item_id)
        if new_state not in WORK_STATES:
            raise OfficeManagerError("target work item state is invalid")
        allowed = {
            "new": {"working", "needs_owner", "cancelled"},
            "working": {"waiting_external", "needs_owner", "scheduled", "completed", "cancelled"},
            "waiting_external": {"working", "needs_owner", "scheduled", "completed", "cancelled"},
            "needs_owner": {"working", "waiting_external", "scheduled", "completed", "cancelled"},
            "scheduled": {"working", "waiting_external", "completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if new_state not in allowed[current["state"]]:
            raise OfficeManagerError(f"invalid work item transition {current['state']} -> {new_state}")
        note = _optional_text(note, "note", maximum=2000)
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute("UPDATE work_items SET state=?,updated_at_utc=? WHERE id=?", (new_state, now, item_id))
        self._audit(actor, "work.transition", "work_item", item_id, {"from": current["state"], "to": new_state, "note": note})
        return self.get_work_item(item_id)

    def link_artifact(self, item_id: str, *, kind: str, ref: str, label: str | None = None, actor: str = "ava") -> dict[str, Any]:
        self.get_work_item(item_id)
        kind = _clean_text(kind, "artifact kind", maximum=64).lower()
        ref = _clean_text(ref, "artifact ref", maximum=1024)
        label = _optional_text(label, "artifact label", maximum=512)
        artifact_id = _new_id("artifact")
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute("INSERT INTO artifacts(id,work_item_id,kind,ref,label,created_at_utc) VALUES(?,?,?,?,?,?)", (artifact_id, item_id, kind, ref, label, now))
        self._audit(actor, "artifact.linked", "work_item", item_id, {"artifact_id": artifact_id, "kind": kind})
        return {"id": artifact_id, "work_item_id": item_id, "kind": kind, "ref": ref, "label": label, "created_at_utc": now}

    def add_standing_instruction(self, *, domain: str, statement: str, effect: str, priority: int = 100, actor: str = "john") -> dict[str, Any]:
        domain = _clean_text(domain, "instruction domain", maximum=128).lower()
        if not CAPABILITY_RE.fullmatch(domain):
            raise OfficeManagerError("instruction domain is invalid")
        statement = _clean_text(statement, "instruction statement", maximum=4000)
        if effect not in INSTRUCTION_EFFECTS:
            raise OfficeManagerError("instruction effect is invalid")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 1000:
            raise OfficeManagerError("instruction priority is invalid")
        instruction_id = _new_id("instruction")
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute("INSERT INTO standing_instructions(id,domain,statement,effect,priority,enabled,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,1,?,?)", (instruction_id, domain, statement, effect, priority, now, now))
        self._audit(actor, "instruction.created", "standing_instruction", instruction_id, {"domain": domain, "effect": effect, "priority": priority})
        return {"id": instruction_id, "domain": domain, "statement": statement, "effect": effect, "priority": priority, "enabled": True, "created_at_utc": now, "updated_at_utc": now}

    def list_standing_instructions(self, *, capability: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM standing_instructions WHERE enabled=1 ORDER BY priority DESC,created_at_utc,id"
        with self.connect() as conn:
            rows = conn.execute(sql).fetchall()
        if capability is None:
            return [dict(row) for row in rows]
        if not CAPABILITY_RE.fullmatch(capability):
            raise OfficeManagerError("capability is invalid")
        return [dict(row) for row in rows if _prefix_match(capability, str(row["domain"]))]

    def evaluate_action(self, capability: str, parameters: dict[str, Any] | None = None) -> AuthorityDecision:
        if not isinstance(capability, str) or not CAPABILITY_RE.fullmatch(capability):
            raise OfficeManagerError("action capability is invalid")
        params = {} if parameters is None else parameters
        if not isinstance(params, dict):
            raise OfficeManagerError("action parameters must be an object")
        _reject_sensitive(params)
        if len(_canonical(params).encode("ascii")) > 32768:
            raise OfficeManagerError("action parameters are too large")

        authority, matched = _required_authority(capability, self.policy)
        instructions = self.list_standing_instructions(capability=capability)
        if any(row["effect"] == "deny" for row in instructions):
            return AuthorityDecision(capability, authority, "blocked", False, "standing instruction denies this capability")
        if not matched:
            return AuthorityDecision(capability, "restricted", "blocked", False, "unknown capability has no commissioned control-plane rule")
        if authority == "restricted":
            return AuthorityDecision(capability, authority, "blocked", False, "restricted capability requires a separate explicit authorization path")
        if any(_prefix_match(capability, prefix) for prefix in self.policy["blocked_prefixes"]):
            return AuthorityDecision(capability, authority, "blocked", False, "capability is behind an explicit hard gate")
        if any(_prefix_match(capability, prefix) for prefix in self.policy["always_confirm_prefixes"]) or any(row["effect"] == "require_confirmation" for row in instructions):
            return AuthorityDecision(capability, authority, "confirmation_required", False, "explicit confirmation is required")

        if AUTHORITY_ORDER[authority] > AUTHORITY_ORDER[self.policy["autonomy_level"]]:
            return AuthorityDecision(capability, authority, "confirmation_required", False, "configured autonomy does not cover this action")

        if authority == "observe":
            return AuthorityDecision(capability, authority, "allowed", False, "read-only observation is authorized")
        if authority == "prepare":
            return AuthorityDecision(capability, authority, "allowed", False, "preparation is authorized; no external action is implied")
        if not self.policy["execution_enabled"]:
            return AuthorityDecision(capability, authority, "allowed", False, "authorized in principle but the external execution gate is disabled")
        return AuthorityDecision(capability, authority, "allowed", True, "authorized by policy and execution gate")

    def propose_action(self, *, capability: str, summary: str, parameters: dict[str, Any] | None = None, work_item_id: str | None = None, requested_by: str = "ava", actor: str = "ava") -> dict[str, Any]:
        if work_item_id is not None:
            self.get_work_item(work_item_id)
        summary = _clean_text(summary, "action summary", maximum=2000)
        requested_by = _clean_text(requested_by, "requested_by", maximum=128)
        params = {} if parameters is None else parameters
        decision = self.evaluate_action(capability, params)
        proposal_id = _new_id("action")
        status = "blocked" if decision.authorization == "blocked" else ("awaiting_confirmation" if decision.authorization == "confirmation_required" else "authorized")
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO action_proposals(id,work_item_id,capability,summary,parameters_json,requested_by,authority_class,authorization,executable,reason,status,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (proposal_id, work_item_id, capability, summary, _canonical(params), requested_by, decision.authority, decision.authorization, 1 if decision.executable else 0, decision.reason, status, now, now),
            )
        self._audit(actor, "action.proposed", "action_proposal", proposal_id, {"capability": capability, "policy_decision": decision.authorization, "executable": decision.executable, "work_item_id": work_item_id})
        return self.get_action_proposal(proposal_id)

    def get_action_proposal(self, proposal_id: str) -> dict[str, Any]:
        if not isinstance(proposal_id, str) or not ID_RE.fullmatch(proposal_id):
            raise OfficeManagerError("action proposal id is invalid")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM action_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise OfficeManagerError("action proposal was not found")
        item = dict(row)
        item["parameters"] = json.loads(item.pop("parameters_json"))
        item["executable"] = bool(item["executable"])
        return item

    def approve_action(self, proposal_id: str, *, actor: str = "john") -> dict[str, Any]:
        proposal = self.get_action_proposal(proposal_id)
        if proposal["status"] != "awaiting_confirmation":
            raise OfficeManagerError("only an action awaiting confirmation may be approved")
        authority, matched = _required_authority(proposal["capability"], self.policy)
        if not matched or authority == "restricted" or any(_prefix_match(proposal["capability"], prefix) for prefix in self.policy["blocked_prefixes"]):
            raise OfficeManagerError("the action is blocked and cannot be approved here")
        if any(row["effect"] == "deny" for row in self.list_standing_instructions(capability=proposal["capability"])):
            raise OfficeManagerError("the action is now blocked by a standing instruction")
        executable = bool(self.policy["execution_enabled"] and authority not in {"observe", "prepare", "restricted"})
        now = utc_now()
        reason = "explicit owner approval recorded; external execution gate " + ("enabled" if executable else "disabled")
        with self._lock, self.connect() as conn:
            conn.execute("UPDATE action_proposals SET authorization='approved',executable=?,reason=?,status='approved',updated_at_utc=? WHERE id=?", (1 if executable else 0, reason, now, proposal_id))
        self._audit(actor, "action.approved", "action_proposal", proposal_id, {"executable": executable})
        return self.get_action_proposal(proposal_id)

    def upsert_team_member(self, *, member_id: str, display_name: str, department: str, role: str, action_level: str, authority_ceiling: str, service_unit: str | None = None, timer_unit: str | None = None, capabilities: list[str] | None = None, health_state: str = "unknown", metadata: dict[str, Any] | None = None, actor: str = "ava-executive") -> dict[str, Any]:
        member_id = _clean_text(member_id, "member_id", maximum=128)
        if not CAPABILITY_RE.fullmatch(member_id):
            raise OfficeManagerError("team member id is invalid")
        display_name = _clean_text(display_name, "display_name", maximum=256)
        department = _clean_text(department, "department", maximum=128)
        role = _clean_text(role, "role", maximum=512)
        action_level = _clean_text(action_level, "action_level", maximum=64)
        authority_ceiling = _clean_text(authority_ceiling, "authority_ceiling", maximum=64)
        service_unit = _optional_text(service_unit, "service_unit", maximum=256)
        timer_unit = _optional_text(timer_unit, "timer_unit", maximum=256)
        capabilities = [] if capabilities is None else capabilities
        metadata = {} if metadata is None else metadata
        _reject_sensitive(metadata, "metadata")
        now = utc_now()
        with self._lock, self.connect() as conn:
            existed = conn.execute("SELECT 1 FROM executive_team_members WHERE member_id=?", (member_id,)).fetchone() is not None
            conn.execute("""INSERT INTO executive_team_members(member_id,display_name,department,role,service_unit,timer_unit,action_level,authority_ceiling,capabilities_json,active,health_state,last_checkin_at_utc,metadata_json,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?, ?, ?) ON CONFLICT(member_id) DO UPDATE SET display_name=excluded.display_name,department=excluded.department,role=excluded.role,service_unit=excluded.service_unit,timer_unit=excluded.timer_unit,action_level=excluded.action_level,authority_ceiling=excluded.authority_ceiling,capabilities_json=excluded.capabilities_json,active=1,health_state=excluded.health_state,last_checkin_at_utc=excluded.last_checkin_at_utc,metadata_json=excluded.metadata_json,updated_at_utc=excluded.updated_at_utc""", (member_id,display_name,department,role,service_unit,timer_unit,action_level,authority_ceiling,_canonical(capabilities),health_state,now,_canonical(metadata),now,now))
        if not existed:
            self._audit(actor, "team.member.registered", "team_member", member_id, {"department": department, "action_level": action_level, "authority_ceiling": authority_ceiling})
        return self.get_team_member(member_id)

    def get_team_member(self, member_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row=conn.execute("SELECT * FROM executive_team_members WHERE member_id=?",(member_id,)).fetchone()
        if not row: raise OfficeManagerError("team member was not found")
        out=dict(row); out["active"]=bool(out["active"]); out["capabilities"]=json.loads(out.pop("capabilities_json")); out["metadata"]=json.loads(out.pop("metadata_json")); return out

    def record_team_report(self, *, member_id: str, report_type: str, health_state: str, summary: str, detail: dict[str, Any], source_ref: str, needs_attention: bool = False, severity: str = "info", assignment_id: str | None = None, actor: str = "ava-executive") -> dict[str, Any]:
        self.get_team_member(member_id)
        report_type=_clean_text(report_type,"report_type",maximum=64); health_state=_clean_text(health_state,"health_state",maximum=64); summary=_clean_text(summary,"summary",maximum=2000); source_ref=_clean_text(source_ref,"source_ref",maximum=1024); severity=_clean_text(severity,"severity",maximum=32); _reject_sensitive(detail,"report.detail")
        if assignment_id is not None and not ID_RE.fullmatch(assignment_id): raise OfficeManagerError("assignment id is invalid")
        now=utc_now(); report_id=_new_id("report")
        with self._lock, self.connect() as conn:
            existing=conn.execute("SELECT id FROM executive_reports WHERE member_id=? AND source_ref=?",(member_id,source_ref)).fetchone()
            if existing: report_id=str(existing["id"])
            else:
                conn.execute("INSERT INTO executive_reports(id,member_id,assignment_id,report_type,health_state,summary,detail_json,needs_attention,severity,source_ref,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(report_id,member_id,assignment_id,report_type,health_state,summary,_canonical(detail),1 if needs_attention else 0,severity,source_ref,now))
            conn.execute("UPDATE executive_team_members SET health_state=?,last_checkin_at_utc=?,last_report_id=?,updated_at_utc=? WHERE member_id=?",(health_state,now,report_id,now,member_id))
        if not existing:
            self._audit(actor,"team.report.received","team_report",report_id,{"member_id":member_id,"health_state":health_state,"needs_attention":bool(needs_attention),"severity":severity})
        return {"id":report_id,"member_id":member_id,"health_state":health_state,"summary":summary,"needs_attention":bool(needs_attention),"severity":severity,"source_ref":source_ref,"created_at_utc":now,"new":not bool(existing)}

    def create_assignment(self, *, member_id: str, objective: str, priority: str = "normal", work_item_id: str | None = None, dependencies: list[str] | None = None, requested_by: str = "ava", state: str = "assigned", actor: str = "ava-executive") -> dict[str, Any]:
        self.get_team_member(member_id)
        if work_item_id is not None: self.get_work_item(work_item_id)
        objective=_clean_text(objective,"objective",maximum=4000)
        if priority not in WORK_PRIORITIES: raise OfficeManagerError("assignment priority is invalid")
        if state not in {"assigned","working","waiting","review","completed","failed","cancelled"}: raise OfficeManagerError("assignment state is invalid")
        dependencies=[] if dependencies is None else dependencies; requested_by=_clean_text(requested_by,"requested_by",maximum=128); aid=_new_id("assignment"); now=utc_now()
        with self._lock,self.connect() as conn:
            conn.execute("INSERT INTO executive_assignments(id,work_item_id,member_id,objective,state,priority,dependencies_json,requested_by,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,work_item_id,member_id,objective,state,priority,_canonical(dependencies),requested_by,now,now))
        self._audit(actor,"assignment.created","assignment",aid,{"member_id":member_id,"work_item_id":work_item_id,"priority":priority,"state":state})
        return {"id":aid,"work_item_id":work_item_id,"member_id":member_id,"objective":objective,"state":state,"priority":priority,"dependencies":dependencies,"requested_by":requested_by,"created_at_utc":now,"updated_at_utc":now}

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            work = {row["state"]: int(row["count"]) for row in conn.execute("SELECT state,COUNT(*) AS count FROM work_items GROUP BY state")}
            actions = {row["status"]: int(row["count"]) for row in conn.execute("SELECT status,COUNT(*) AS count FROM action_proposals GROUP BY status")}
            instructions = int(conn.execute("SELECT COUNT(*) FROM standing_instructions WHERE enabled=1").fetchone()[0])
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": "office-manager-foundation",
            "execution_enabled": bool(self.policy["execution_enabled"]),
            "autonomy_level": self.policy["autonomy_level"],
            "work_items": work,
            "actions": actions,
            "standing_instructions": instructions,
            "audit_chain_valid": self.verify_audit_chain(),
        }
