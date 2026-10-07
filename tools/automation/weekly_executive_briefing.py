#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3'); OUT=Path('/var/www/edge1-status/executive-briefing/status.json')
def load(path):
    try:return json.loads(Path(path).read_text())
    except Exception:return {}
def build():
    sources={
      'actions':load('/var/www/edge1-status/outstanding-actions/status.json'),
      'backup':load('/var/www/edge1-status/backup-verification/status.json'),
      'drift':load('/var/www/edge1-status/drift-monitor/status.json'),
      'documents':load('/var/www/edge1-status/document-filing/status.json'),
      'certificates':load('/var/www/edge1-status/certificate-expiry/status.json'),
      'storage':load('/var/www/edge1-status/storage-health/status.json'),
      'automation':load('/var/www/edge1-status/automation-center/inventory.json'),
      'api':load('/var/www/edge1-status/api-directory/inventory.json'),
    }
    return {'contract':'wwcx.executive-briefing.v1','generated_at':utcnow(),'summary':{'outstanding_actions':sources['actions'].get('summary',{}).get('total'),'high_actions':sources['actions'].get('summary',{}).get('high'),'backup_state':sources['backup'].get('state','unknown'),'drift_findings':sources['drift'].get('summary',{}).get('findings'),'documents_indexed':sources['documents'].get('indexed'),'certificate_state':sources['certificates'].get('state','unknown'),'storage_state':sources['storage'].get('state','unknown'),'automation_failures':sources['automation'].get('summary',{}).get('failed_or_non_success'),'live_api_listeners':sources['api'].get('summary',{}).get('live_api_listeners')},'sources_available':{k:bool(v) for k,v in sources.items()}}
def md(d):
    s=d['summary']; lines=['# Ava Weekly Executive Briefing','',f"Generated: {d['generated_at']}",'', '## At a glance','',f"- Outstanding actions: **{s['outstanding_actions']}**; high priority: **{s['high_actions']}**",f"- Backup/restore posture: **{s['backup_state']}**",f"- Drift findings: **{s['drift_findings']}**",f"- Documents indexed by filing bot: **{s['documents_indexed']}**",f"- Certificate/key posture: **{s['certificate_state']}**",f"- Storage/database posture: **{s['storage_state']}**",f"- Automation failures/non-success: **{s['automation_failures']}**",f"- Live API listeners inventoried: **{s['live_api_listeners']}**",'', '## Source availability','',f"`{json.dumps(d['sources_available'],sort_keys=True)}`",'', 'Use the underlying Ava operations documents for details and evidence. This briefing does not authorize changes.']
    return '\n'.join(lines)+'\n'
def main():
    d=build(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(d,indent=2)+'\n'); OUT.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/executive-briefings/current-week.md','Ava Weekly Executive Briefing',md(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__': main()
