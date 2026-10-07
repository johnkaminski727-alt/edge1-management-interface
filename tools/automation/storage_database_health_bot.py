#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, sqlite3
from pathlib import Path
from datetime import datetime, timezone
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/storage-health/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
DBS=[Path('/var/lib/wwcx-mail-room/correspondence.sqlite3'),Path('/var/lib/wwcx-mail-security/security.sqlite3'),Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'),Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite'),LIB]
def dbhealth(p):
    row={'path':str(p),'bytes':p.stat().st_size if p.exists() else None,'wal_bytes':Path(str(p)+'-wal').stat().st_size if Path(str(p)+'-wal').exists() else 0}
    if not p.exists(): return {**row,'state':'missing'}
    try:
        with sqlite3.connect(f'file:{p}?mode=ro',uri=True,timeout=10) as db: ok=db.execute('PRAGMA quick_check').fetchone()[0]
        row['state']='ok' if ok=='ok' else 'failed'
    except Exception as e: row.update(state='error',error_type=type(e).__name__)
    return row
def build():
    du=shutil.disk_usage('/'); pct=du.used/du.total*100; dbs=[dbhealth(p) for p in DBS]; attention=pct>=80 or any(x['state']!='ok' for x in dbs) or any((x.get('wal_bytes') or 0)>256*1024*1024 for x in dbs)
    return {'contract':'wwcx.storage-database-health.v1','generated_at':utcnow(),'state':'attention' if attention else 'healthy','filesystem':{'path':'/','total_bytes':du.total,'used_bytes':du.used,'free_bytes':du.free,'used_percent':round(pct,1)},'databases':dbs,'maintenance_performed':False,'recommendations':['Review any failed integrity check or WAL larger than 256 MiB before applying maintenance.'] if attention else []}
def md(d):
    lines=['# Storage & Database Health','',f"Generated: {d['generated_at']}",f"Root filesystem used: **{d['filesystem']['used_percent']}%**",'', '## Databases','']+[f"- `{x['path']}` — {x['state']} — {x['bytes']} bytes; WAL {x['wal_bytes']} bytes" for x in d['databases']]
    lines += ['','This pass is read-only; it does not VACUUM, delete archives, or checkpoint live databases automatically.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/storage-health/current.md','Storage & Database Health',md(d)); print(json.dumps({'state':d['state'],'used_percent':d['filesystem']['used_percent']},sort_keys=True))
if __name__=='__main__': main()
