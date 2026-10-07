"""Bounded administration layer for the Edge1 navigation registry."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .edge1_navigation_registry import ALLOWED_ICONS, atomic_write_json, connect, export_registry, migrate

DEFAULT_DB = Path('/var/lib/edge1-navigation/navigation.sqlite3')
DEFAULT_OUTPUT = Path('/var/www/edge1-status/operator-shell/navigation.json')
ALLOWED_THEMES = {'inherit','light','dark'}
ALLOWED_MENU_VISIBILITY = {'primary','live','upcoming','hidden'}
FORBIDDEN_ROUTE_PARTS = ('/api/','/actions/','/callback','/include','/private/','/src/')
MODULE_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,63}$')
EDITABLE_FIELDS = {
    'enabled','label','section','sort_order','browser_route','theme','icon',
    'menu_visibility','dashboard_visibility','toolbox','palette','description'
}

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS navigation_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  request_id TEXT NOT NULL,
  changed_fields_json TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS navigation_audit_module_idx
  ON navigation_audit(module_id, id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def ensure_admin_schema(conn: sqlite3.Connection) -> None:
    migrate(conn)
    conn.executescript(AUDIT_DDL)


def list_modules(db: Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with connect(db, read_only=True) as conn:
        rows = conn.execute(
            "SELECT * FROM navigation_modules ORDER BY sort_order,section,label,id"
        ).fetchall()
        out=[]
        for row in rows:
            item=dict(row)
            for key in ('palette','toolbox','dashboard_visibility','enabled'):
                item[key]=bool(item[key])
            out.append(item)
        return out


def list_audit(db: Path = DEFAULT_DB, limit: int = 50) -> list[dict[str, Any]]:
    limit=max(1,min(int(limit),200))
    with connect(db, read_only=True) as conn:
        try:
            rows=conn.execute(
                "SELECT id,module_id,actor,request_id,changed_fields_json,created_at "
                "FROM navigation_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    result=[]
    for row in rows:
        item=dict(row)
        item['changed_fields']=json.loads(item.pop('changed_fields_json'))
        result.append(item)
    return result


def _clean_text(name: str, value: Any, maximum: int) -> str:
    if not isinstance(value,str):
        raise ValueError(f'{name} must be text')
    value=value.strip()
    if not value or len(value)>maximum or any(ord(c)<32 for c in value):
        raise ValueError(f'{name} is invalid')
    return value


def _validate_route(value: Any) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value,str) or len(value)>512 or not value.startswith('/') or value.startswith('//'):
        raise ValueError('browser_route is invalid')
    lower=value.lower()
    if any(part in lower for part in FORBIDDEN_ROUTE_PARTS):
        raise ValueError('browser_route targets an implementation/API path')
    return value


def _normalize_patch(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    unknown=set(patch)-EDITABLE_FIELDS-{'confirm_route_change'}
    if unknown:
        raise ValueError('unsupported fields: '+','.join(sorted(unknown)))
    if not (set(patch)&EDITABLE_FIELDS):
        raise ValueError('no editable fields supplied')
    clean: dict[str,Any]={}
    if 'enabled' in patch:
        if not isinstance(patch['enabled'],bool): raise ValueError('enabled must be boolean')
        clean['enabled']=int(patch['enabled'])
    if 'label' in patch: clean['label']=_clean_text('label',patch['label'],160)
    if 'section' in patch: clean['section']=_clean_text('section',patch['section'],120)
    if 'description' in patch:
        if not isinstance(patch['description'],str) or len(patch['description'])>1000:
            raise ValueError('description is invalid')
        clean['description']=patch['description'].strip()
    if 'sort_order' in patch:
        if isinstance(patch['sort_order'],bool) or not isinstance(patch['sort_order'],int) or not 0 <= patch['sort_order'] <= 10000:
            raise ValueError('sort_order must be an integer from 0 to 10000')
        clean['sort_order']=patch['sort_order']
    if 'theme' in patch:
        if patch['theme'] not in ALLOWED_THEMES: raise ValueError('theme is invalid')
        clean['theme']=patch['theme']
    if 'icon' in patch:
        if patch['icon'] not in ALLOWED_ICONS: raise ValueError('icon is invalid')
        clean['icon']=patch['icon']
    if 'menu_visibility' in patch:
        if patch['menu_visibility'] not in ALLOWED_MENU_VISIBILITY: raise ValueError('menu_visibility is invalid')
        clean['menu_visibility']=patch['menu_visibility']
    for field in ('dashboard_visibility','toolbox','palette'):
        if field in patch:
            if not isinstance(patch[field],bool): raise ValueError(f'{field} must be boolean')
            clean[field]=int(patch[field])
    if 'browser_route' in patch:
        route=_validate_route(patch['browser_route'])
        if route != current.get('browser_route') and patch.get('confirm_route_change') is not True:
            raise ValueError('route change requires explicit confirmation')
        if route is not None and current.get('availability') != 'accepted_live':
            raise ValueError('only accepted_live modules may expose browser routes')
        clean['browser_route']=route
    return clean


def update_module(module_id: str, patch: dict[str, Any], *, actor: str, request_id: str,
                  db: Path = DEFAULT_DB, output: Path | None = DEFAULT_OUTPUT) -> dict[str, Any]:
    if not MODULE_ID_RE.fullmatch(module_id): raise ValueError('invalid module id')
    actor=_clean_text('actor',actor,128)
    request_id=_clean_text('request_id',request_id,160)
    with connect(db) as conn:
        ensure_admin_schema(conn)
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM navigation_modules WHERE id=?',(module_id,)).fetchone()
        if row is None:
            conn.rollback(); raise KeyError(module_id)
        before=dict(row)
        clean=_normalize_patch(before,patch)
        cols=list(clean)
        params=[clean[c] for c in cols]+[module_id]
        conn.execute(
            'UPDATE navigation_modules SET '+','.join(f'{c}=?' for c in cols)+',updated_at=CURRENT_TIMESTAMP WHERE id=?',
            params,
        )
        after=dict(conn.execute('SELECT * FROM navigation_modules WHERE id=?',(module_id,)).fetchone())
        changed=[c for c in cols if before.get(c)!=after.get(c)]
        if changed:
            conn.execute(
                'INSERT INTO navigation_audit(module_id,actor,request_id,changed_fields_json,before_json,after_json,created_at) '
                'VALUES(?,?,?,?,?,?,?)',
                (module_id,actor,request_id,json.dumps(changed,separators=(',',':')),
                 json.dumps(before,separators=(',',':')),json.dumps(after,separators=(',',':')),_now()),
            )
        conn.commit()
    with connect(db,read_only=True) as conn:
        registry=export_registry(conn)
    if output is not None:
        atomic_write_json(output,registry)
    for key in ('palette','toolbox','dashboard_visibility','enabled'):
        after[key]=bool(after[key])
    return {'module':after,'changed_fields':changed,'generated_modules':len(registry['modules'])}


def upsert_management_module(db: Path = DEFAULT_DB, output: Path = DEFAULT_OUTPUT) -> None:
    module={
      'id':'navigation-management','label':'Navigation Management','section':'Configuration','sort_order':151,
      'browser_route':'/edge1-ops/status/navigation-management/','candidate_route':'/edge1-ops/status/navigation-management/',
      'runtime_route':'/edge1-ops/status/navigation-management/','availability':'accepted_live','authorization':'authenticated_admin',
      'description':'Manage the database-backed Edge1 navigation registry, menu visibility, ordering, links and shell themes.',
      'palette':1,'toolbox':1,'evidence_status':'database_backed_admin_ui','menu_visibility':'primary',
      'dashboard_visibility':1,'enabled':1,'icon':'navigation','theme':'inherit'
    }
    with connect(db) as conn:
        ensure_admin_schema(conn)
        conn.execute('''INSERT INTO navigation_modules(
          id,label,section,sort_order,browser_route,candidate_route,runtime_route,availability,authorization,description,
          palette,toolbox,evidence_status,menu_visibility,dashboard_visibility,enabled,theme,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET label=excluded.label,section=excluded.section,sort_order=excluded.sort_order,
          browser_route=excluded.browser_route,candidate_route=excluded.candidate_route,runtime_route=excluded.runtime_route,
          availability=excluded.availability,authorization=excluded.authorization,description=excluded.description,
          palette=excluded.palette,toolbox=excluded.toolbox,evidence_status=excluded.evidence_status,
          menu_visibility=excluded.menu_visibility,dashboard_visibility=excluded.dashboard_visibility,enabled=excluded.enabled,
          icon=excluded.icon,theme=excluded.theme,updated_at=CURRENT_TIMESTAMP''', tuple(module[k] for k in (
            'id','label','section','sort_order','browser_route','candidate_route','runtime_route','availability','authorization','description',
            'palette','toolbox','evidence_status','menu_visibility','dashboard_visibility','enabled','icon','theme')))
        conn.commit()
    with connect(db,read_only=True) as conn: registry=export_registry(conn)
    atomic_write_json(output,registry)
