#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
SOURCE=Path('/var/www/edge1-status/outstanding-actions/status.json')
STATE=Path('/var/lib/edge1-action-lifecycle/lifecycle.sqlite3')
STATUS=Path('/var/www/edge1-status/action-lifecycle/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
DDL='''CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,source TEXT,priority TEXT,title TEXT,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,resolved_at TEXT,payload_json TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_actions_resolved ON actions(resolved_at,last_seen);'''
def run(source=SOURCE,state=STATE,now=None):
    now=now or datetime.now(timezone.utc); stamp=now.isoformat(); data=json.loads(source.read_text()); current={str(x['id']):x for x in data.get('actions',[]) if x.get('id')}; state.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(state) as db:
        db.row_factory=sqlite3.Row; db.executescript(DDL)
        active_before={r['id'] for r in db.execute('SELECT id FROM actions WHERE resolved_at IS NULL')}
        new_ids=set(current)-active_before
        resolved_ids=active_before-set(current)
        reopened=[]
        for ident,item in current.items():
            old=db.execute('SELECT resolved_at FROM actions WHERE id=?',(ident,)).fetchone()
            if old and old['resolved_at']: reopened.append(ident)
            db.execute('''INSERT INTO actions(id,source,priority,title,first_seen,last_seen,resolved_at,payload_json) VALUES(?,?,?,?,?,?,NULL,?)
              ON CONFLICT(id) DO UPDATE SET source=excluded.source,priority=excluded.priority,title=excluded.title,last_seen=excluded.last_seen,resolved_at=NULL,payload_json=excluded.payload_json''',(ident,item.get('source'),item.get('priority'),item.get('title'),stamp,stamp,json.dumps(item,sort_keys=True)))
        for ident in resolved_ids: db.execute('UPDATE actions SET resolved_at=? WHERE id=? AND resolved_at IS NULL',(stamp,ident))
        cutoff=(now-timedelta(days=7)).isoformat()
        recent=[dict(r) for r in db.execute('SELECT id,source,priority,title,resolved_at FROM actions WHERE resolved_at>=? ORDER BY resolved_at DESC LIMIT 100',(cutoff,))]
        persistent=[dict(r) for r in db.execute('SELECT id,source,priority,title,first_seen,last_seen FROM actions WHERE resolved_at IS NULL ORDER BY first_seen LIMIT 200')]
        db.commit()
    return {'contract':'wwcx.action-lifecycle.v1','generated_at':stamp,'summary':{'active':len(current),'new':len(new_ids),'resolved_this_run':len(resolved_ids),'reopened':len(reopened),'resolved_last_7d':len(recent)},'new_ids':sorted(new_ids),'resolved_ids':sorted(resolved_ids),'reopened_ids':sorted(reopened),'persistent':persistent,'recently_resolved':recent,'production_mutation_performed':False}
def markdown(d):
    s=d['summary']; lines=['# Outstanding Action Lifecycle','',f"Generated: {d['generated_at']}",f"Active: **{s['active']}** · New: **{s['new']}** · Resolved this run: **{s['resolved_this_run']}** · Resolved in 7 days: **{s['resolved_last_7d']}**",'', '## Newly observed','']
    lines += [f'- `{x}`' for x in d['new_ids']] or ['- None.']; lines += ['','## Resolved this run','']; lines += [f'- `{x}`' for x in d['resolved_ids']] or ['- None.']; lines += ['','Lifecycle state is observational; resolving an item here never performs the underlying action.']; return '\n'.join(lines)+'\n'
def main():
    d=run(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/action-lifecycle/current.md','Outstanding Action Lifecycle',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
