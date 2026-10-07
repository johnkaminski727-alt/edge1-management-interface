#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3
from collections import Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
SEC=Path('/var/lib/wwcx-mail-security/security.sqlite3')
STATUS=Path('/var/www/edge1-status/mail-learning/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')

def build():
    if not SEC.is_file(): raise RuntimeError('mail security database unavailable')
    with sqlite3.connect(f'file:{SEC}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        states={r['state']:r['n'] for r in db.execute('SELECT state,count(*) n FROM decisions GROUP BY state')}
        events={r['action']:r['n'] for r in db.execute('SELECT action,count(*) n FROM events GROUP BY action')}
        learning={r['classification']:{'total':r['n'],'completed':r['done']} for r in db.execute("SELECT classification,count(*) n,sum(CASE WHEN completed IS NOT NULL THEN 1 ELSE 0 END) done FROM learning GROUP BY classification")}
        reasons=Counter(); symbols=Counter(); overrides=Counter()
        for r in db.execute("SELECT state,payload,override FROM decisions WHERE state IN ('junk','quarantine')"):
            try:p=json.loads(r['payload'] or '{}')
            except Exception:p={}
            for reason in p.get('reasons') or []: reasons[str(reason)]+=1
            for symbol in p.get('symbols') or []: symbols[str(symbol)]+=1
            if r['override']: overrides[str(r['override']).split(':',1)[0]]+=1
    corrections={'spam':events.get('spam',0),'not_spam':events.get('not_spam',0),'phishing':events.get('phishing',0),'confirmed_phishing':events.get('confirmed_phishing',0),'manual_release':events.get('release',0)}
    recommendations=[]
    if corrections['not_spam']>=3: recommendations.append('Review recurring false-positive causes before changing thresholds.')
    if reasons.get('unregistered_catch_all_recipient_review',0)>=20: recommendations.append('Catch-all recipient review is a frequent quarantine cause; review registered-recipient inventory.')
    if corrections['phishing'] or corrections['confirmed_phishing']: recommendations.append('Review related phishing holds and indicator clusters; do not auto-release related messages.')
    result={'contract':'wwcx.mail-learning-intelligence.v1','generated_at':utcnow(),'states':states,'events':events,'learning':learning,'operator_corrections':corrections,'top_quarantine_reasons':reasons.most_common(20),'top_filter_symbols':symbols.most_common(20),'override_types':dict(overrides),'recommendations':recommendations,'thresholds_changed':False,'quarantine_release_authorized':False,'learning_mutation_performed':False}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2)+'\n'); STATUS.chmod(0o644)
    lines=['# Mail Learning Intelligence','',f"Generated: {result['generated_at']}",f"States: {json.dumps(states,sort_keys=True)}",f"Operator corrections: {json.dumps(corrections,sort_keys=True)}",'', '## Top quarantine reasons','']
    lines += [f'- {n} × `{reason}`' for reason,n in result['top_quarantine_reasons']] or ['- None.']
    lines += ['','## Recommendations',''] + ([f'- {x}' for x in recommendations] or ['- No learning-policy review recommended currently.'])
    lines += ['','This bot never releases quarantine or changes spam/security thresholds automatically.']
    upsert_library_document(LIB,ROOT,'operations/mail-learning/current.md','Mail Learning Intelligence','\n'.join(lines)+'\n')
    return result
if __name__=='__main__':
    d=build(); print(json.dumps({'states':d['states'],'operator_corrections':d['operator_corrections'],'recommendations':len(d['recommendations'])},sort_keys=True))
