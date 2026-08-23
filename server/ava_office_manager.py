#!/usr/bin/env python3
"""Durable workflow and authority foundation for the WW.CX Ava office manager.

This module intentionally performs no external side effects.  It stores work, standing
instructions, cross-channel references and action proposals, then evaluates each action
against an explicit policy.  Provider adapters (calendar, mail, telephony, purchasing,
etc.) must remain separate and may execute only after their own control plane is enabled.
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

SCHEMA_VERSION = 1
WORK_STATES = {
    "new",
    "working",
    "waiting_external",
    "needs_owner",
    "scheduled",
    "completed",
    "cancelled",
}
WORK_PRIORITIES = {"low", "normal", "high", "urgent"}
INSTRUCTION_EFFECTS = {"deny", "require_confirmation", "prefer"}
ACTION_STATUSES = {"proposed", "awaiting_confirmation", "authorized", "approved", "blocked", "completed", "failed", "cancelled"}
AUTHORITY_ORDER = {"observe": 1, "prepare": 2, "routine": 3, "conditional": 4, "restricted": 5}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{7,127}$")
CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
FORBIDDEN_KEYS = {
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "private_key",
    "credential",
    "credentials",
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
        "calendar.event.cancel",
        "telephony.originate",
        "purchasing.commit",
        "travel.book",
        "financial",
        "legal",
        "contract",
        "credential",
        "destructive",
        "emergency",
    ],
    "blocked_prefixes": [
        "financial.transfer",
        "contract.sign",
        "credential.export",
        "destructive.delete_irrecoverable",
        "emergency.call",
        "telephony.route.change",
        "telephony.number.port",
        "telephony.stir_shaken.sign",
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
    normalized_rules: list[dict[str, str]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise OfficeManagerError("office-manager capability rule must be an object")
        prefix = rule.get("prefix")
        authority = rule.get("authority")
        if not isinstance(prefix, str) or not CAPABILITY_RE.fullmatch(prefix):
            raise OfficeManagerError("office-manager capability rule prefix is invalid")
        if authority not in AUTHORITY_ORDER:
            raise OfficeManagerError("office-manager capability rule authority is invalid")
        normalized_rules.append({"prefix": prefix, "authority": authority})
    for name in ("always_confirm_prefixes", "blocked_prefixes"):
        values = policy.get(name, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not CAPABILITY_RE.fullmatch(v) for v in values):
            raise OfficeManagerError(f"office-manager {name} is invalid")
    return {
        "version": 1,
        "autonomy_level": autonomy,
        "execution_enabled": bool(policy["execution_enabled"]),
        "capability_rules": normalized_rules,
        "always_confirm_prefixes": list(policy.get("always_confirm_prefixes", [])),
        "blocked_prefixes": list(policy.get("blocked_prefixes", [])),
    }


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        return validate_policy(dict(DEFAULT_POLICY))
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_policy(raw)


def _prefix_match(capability: str, prefix: str) -> bool:
    return capability == prefix or capability.startswith(prefix + ".")


def _required_authority(capability: str, policy: dict[str, Any]) -> str:
    matches = [rule for rule in policy["capability_rules"] if _prefix_match(capability, rule["prefix"])]
    if not matches:
        return "restricted"
    matches.sort(key=lambda rule: len(rule["prefix"]), reverse=True)
    return str(matches[0]["authority"])


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
                conn.execute("PRAGMA journal_mode=WAL")
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
            record = {
                "created_at_utc": now,
                "actor": actor,
                "event_type": event_type,
                "object_type": object_type,
                "object_id": object_id,
                "detail": detail,
                "previous_hash": previous,
            }
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
            record = {
                "created_at_utc": row["created_at_utc"],
                "actor": row["actor"],
                "event_type": row["event_type"],
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "detail": detail,
                "previous_hash": previous,
            }
            expected = hashlib.sha256(_canonical(record).encode("ascii")).hexdigest()
            if expected != row["event_hash"]:
                return False
            previous = expected
        return True

    def create_work_item(
        self,
        *,
        title: str,
        desired_outcome: str,
        source_channel: str,
        source_ref: str | None = None,
        priority: str = "normal",
        owner: str = "john",
        due_at_utc: str | None = None,
        actor: str = "ava",
    ) -> dict[str, Any]:
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
            conn.execute(
                "INSERT INTO artifacts(id,work_item_id,kind,ref,label,created_at_utc) VALUES(?,?,?,?,?,?)",
                (artifact_id, item_id, kind, ref, label, now),
            )
        self._audit(actor, "artifact.linked", "work_item", item_id, {"artifact_id": artifact_id, "kind": kind})
        return {"id": artifact_id, "work_item_id": item_id, "kind": kind, "ref": ref, "label": label, "created_at_utc": now}

    def add_standing_instruction(
        self,
        *,
        domain: str,
        statement: str,
        effect: str,
        priority: int = 100,
        actor: str = "john",
    ) -> dict[str, Any]:
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
            conn.execute(
                "INSERT INTO standing_instructions(id,domain,statement,effect,priority,enabled,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,1,?,?)",
                (instruction_id, domain, statement, effect, priority, now, now),
            )
        self._audit(actor, "instruction.created", "standing_instruction", instruction_id, {"domain": domain, "effect": effect, "priority": priority})
        return {"id": instruction_id, "domain": domain, "statement": statement, "effect": effect, "priority": priority, "enabled": True, "created_at_utc": now, "updated_at_utc": now}

    def list_standing_instructions(self, *, capability: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM standing_instructions WHERE enabled=1"
        params: list[Any] = []
        if capability is not None:
            if not CAPABILITY_RE.fullmatch(capability):
                raise OfficeManagerError("capability is invalid")
            rows: list[sqlite3.Row]
            with self.connect() as conn:
                rows = conn.execute(sql + " ORDER BY priority DESC,created_at_utc,id").fetchall()
            return [dict(row) for row in rows if _prefix_match(capability, str(row["domain"]))]
        with self.connect() as conn:
            rows = conn.execute(sql + " ORDER BY priority DESC,created_at_utc,id", params).fetchall()
        return [dict(row) for row in rows]

    def evaluate_action(self, capability: str, parameters: dict[str, Any] | None = None) -> AuthorityDecision:
        if not isinstance(capability, str) or not CAPABILITY_RE.fullmatch(capability):
            raise OfficeManagerError("action capability is invalid")
        params = {} if parameters is None else parameters
        if not isinstance(params, dict):
            raise OfficeManagerError("action parameters must be an object")
        _reject_sensitive(params)
        if len(_canonical(params).encode("ascii")) > 32768:
            raise OfficeManagerError("action parameters are too large")

        authority = _required_authority(capability, self.policy)
        blocked = any(_prefix_match(capability, prefix) for prefix in self.policy["blocked_prefixes"])
        always_confirm = any(_prefix_match(capability, prefix) for prefix in self.policy["always_confirm_prefixes"])
        instructions = self.list_standing_instructions(capability=capability)

        if any(row["effect"] == "deny" for row in instructions):
            return AuthorityDecision(capability, authority, "blocked", False, "standing instruction denies this capability")
        if blocked:
            return AuthorityDecision(capability, authority, "blocked", False, "capability is behind an explicit hard gate")
        if always_confirm or any(row["effect"] == "require_confirmation" for row in instructions):
            return AuthorityDecision(capability, authority, "confirmation_required", False, "explicit confirmation is required")

        configured = AUTHORITY_ORDER[self.policy["autonomy_level"]]
        required = AUTHORITY_ORDER[authority]
        if required > configured:
            return AuthorityDecision(capability, authority, "confirmation_required", False, "configured autonomy does not cover this action")

        executable = bool(self.policy["execution_enabled"] and authority not in {"observe", "prepare"})
        reason = "authorized by policy"
        if authority == "observe":
            executable = False
            reason = "read-only observation is authorized"
        elif authority == "prepare":
            executable = False
            reason = "preparation is authorized; no external action is implied"
        elif not self.policy["execution_enabled"]:
            reason = "authorized in principle but the external execution gate is disabled"
        return AuthorityDecision(capability, authority, "allowed", executable, reason)

    def propose_action(
        self,
        *,
        capability: str,
        summary: str,
        parameters: dict[str, Any] | None = None,
        work_item_id: str | None = None,
        requested_by: str = "ava",
        actor: str = "ava",
    ) -> dict[str, Any]:
        if work_item_id is not None:
            self.get_work_item(work_item_id)
        summary = _clean_text(summary, "action summary", maximum=2000)
        requested_by = _clean_text(requested_by, "requested_by", maximum=128)
        params = {} if parameters is None else parameters
        decision = self.evaluate_action(capability, params)
        proposal_id = _new_id("action")
        if decision.authorization == "blocked":
            status = "blocked"
        elif decision.authorization == "confirmation_required":
            status = "awaiting_confirmation"
        else:
            status = "authorized"
        now = utc_now()
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO action_proposals(id,work_item_id,capability,summary,parameters_json,requested_by,authority_class,authorization,executable,reason,status,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (proposal_id, work_item_id, capability, summary, _canonical(params), requested_by, decision.authority, decision.authorization, 1 if decision.executable else 0, decision.reason, status, now, now),
            )
        self._audit(actor, "action.proposed", "action_proposal", proposal_id, {"capability": capability, "authorization": decision.authorization, "executable": decision.executable, "work_item_id": work_item_id})
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
        decision = self.evaluate_action(proposal["capability"], proposal["parameters"])
        if decision.authorization == "blocked":
            raise OfficeManagerError("the action is now blocked by policy")
        now = utc_now()
        executable = bool(self.policy["execution_enabled"] and proposal["authority_class"] not in {"observe", "prepare"})
        with self._lock, self.connect() as conn:
            conn.execute(
                "UPDATE action_proposals SET authorization='approved',executable=?,reason=?,status='approved',updated_at_utc=? WHERE id=?",
                (1 if executable else 0, "explicit owner approval recorded; external execution gate " + ("enabled" if executable else "disabled"), now, proposal_id),
            )
        self._audit(actor, "action.approved", "action_proposal", proposal_id, {"executable": executable})
        return self.get_action_proposal(proposal_id)

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
