#!/usr/bin/env python3
"""Read-only BigBird Edge1 connector lifecycle manager.

This component manages connection state only. It does not enable mutation
operations, execute arbitrary commands, or bypass the Edge1 Operations API.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

CONFIG = Path("config/bigbird-edge1-connector.json")
STATE = Path("/var/lib/bigbird-edge1-connector/restart-state.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def load_state():
    if not STATE.exists():
        return {
            "restart_count": 0,
            "interval_minutes": 360,
            "updated_at": utc_now(),
        }
    return json.loads(STATE.read_text(encoding="utf-8"))


def next_restart(state):
    cfg = load_config()["restart_policy"]
    return min(
        state["interval_minutes"] + cfg["increment_minutes"],
        cfg["maximum_interval_minutes"],
    )


if __name__ == "__main__":
    print(json.dumps({
        "status": "ready",
        "mode": load_config()["mode"],
        "state": load_state(),
        "checked_at": utc_now(),
        "next_interval_minutes": next_restart(load_state()),
    }, indent=2))
