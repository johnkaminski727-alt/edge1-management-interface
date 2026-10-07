#!/usr/bin/env python3
from __future__ import annotations
import json, os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'server'))
from tools.automation.automation_common import utcnow, upsert_library_document
from server.private_ai_browser_worker import QUEUE_URL, post, queue_headers, verify_queue_response
STATUS=Path('/var/www/edge1-status/ava-quality/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
WORKER_ID='ava-quality-edge1'
def fetch(window_days=7):
    secret=os.environ.get('BB_BROWSER_WORKER_SECRET','');key_id=os.environ.get('BB_BROWSER_WORKER_KEY_ID','')
    if not secret or not key_id: raise RuntimeError('Ava quality worker credentials unavailable')
    body=json.dumps({'action':'quality_status','worker_id':WORKER_ID,'window_days':max(1,min(int(window_days),30))},separators=(',',':'),sort_keys=True).encode()
    headers,nonce=queue_headers(body,secret,key_id,QUEUE_URL)
    payload=verify_queue_response(post(QUEUE_URL,body,headers,20.0,262144),nonce,secret)
    if not isinstance(payload,dict) or payload.get('contract')!='wwcx.ava-quality-status.v1': raise RuntimeError('invalid Ava quality contract')
    if payload.get('content_included') is not False or payload.get('user_identifiers_included') is not False or payload.get('request_identifiers_included') is not False or payload.get('mutation_authorized') is not False:
        raise RuntimeError('Ava quality response violated metadata-only boundary')
    return payload
def build(window_days=7):
    remote=fetch(window_days); metrics=remote.get('metrics') or {}; recommendations=[str(x)[:240] for x in (remote.get('recommendations') or [])[:12]]
    result={'contract':'wwcx.ava-quality-control.v1','generated_at':utcnow(),'source_generated_at':remote.get('generated_at'),'window_days':remote.get('window_days'),'state':remote.get('state','attention'),'metrics':{k:max(0,int(v or 0)) for k,v in metrics.items()},'failure_codes':remote.get('failure_codes') or [],'recommendations':recommendations,'content_included':False,'user_identifiers_included':False,'request_identifiers_included':False,'mutation_performed':False}
    STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(result,indent=2)+'\n');STATUS.chmod(0o644)
    m=result['metrics']; lines=['# Ava Quality Control','',f"Generated: {result['generated_at']}",f"Window: {result['window_days']} days · state: **{result['state']}**",'', '## Completion evidence','',f"- Completed: **{m.get('completed',0)}**",f"- Source-backed completions: **{m.get('completed_with_evidence',0)}**",f"- Zero-evidence completions: **{m.get('completed_zero_evidence',0)}**",f"- Read-routed completions: **{m.get('read_routed',0)}**; zero evidence: **{m.get('read_routed_zero_evidence',0)}**",f"- Mail-routed completions: **{m.get('mail_routed',0)}**; zero Mail Room sources: **{m.get('mail_routed_zero_sources',0)}**",f"- Failed requests: **{m.get('failed',0)}**",'', '## Recommendations','']
    lines += [f'- {x}' for x in recommendations] or ['- No QA review recommendation in the current window.']
    lines += ['','Only aggregate routing/evidence/error metadata is inspected. Prompt text, answer text, user identifiers and request IDs are excluded.']
    upsert_library_document(LIB,ROOT,'operations/ava-quality/current.md','Ava Quality Control','\n'.join(lines)+'\n')
    return result
if __name__=='__main__':
    d=build(int(os.environ.get('AVA_QUALITY_WINDOW_DAYS','7')));print(json.dumps({'state':d['state'],'window_days':d['window_days'],'metrics':d['metrics'],'recommendations':len(d['recommendations'])},sort_keys=True))
