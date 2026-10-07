"""Database-backed Edge1 operator navigation registry.

The SQLite database is the runtime source of truth. JSON is an exported browser
contract only; navigation never grants authorization.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

CONTRACT = "wwcx.edge1-operator-navigation.v1"
SCHEMA_VERSION = 1
ALLOWED_THEMES = {"inherit", "light", "dark"}
ALLOWED_ICONS = {
    "home", "contacts", "sparkles", "phone-book", "shield", "firewall", "network",
    "route", "dns", "bitcoin", "pickaxe", "clock", "release", "backup", "mail-shield",
    "mail", "messages", "sms", "phone-call", "link", "newspaper", "brain", "cookie",
    "settings", "navigation", "change", "history", "circle",
}
SAFETY_DEFAULTS = {
    "navigation_grants_authorization": False,
    "generic_execution_authorized": False,
    "production_traffic_authorized": False,
    "mutations_enabled": False,
    "unknown_status_is_healthy": False,
}
UI_DEFAULTS = {
    "version": 3,
    "navigation_model": "database_generated",
    "render_upcoming_modules": True,
    "dashboard_source": "same_registry",
    "badges_source": "availability_and_status",
    "search_source": "same_registry",
    "toolbox_source": "same_registry",
}

DDL = """
CREATE TABLE IF NOT EXISTS navigation_meta (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS navigation_modules (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  section TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  browser_route TEXT,
  candidate_route TEXT,
  runtime_route TEXT,
  availability TEXT NOT NULL,
  authorization TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  palette INTEGER NOT NULL DEFAULT 0 CHECK (palette IN (0,1)),
  toolbox INTEGER NOT NULL DEFAULT 0 CHECK (toolbox IN (0,1)),
  evidence_status TEXT NOT NULL,
  menu_visibility TEXT NOT NULL,
  dashboard_visibility INTEGER NOT NULL DEFAULT 1 CHECK (dashboard_visibility IN (0,1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
  icon TEXT NOT NULL DEFAULT 'circle',
  theme TEXT NOT NULL DEFAULT 'inherit' CHECK (theme IN ('inherit','light','dark')),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS navigation_modules_order_idx
  ON navigation_modules(enabled, sort_order, section, label);
"""

FIELDS = (
    "id", "label", "section", "sort_order", "browser_route", "candidate_route",
    "runtime_route", "availability", "authorization", "description", "palette",
    "toolbox", "evidence_status", "menu_visibility", "dashboard_visibility",
    "enabled", "icon", "theme",
)


def connect(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=10)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(navigation_modules)")}
    if "icon" not in columns:
        conn.execute("ALTER TABLE navigation_modules ADD COLUMN icon TEXT NOT NULL DEFAULT 'circle'")
    conn.commit()


def _icon_for(module: dict[str, Any]) -> str:
    icon = str(module.get("icon") or "circle")
    if icon not in ALLOWED_ICONS:
        raise ValueError(f"unsupported icon for {module.get('id')}: {icon}")
    return icon


def _theme_for(module: dict[str, Any]) -> str:
    theme = str(module.get("theme") or "inherit")
    if theme not in ALLOWED_THEMES:
        raise ValueError(f"unsupported theme for {module.get('id')}: {theme}")
    return theme


def import_registry(conn: sqlite3.Connection, registry: dict[str, Any], *, replace: bool = False) -> None:
    if registry.get("contract") != CONTRACT:
        raise ValueError("unexpected navigation contract")
    migrate(conn)
    safety = registry.get("safety") or SAFETY_DEFAULTS
    if safety != SAFETY_DEFAULTS:
        raise ValueError("navigation safety contract must remain fail-closed")
    if replace:
        conn.execute("DELETE FROM navigation_modules")
    meta = {
        "contract": CONTRACT,
        "schema_version": int(registry.get("schema_version", SCHEMA_VERSION)),
        "source_issue": registry.get("source_issue"),
        "safety": safety,
        "ui": registry.get("ui") or UI_DEFAULTS,
    }
    for key, value in meta.items():
        conn.execute(
            "INSERT INTO navigation_meta(key,value_json) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
            (key, json.dumps(value, separators=(",", ":"))),
        )
    sql = """INSERT INTO navigation_modules(
      id,label,section,sort_order,browser_route,candidate_route,runtime_route,
      availability,authorization,description,palette,toolbox,evidence_status,
      menu_visibility,dashboard_visibility,enabled,icon,theme,updated_at
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
    ON CONFLICT(id) DO UPDATE SET
      label=excluded.label, section=excluded.section, sort_order=excluded.sort_order,
      browser_route=excluded.browser_route, candidate_route=excluded.candidate_route,
      runtime_route=excluded.runtime_route, availability=excluded.availability,
      authorization=excluded.authorization, description=excluded.description,
      palette=excluded.palette, toolbox=excluded.toolbox,
      evidence_status=excluded.evidence_status, menu_visibility=excluded.menu_visibility,
      dashboard_visibility=excluded.dashboard_visibility, enabled=excluded.enabled,
      icon=excluded.icon, theme=excluded.theme, updated_at=CURRENT_TIMESTAMP"""
    for module in registry.get("modules", []):
        values = (
            module["id"], module["label"], module["section"], int(module["sort_order"]),
            module.get("browser_route"), module.get("candidate_route"), module.get("runtime_route"),
            module["availability"], module["authorization"], module.get("description", ""),
            int(bool(module.get("palette"))), int(bool(module.get("toolbox"))),
            module["evidence_status"], module["menu_visibility"],
            int(bool(module.get("dashboard_visibility", True))),
            int(bool(module.get("enabled", True))), _icon_for(module), _theme_for(module),
        )
        conn.execute(sql, values)
    conn.commit()


def _meta(conn: sqlite3.Connection, key: str, default: Any) -> Any:
    row = conn.execute("SELECT value_json FROM navigation_meta WHERE key=?", (key,)).fetchone()
    return default if row is None else json.loads(row[0])


def export_registry(conn: sqlite3.Connection, *, include_disabled: bool = False) -> dict[str, Any]:
    where = "" if include_disabled else "WHERE enabled=1"
    rows = conn.execute(
        f"SELECT {','.join(FIELDS)} FROM navigation_modules {where} ORDER BY sort_order, section, label, id"
    ).fetchall()
    modules = []
    for row in rows:
        item = dict(row)
        for key in ("palette", "toolbox", "dashboard_visibility", "enabled"):
            item[key] = bool(item[key])
        modules.append(item)
    return {
        "schema_version": _meta(conn, "schema_version", SCHEMA_VERSION),
        "contract": _meta(conn, "contract", CONTRACT),
        "source_issue": _meta(conn, "source_issue", None),
        "safety": _meta(conn, "safety", SAFETY_DEFAULTS),
        "modules": modules,
        "ui": {**UI_DEFAULTS, **(_meta(conn, "ui", {}) or {}), "navigation_model": "database_generated"},
        "generated": {"source": "sqlite", "disabled_modules_omitted": not include_disabled},
    }


def atomic_write_json(path: Path, payload: dict[str, Any], *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def set_enabled(conn: sqlite3.Connection, module_id: str, enabled: bool) -> None:
    cur = conn.execute(
        "UPDATE navigation_modules SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (int(enabled), module_id),
    )
    if cur.rowcount != 1:
        raise KeyError(module_id)
    conn.commit()


def set_theme(conn: sqlite3.Connection, module_id: str, theme: str) -> None:
    if theme not in ALLOWED_THEMES:
        raise ValueError(theme)
    cur = conn.execute(
        "UPDATE navigation_modules SET theme=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (theme, module_id),
    )
    if cur.rowcount != 1:
        raise KeyError(module_id)
    conn.commit()
