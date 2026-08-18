#!/usr/bin/env python3
"""WW.CX Edge1 SNMP platform core.

Private-first, stdlib orchestration around mature Net-SNMP command-line tools.
Credentials are resolved from root-readable profile files and are never persisted
in the inventory, telemetry, audit log, or API output.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import math
import os
import re
import sqlite3
import statistics
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(os.environ.get("EDGE1_SNMP_DB", "/var/lib/edge1-snmp/snmp.sqlite3"))
CONFIG_PATH = Path(os.environ.get("EDGE1_SNMP_CONFIG", "/etc/edge1-snmp/config.json"))
PROFILE_DIR = Path(os.environ.get("EDGE1_SNMP_PROFILE_DIR", "/etc/edge1-snmp/profiles"))
DEFAULT_TIMEOUT = 3
DEFAULT_RETRIES = 1
MAX_DISCOVERY_HOSTS = 4096
STANDARD_OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0", "sysObjectID": "1.3.6.1.2.1.1.2.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0", "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0", "sysLocation": "1.3.6.1.2.1.1.6.0",
    "ifNumber": "1.3.6.1.2.1.2.1.0",
}
ACTION_CLASS = {
    "repoll_device": "READ_ONLY", "refresh_inventory": "REVERSIBLE_LOW_RISK",
    "clear_internal_queue": "REVERSIBLE_LOW_RISK", "temporarily_adjust_polling": "REVERSIBLE_OPERATIONAL",
    "disable_broken_polling": "REVERSIBLE_OPERATIONAL", "restore_application_config": "REVERSIBLE_OPERATIONAL",
    "restart_snmp_service": "REVERSIBLE_OPERATIONAL", "snmp_set": "PRIVILEGED_NETWORK_CHANGE",
}
AUTO_ALLOWED = {"READ_ONLY", "REVERSIBLE_LOW_RISK", "REVERSIBLE_OPERATIONAL"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"timezone": "UTC", "polling": {"interval_seconds": 300, "timeout_seconds": 3, "retries": 1, "concurrency": 16},
                "discovery": {"allowed_cidrs": [], "max_hosts": 256, "allow_public": False},
                "retention": {"telemetry_days": 30, "events_days": 90, "audit_days": 365}, "snmp_set_enabled": False}
    data = json.loads(path.read_text(encoding="utf-8")); validate_config(data); return data


def validate_config(data: dict[str, Any]) -> None:
    if not isinstance(data, dict): raise ValueError("configuration must be an object")
    poll = data.get("polling", {}); interval = int(poll.get("interval_seconds", 300)); concurrency = int(poll.get("concurrency", 16))
    if interval < 10 or interval > 86400: raise ValueError("polling interval must be 10..86400 seconds")
    if concurrency < 1 or concurrency > 256: raise ValueError("polling concurrency must be 1..256")
    disc = data.get("discovery", {}); max_hosts = int(disc.get("max_hosts", 256))
    if max_hosts < 1 or max_hosts > MAX_DISCOVERY_HOSTS: raise ValueError(f"discovery max_hosts must be 1..{MAX_DISCOVERY_HOSTS}")
    for cidr in disc.get("allowed_cidrs", []): ipaddress.ip_network(cidr, strict=False)


def connect_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15); conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL"); conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS devices (device_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, hostname TEXT,
      management_address TEXT NOT NULL UNIQUE, device_type TEXT, vendor TEXT, model TEXT, serial_number TEXT, site TEXT,
      location TEXT, tags_json TEXT NOT NULL DEFAULT '[]', owner TEXT, environment TEXT, snmp_version TEXT NOT NULL DEFAULT '3',
      snmp_port INTEGER NOT NULL DEFAULT 161, snmp_profile TEXT, credential_reference TEXT, polling_enabled INTEGER NOT NULL DEFAULT 1,
      polling_interval INTEGER NOT NULL DEFAULT 300, trap_enabled INTEGER NOT NULL DEFAULT 1, write_enabled INTEGER NOT NULL DEFAULT 0,
      timezone TEXT NOT NULL DEFAULT 'UTC', status TEXT NOT NULL DEFAULT 'unknown', last_seen TEXT, last_poll TEXT, last_success TEXT,
      last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, device_id TEXT NOT NULL,
      oid TEXT NOT NULL, name TEXT, value_num REAL, value_text TEXT, unit TEXT, source TEXT NOT NULL DEFAULT 'poll',
      FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_metrics_device_ts ON metrics(device_id, ts); CREATE INDEX IF NOT EXISTS idx_metrics_oid_ts ON metrics(oid, ts);
    CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, ts TEXT NOT NULL, source_address TEXT, device_id TEXT, snmp_version TEXT,
      enterprise TEXT, trap_oid TEXT, varbinds_json TEXT NOT NULL DEFAULT '{}', severity TEXT NOT NULL DEFAULT 'info', event_type TEXT NOT NULL,
      correlation_id TEXT, raw_metadata_json TEXT NOT NULL DEFAULT '{}', dedupe_key TEXT);
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts); CREATE INDEX IF NOT EXISTS idx_events_dedupe ON events(dedupe_key, ts);
    CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT,
      device_id TEXT, severity TEXT NOT NULL, policy TEXT NOT NULL, state TEXT NOT NULL, summary TEXT NOT NULL,
      evidence_json TEXT NOT NULL DEFAULT '[]', correlation_id TEXT);
    CREATE TABLE IF NOT EXISTS mib_objects (oid TEXT PRIMARY KEY, name TEXT NOT NULL, module TEXT, syntax TEXT, access TEXT, status TEXT,
      units TEXT, description TEXT, enums_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
    CREATE VIRTUAL TABLE IF NOT EXISTS mib_search USING fts5(oid, name, module, description, content='');
    CREATE TABLE IF NOT EXISTS action_proposals (proposal_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL,
      action TEXT NOT NULL, action_class TEXT NOT NULL, target TEXT, reason TEXT NOT NULL, state TEXT NOT NULL,
      validation_json TEXT NOT NULL DEFAULT '{}', rollback_json TEXT NOT NULL DEFAULT '{}', result_json TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS audit (audit_id TEXT PRIMARY KEY, ts TEXT NOT NULL, actor TEXT NOT NULL, source TEXT NOT NULL,
      action TEXT NOT NULL, target TEXT, reason TEXT, before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}',
      result TEXT NOT NULL, correlation_id TEXT, ai_involvement TEXT NOT NULL DEFAULT 'none', rollback_json TEXT NOT NULL DEFAULT '{}');
    """); conn.commit(); return conn


def audit(conn: sqlite3.Connection, *, actor: str, source: str, action: str, target: str | None, reason: str, result: str,
          before: Any = None, after: Any = None, correlation_id: str | None = None, ai_involvement: str = "none", rollback: Any = None) -> str:
    aid = str(uuid.uuid4()); conn.execute("INSERT INTO audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, utcnow(), actor, source, action, target, reason, json.dumps(before or {}, sort_keys=True), json.dumps(after or {}, sort_keys=True),
         result, correlation_id, ai_involvement, json.dumps(rollback or {}, sort_keys=True))); conn.commit(); return aid


def canonical_oid(value: str) -> str:
    value = value.strip().lstrip(".")
    if not value or not re.fullmatch(r"\d+(?:\.\d+)*", value): raise ValueError("OID must contain dotted decimal integers")
    parts = [int(x) for x in value.split(".")]
    if len(parts) < 2 or parts[0] > 2 or (parts[1] > 39 and parts[0] < 2): raise ValueError("invalid ASN.1 object identifier prefix")
    return ".".join(str(x) for x in parts)


def counter_rate(previous: int | None, current: int, elapsed_seconds: float, bits: int = 64, rebooted: bool = False) -> float | None:
    if previous is None or elapsed_seconds <= 0 or rebooted: return None
    if current >= previous: delta = current - previous
    else:
        modulus = 1 << bits
        if previous > modulus * 0.75 and current < modulus * 0.25: delta = modulus - previous + current
        else: return None
    return delta / elapsed_seconds


def rolling_anomaly(values: Iterable[float], current: float, *, z_threshold: float = 3.0) -> dict[str, Any]:
    samples = [float(v) for v in values if math.isfinite(float(v))]
    if len(samples) < 5: return {"anomalous": False, "reason": "insufficient_baseline", "sample_count": len(samples)}
    mean = statistics.fmean(samples); sd = statistics.pstdev(samples); z = (0.0 if current == mean else math.inf) if sd == 0 else (current - mean) / sd
    return {"anomalous": abs(z) >= z_threshold, "mean": mean, "stddev": sd, "z_score": z, "sample_count": len(samples)}


@dataclass(frozen=True)
class CredentialProfile:
    version: str; username: str | None = None; auth_protocol: str | None = None; auth_password: str | None = None
    priv_protocol: str | None = None; priv_password: str | None = None; community: str | None = None


class CredentialResolver:
    def __init__(self, profile_dir: Path = PROFILE_DIR): self.profile_dir = profile_dir
    def load(self, reference: str) -> CredentialProfile:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", reference or ""): raise ValueError("invalid credential reference")
        path = self.profile_dir / f"{reference}.json"; st = path.stat()
        if st.st_mode & 0o077: raise PermissionError("credential profile must not be group/world accessible")
        data = json.loads(path.read_text(encoding="utf-8")); version = str(data.get("version", "3"))
        if version == "3":
            required = ["username", "auth_protocol", "auth_password", "priv_protocol", "priv_password"]
            if any(not data.get(k) for k in required): raise ValueError("SNMPv3 authPriv profile is incomplete")
            return CredentialProfile(version="3", username=data["username"], auth_protocol=data["auth_protocol"], auth_password=data["auth_password"], priv_protocol=data["priv_protocol"], priv_password=data["priv_password"])
        if version in {"1", "2c"} and data.get("community"): return CredentialProfile(version=version, community=data["community"])
        raise ValueError("unsupported credential profile")


class NetSNMP:
    def __init__(self, resolver: CredentialResolver | None = None): self.resolver = resolver or CredentialResolver()
    def _auth_argv(self, profile: CredentialProfile) -> list[str]:
        if profile.version == "3":
            return ["-v3", "-l", "authPriv", "-u", profile.username or "", "-a", profile.auth_protocol or "SHA", "-A", profile.auth_password or "", "-x", profile.priv_protocol or "AES", "-X", profile.priv_password or ""]
        return [f"-v{profile.version}", "-c", profile.community or ""]
    @staticmethod
    def _safe_error(text: str) -> str:
        return re.sub(r"(?i)(community|password|passphrase|authpass|privpass)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)[-4000:]
    def query(self, tool: str, address: str, port: int, profile_ref: str, oids: list[str], *, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> dict[str, str]:
        if tool not in {"snmpget", "snmpwalk", "snmpbulkwalk"}: raise ValueError("unsupported Net-SNMP query tool")
        profile = self.resolver.load(profile_ref); argv = [tool, "-OQn", "-t", str(timeout), "-r", str(retries), *self._auth_argv(profile), f"udp:{address}:{port}", *oids]
        try: cp = subprocess.run(argv, text=True, capture_output=True, timeout=max(5, timeout * (retries + 2)), check=False, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "MIBS": ""})
        finally:
            for i in range(len(argv)): argv[i] = "[REDACTED]"
        if cp.returncode != 0: raise RuntimeError(self._safe_error(cp.stderr or cp.stdout or "SNMP query failed"))
        result: dict[str, str] = {}
        for line in cp.stdout.splitlines():
            if "=" in line:
                oid, value = line.split("=", 1); result[oid.strip().lstrip(".")] = value.strip()
        return result


def add_device(conn: sqlite3.Connection, payload: dict[str, Any], actor: str = "operator") -> dict[str, Any]:
    address = str(ipaddress.ip_address(payload["management_address"])); version = str(payload.get("snmp_version", "3"))
    if version not in {"1", "2c", "3"}: raise ValueError("unsupported SNMP version")
    if version != "3" and not bool(payload.get("legacy_protocol_approved", False)): raise ValueError("SNMPv1/v2c onboarding requires explicit legacy_protocol_approved=true")
    credential_reference = str(payload.get("credential_reference") or "")
    if not credential_reference: raise ValueError("credential_reference is required")
    device_id = str(payload.get("device_id") or uuid.uuid4()); now = utcnow()
    row = (device_id, payload.get("display_name") or address, payload.get("hostname"), address, payload.get("device_type"), payload.get("vendor"), payload.get("model"), payload.get("serial_number"), payload.get("site"), payload.get("location"), json.dumps(payload.get("tags", [])), payload.get("owner"), payload.get("environment"), version, int(payload.get("snmp_port", 161)), payload.get("snmp_profile"), credential_reference, int(bool(payload.get("polling_enabled", True))), int(payload.get("polling_interval", 300)), int(bool(payload.get("trap_enabled", True))), int(bool(payload.get("write_enabled", False))), payload.get("timezone", "UTC"), "unknown", None, None, None, None, now, now, json.dumps(payload.get("metadata", {}), sort_keys=True))
    conn.execute("INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row); conn.commit()
    audit(conn, actor=actor, source="api", action="device.create", target=device_id, reason="managed device onboarding", result="succeeded", after={"management_address": address, "snmp_version": version})
    return get_device(conn, device_id)


def get_device(conn: sqlite3.Connection, device_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
    if not row: raise KeyError(device_id)
    value = dict(row); value["tags"] = json.loads(value.pop("tags_json")); value["metadata"] = json.loads(value.pop("metadata_json")); return value


def list_devices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [get_device(conn, r["device_id"]) for r in conn.execute("SELECT device_id FROM devices ORDER BY display_name")]


def store_metric(conn: sqlite3.Connection, device_id: str, oid: str, value: Any, *, name: str | None = None, unit: str | None = None, source: str = "poll") -> None:
    num = None; text = None
    try:
        num = float(value)
        if not math.isfinite(num): num = None; text = str(value)
    except (TypeError, ValueError): text = str(value)
    conn.execute("INSERT INTO metrics(ts,device_id,oid,name,value_num,value_text,unit,source) VALUES(?,?,?,?,?,?,?,?)", (utcnow(), device_id, canonical_oid(oid), name, num, text, unit, source))


def normalize_trap(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    ts = payload.get("timestamp") or utcnow(); source = payload.get("source_address"); trap_oid = canonical_oid(payload.get("trap_oid") or "1.3.6.1.6.3.1.1.5.1"); varbinds = payload.get("varbinds") or {}
    dedupe_key = hashlib.sha256(json.dumps([source, trap_oid, varbinds], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    recent = conn.execute("SELECT event_id FROM events WHERE dedupe_key=? AND ts >= datetime('now','-30 seconds') LIMIT 1", (dedupe_key,)).fetchone()
    if recent: return {"duplicate": True, "event_id": recent["event_id"]}
    event_id = str(uuid.uuid4()); correlation_id = payload.get("correlation_id") or str(uuid.uuid4())
    conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (event_id, ts, source, payload.get("device_id"), payload.get("snmp_version"), payload.get("enterprise"), trap_oid, json.dumps(varbinds, sort_keys=True), payload.get("severity", "info"), payload.get("event_type", "snmp_trap"), correlation_id, json.dumps(payload.get("raw_metadata") or {}, sort_keys=True), dedupe_key)); conn.commit()
    return {"duplicate": False, "event_id": event_id, "correlation_id": correlation_id}


def allowed_discovery_hosts(cidr: str, config: dict[str, Any]) -> list[str]:
    network = ipaddress.ip_network(cidr, strict=False); disc = config.get("discovery", {}); allowed = [ipaddress.ip_network(x, strict=False) for x in disc.get("allowed_cidrs", [])]
    if not any(network.subnet_of(parent) for parent in allowed): raise PermissionError("discovery CIDR is outside configured allowed networks")
    if network.is_global and not bool(disc.get("allow_public", False)): raise PermissionError("public-network discovery is disabled")
    hosts = [str(ip) for ip in network.hosts()]; limit = min(int(disc.get("max_hosts", 256)), MAX_DISCOVERY_HOSTS)
    if len(hosts) > limit: raise ValueError(f"discovery range exceeds configured max_hosts={limit}")
    return hosts


async def poll_device(conn: sqlite3.Connection, device: dict[str, Any], net: NetSNMP | None = None) -> dict[str, Any]:
    net = net or NetSNMP(); started = utcnow(); conn.execute("UPDATE devices SET last_poll=?, updated_at=? WHERE device_id=?", (started, started, device["device_id"])); conn.commit()
    try:
        result = await asyncio.to_thread(net.query, "snmpget", device["management_address"], int(device["snmp_port"]), device["credential_reference"], list(STANDARD_OIDS.values()), timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES)
        for name, oid in STANDARD_OIDS.items():
            if oid in result: store_metric(conn, device["device_id"], oid, result[oid], name=name)
        now = utcnow(); conn.execute("UPDATE devices SET status='online', last_seen=?, last_success=?, last_error=NULL, updated_at=? WHERE device_id=?", (now, now, now, device["device_id"])); conn.commit(); return {"device_id": device["device_id"], "status": "online", "objects": len(result)}
    except Exception as exc:
        now = utcnow(); message = str(exc)[-1000:]; conn.execute("UPDATE devices SET status='offline', last_error=?, updated_at=? WHERE device_id=?", (message, now, device["device_id"])); conn.commit(); return {"device_id": device["device_id"], "status": "offline", "error": message}


async def poll_enabled(conn: sqlite3.Connection, concurrency: int = 16) -> list[dict[str, Any]]:
    devices = [get_device(conn, r["device_id"]) for r in conn.execute("SELECT device_id FROM devices WHERE polling_enabled=1")]; sem = asyncio.Semaphore(concurrency)
    async def run(d):
        async with sem: return await poll_device(conn, d)
    return await asyncio.gather(*(run(d) for d in devices))


def propose_action(conn: sqlite3.Connection, *, actor: str, action: str, target: str | None, reason: str, ai_involvement: bool = True, validation: dict[str, Any] | None = None, rollback: dict[str, Any] | None = None) -> dict[str, Any]:
    action_class = ACTION_CLASS.get(action, "DESTRUCTIVE"); state = "approved" if action_class in AUTO_ALLOWED and validation and rollback else "pending_review"; proposal_id = str(uuid.uuid4())
    conn.execute("INSERT INTO action_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?)", (proposal_id, utcnow(), actor, action, action_class, target, reason, state, json.dumps(validation or {}, sort_keys=True), json.dumps(rollback or {}, sort_keys=True), "{}")); conn.commit()
    audit(conn, actor=actor, source="ai" if ai_involvement else "api", action="action.propose", target=target, reason=reason, result=state, ai_involvement="proposal" if ai_involvement else "none", after={"proposal_id": proposal_id, "action": action, "class": action_class}, rollback=rollback or {})
    return {"proposal_id": proposal_id, "action": action, "action_class": action_class, "state": state}


def evidence_query(conn: sqlite3.Connection, question: str) -> dict[str, Any]:
    q = question.lower().strip(); evidence=[]; observations=[]; inferences=[]; recommendations=[]
    if "not respond" in q or "unreachable" in q or "offline" in q:
        rows = conn.execute("SELECT device_id,display_name,last_success,last_error FROM devices WHERE status='offline' ORDER BY updated_at DESC").fetchall(); evidence.extend({"type":"device","id":r["device_id"],"fields":dict(r)} for r in rows); observations.append(f"{len(rows)} managed device(s) are currently marked offline.")
        if rows: recommendations.append("Repoll affected devices and inspect upstream link or authentication evidence before changing configuration.")
    elif "reboot" in q:
        oid=STANDARD_OIDS["sysUpTime"]; rows=conn.execute("SELECT device_id,ts,value_num,value_text FROM metrics WHERE oid=? ORDER BY ts DESC LIMIT 100",(oid,)).fetchall(); evidence.extend({"type":"metric","id":f"{r['device_id']}:{r['ts']}","fields":dict(r)} for r in rows); observations.append(f"Reviewed {len(rows)} recent sysUpTime samples."); recommendations.append("Confirm uptime discontinuities against traps and service logs before concluding a reboot occurred.")
    elif "health" in q or "summary" in q:
        total=conn.execute("SELECT count(*) FROM devices").fetchone()[0]; online=conn.execute("SELECT count(*) FROM devices WHERE status='online'").fetchone()[0]; alerts=conn.execute("SELECT count(*) FROM alerts WHERE state='open'").fetchone()[0]; evidence.extend([{"type":"derived_metric","id":"managed_device_count","value":total},{"type":"derived_metric","id":"online_device_count","value":online},{"type":"derived_metric","id":"open_alert_count","value":alerts}]); observations.append(f"Managed devices: {total}; online: {online}; open alerts: {alerts}.")
        if total and online < total: inferences.append("One or more managed devices may require investigation; this is an inference from inventory status, not root-cause proof.")
    elif re.search(r"\b1(?:\.\d+){2,}\b", q):
        match=re.search(r"\b(1(?:\.\d+){2,})\b",q); oid=canonical_oid(match.group(1)) if match else ""; row=conn.execute("SELECT * FROM mib_objects WHERE oid=?",(oid,)).fetchone()
        if row: evidence.append({"type":"mib_object","id":oid,"fields":dict(row)}); observations.append(f"{oid} resolves to {row['name']} in {row['module'] or 'an indexed MIB'}.")
        else: observations.append(f"OID {oid} is not present in the local indexed MIB store."); recommendations.append("Import or validate the relevant vendor MIB, or use snmptranslate against the local MIB repository.")
    else: observations.append("The deterministic evidence layer does not have a specialized handler for this question."); recommendations.append("Use inventory, events, telemetry, MIB and incident evidence as context for the configured AI provider.")
    return {"question":question,"observed_facts":observations,"derived_metrics":[e for e in evidence if e.get("type")=="derived_metric"],"deterministic_rule_results":[],"ai_inferences":inferences,"recommended_actions":recommendations,"executed_actions":[],"evidence":evidence,"provider":"deterministic-evidence-layer","generated_at":utcnow()}


def health(conn: sqlite3.Connection) -> dict[str, Any]:
    return {"status":"ok","database":str(DB_PATH),"managed_devices":conn.execute("SELECT count(*) FROM devices").fetchone()[0],"online_devices":conn.execute("SELECT count(*) FROM devices WHERE status='online'").fetchone()[0],"active_alerts":conn.execute("SELECT count(*) FROM alerts WHERE state='open'").fetchone()[0],"recent_events":conn.execute("SELECT count(*) FROM events WHERE ts >= datetime('now','-1 hour')").fetchone()[0],"generated_at":utcnow()}


def cli() -> int:
    p=argparse.ArgumentParser(description="WW.CX Edge1 SNMP platform core"); p.add_argument("--db",type=Path,default=DB_PATH); sub=p.add_subparsers(dest="cmd",required=True); sub.add_parser("init-db"); sub.add_parser("health"); sub.add_parser("poll"); q=sub.add_parser("ai-query"); q.add_argument("question"); o=sub.add_parser("oid"); o.add_argument("value"); d=sub.add_parser("discovery-preview"); d.add_argument("cidr"); d.add_argument("--config",type=Path,default=CONFIG_PATH); args=p.parse_args(); conn=connect_db(args.db)
    if args.cmd=="init-db": print(json.dumps({"status":"initialized","db":str(args.db)})); return 0
    if args.cmd=="health": print(json.dumps(health(conn),sort_keys=True)); return 0
    if args.cmd=="poll":
        cfg=load_config(); results=asyncio.run(poll_enabled(conn,int(cfg.get("polling",{}).get("concurrency",16)))); print(json.dumps(results,sort_keys=True)); return 0 if all(r["status"]=="online" for r in results) else 2
    if args.cmd=="ai-query": print(json.dumps(evidence_query(conn,args.question),sort_keys=True)); return 0
    if args.cmd=="oid": print(canonical_oid(args.value)); return 0
    if args.cmd=="discovery-preview": cfg=load_config(args.config); print(json.dumps(allowed_discovery_hosts(args.cidr,cfg))); return 0
    return 2

if __name__ == "__main__": raise SystemExit(cli())
