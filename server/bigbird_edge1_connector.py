#!/usr/bin/env python3
"""Read-only BigBird Edge1 connector lifecycle manager.

The connector authenticates to the loopback Edge1 Operations API, discovers
its action inventory, verifies the public health endpoint, and persists a
bounded local state record. It never executes actions or enables mutations.
"""

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(os.environ.get("BIGBIRD_EDGE1_ROOT", "/opt/edge1-management-interface"))
CONFIG = Path(os.environ.get("BIGBIRD_EDGE1_CONFIG", str(ROOT / "config/bigbird-edge1-connector.json")))
STATE_DIR = Path(os.environ.get("BIGBIRD_EDGE1_STATE_DIR", "/var/lib/bigbird-edge1-connector"))
STATE = STATE_DIR / "restart-state.json"
AUDIT = STATE_DIR / "audit.jsonl"
SECRET_FILE = Path(os.environ.get("BIGBIRD_EDGE1_SECRET_FILE", "/etc/edge1-operations-api.secret"))
ACTOR = os.environ.get("BIGBIRD_EDGE1_ACTOR", "bigbird-edge1-connector")
TIMEOUT = int(os.environ.get("BIGBIRD_EDGE1_TIMEOUT", "10"))


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat()


def load_config():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("mode") != "read_only":
        raise ValueError("connector mode must remain read_only")
    return config


def initial_state(config):
    now = utc_now()
    interval = int(config["restart_policy"]["initial_interval_minutes"])
    return {
        "version": 1,
        "restart_count": 0,
        "interval_minutes": interval,
        "last_attempt_at": None,
        "last_success_at": None,
        "next_due_at": iso(now),
        "health": None,
        "advertised_actions": [],
        "approved_actions": [],
        "unexpected_actions": [],
        "last_error": None,
        "updated_at": iso(now),
    }


def load_state(config):
    if not STATE.exists():
        return initial_state(config)
    value = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("connector state must be an object")
    return value


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def audit(event, **fields):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    record = {"created_at": iso(utc_now()), "event": event, **fields}
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    os.chmod(AUDIT, 0o600)


def read_secret():
    value = SECRET_FILE.read_bytes().strip()
    if len(value) < 32:
        raise ValueError("operations API secret must contain at least 32 bytes")
    return value


def signed_json(base_url, method, path, body=b""):
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(24)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, timestamp, nonce, ACTOR, body_hash)).encode()
    signature = hmac.new(read_secret(), canonical, hashlib.sha256).hexdigest()
    request = Request(
        base_url.rstrip("/") + path,
        data=body if method != "GET" else None,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-WWCX-Actor": ACTOR,
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Timestamp": timestamp,
            "X-WWCX-Signature": signature,
        },
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def public_health(base_url):
    request = Request(base_url.rstrip("/") + "/healthz", headers={"Accept": "application/json"})
    with urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def discover(config):
    health = public_health(config["base_url"])
    inventory = signed_json(config["base_url"], "GET", "/v1/actions")
    advertised = sorted(item["name"] for item in inventory.get("actions", []))
    enabled = sorted(config["enabled_tools"])
    disabled = set(config["disabled_tools"])
    unexpected = sorted(name for name in advertised if name not in enabled and name not in disabled)
    approved = sorted(name for name in advertised if name in enabled)
    return health, advertised, approved, unexpected


def next_interval(config, state):
    policy = config["restart_policy"]
    return min(
        int(state.get("interval_minutes", policy["initial_interval_minutes"])) + int(policy["increment_minutes"]),
        int(policy["maximum_interval_minutes"]),
    )


def is_due(state, now=None):
    now = now or utc_now()
    due = state.get("next_due_at")
    if not due:
        return True
    return now >= datetime.fromisoformat(due)


def refresh(force=False):
    config = load_config()
    state = load_state(config)
    now = utc_now()
    if not force and not is_due(state, now):
        return {"status": "not_due", "state": state}

    state["last_attempt_at"] = iso(now)
    state["updated_at"] = iso(now)
    audit("refresh_started", restart_count=state.get("restart_count", 0))
    try:
        health, advertised, approved, unexpected = discover(config)
        if health.get("status") != "ok":
            raise RuntimeError("operations API health is not ok")
        if health.get("mutations_enabled") is not False:
            raise RuntimeError("operations API mutations must remain disabled")
        missing = sorted(set(config["enabled_tools"]) - set(advertised))
        if missing:
            raise RuntimeError("required actions are missing: " + ", ".join(missing))
        if unexpected:
            raise RuntimeError("unexpected actions advertised: " + ", ".join(unexpected))

        interval = next_interval(config, state)
        state.update({
            "restart_count": int(state.get("restart_count", 0)) + 1,
            "interval_minutes": interval,
            "last_success_at": iso(now),
            "next_due_at": iso(now + timedelta(minutes=interval)),
            "health": health,
            "advertised_actions": advertised,
            "approved_actions": approved,
            "unexpected_actions": [],
            "last_error": None,
            "updated_at": iso(now),
        })
        atomic_write(STATE, state)
        audit("refresh_succeeded", restart_count=state["restart_count"], interval_minutes=interval)
        return {"status": "ok", "state": state}
    except (OSError, ValueError, RuntimeError, HTTPError, URLError, json.JSONDecodeError) as exc:
        state.update({"last_error": str(exc), "updated_at": iso(now)})
        atomic_write(STATE, state)
        audit("refresh_failed", error=str(exc))
        raise


def validate():
    config = load_config()
    policy = config["restart_policy"]
    if policy.get("restart_scope") != "connector_only":
        raise ValueError("restart scope must remain connector_only")
    if int(policy["initial_interval_minutes"]) < 60:
        raise ValueError("initial interval is unexpectedly aggressive")
    if int(policy["maximum_interval_minutes"]) > 720:
        raise ValueError("maximum interval exceeds twelve hours")
    overlap = set(config["enabled_tools"]) & set(config["disabled_tools"])
    if overlap:
        raise ValueError("enabled and disabled tools overlap")
    return {"status": "valid", "mode": config["mode"], "enabled_tools": sorted(config["enabled_tools"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "validate", "refresh"), nargs="?", default="status")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        result = validate()
    elif args.command == "refresh":
        result = refresh(force=args.force)
    else:
        config = load_config()
        result = {"status": "ready", "mode": config["mode"], "state": load_state(config)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
