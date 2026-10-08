#!/usr/bin/env python3
"""AVA operations intelligence: executive review, briefing, scorecards and cross-domain summaries.

This service is an observation/coordination projection. It never mutates Contacts,
Library evidence, accounting records, provider sources, or system services. The AVA
Office DB is the only mutable store and remains the executive coordination authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path('/opt/edge1-management-interface')
OFFICE = Path('/var/lib/wwcx-ava-office-manager/office-manager.sqlite3')
CONTACTS = Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
CATALOG = Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
AUTOMATION = Path('/var/www/edge1-status/automation-center/inventory.json')
OUTSTANDING = Path('/var/www/edge1-status/outstanding-actions/status.json')
TEMPLATES = ROOT / 'config/ava-workflow-templates.json'
CAPABILITIES = ROOT / 'config/ava-executive-capabilities.json'
STATUS = Path('/var/www/edge1-status/ava/operations-intelligence.json')

sys.path.insert(0, str(ROOT))
from server.ava_office_manager import OfficeManagerStore, utc_now  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hash_id(prefix: str, text: str) -> str:
    return prefix + '-' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def month_key(value: str | None) -> str | None:
    if not value or len(value) < 7:
        return None
    part = value[:7]
    try:
        datetime.strptime(part, '%Y-%m')
    except ValueError:
        return None
    return part


def months_between(first: str, last: str) -> list[str]:
    y, m = map(int, first.split('-'))
    ey, em = map(int, last.split('-'))
    out: list[str] = []
    while (y, m) <= (ey, em) and len(out) < 120:
        out.append(f'{y:04d}-{m:02d}')
        m += 1
        if m == 13:
            y += 1; m = 1
    return out


def category_for(source: str) -> str:
    s = source.lower()
    if 'mail' in s: return 'communications'
    if 'contact' in s: return 'contacts'
    if 'account' in s: return 'finance'
    if 'backup' in s or 'recovery' in s: return 'continuity'
    if 'security' in s or 'spamhaus' in s or 'suricata' in s or 'credential' in s: return 'security'
    if 'automation' in s or 'drift' in s or 'update' in s: return 'operations'
    return 'general'


def review_recommendation(action: dict[str, Any]) -> str:
    source = str(action.get('source') or '')
    level = str(action.get('action_level') or '')
    if level == 'AUTO-STAGE':
        return 'AVA may continue bounded preparation automatically; owner approval is not required unless a later policy gate is reached.'
    if source in {'automation', 'automation-watchdog'}:
        return 'AVA should use a registered remediation workflow first; owner review is required only after bounded retries are exhausted.'
    if source == 'contacts':
        return 'Review only the evidence-backed ambiguous/conflicting candidates; verified deterministic facts should remain automatic.'
    if source == 'mail':
        return 'Review the latest grouped notice and its preserved evidence before any external commitment or account action.'
    return 'Review the evidence and approve, decline, or delegate the next bounded action.'


def refresh_reviews(store: OfficeManagerStore, outstanding: dict[str, Any]) -> dict[str, int]:
    now = utc_now(); seen: set[str] = set(); inserted = updated = resolved = 0
    actions = outstanding.get('actions') if isinstance(outstanding.get('actions'), list) else []
    with store.connect() as db:
        for action in actions:
            if not isinstance(action, dict): continue
            ref = str(action.get('id') or '').strip()
            if not ref: continue
            seen.add(ref)
            rid = hash_id('review', 'outstanding-actions:' + ref)
            owner_required = str(action.get('action_level') or '') == 'REVIEW-REQUIRED'
            ref_lower = ref.lower()
            if ref in {'automation:watchdog','maintenance:failed-units','drift:git_working_tree','contacts:review'}:
                owner_required = False
            if ref == 'evidence:integrity':
                evidence_state = load_json(Path('/var/www/edge1-status/evidence-integrity/status.json'))
                owner_required = int((evidence_state.get('summary') or {}).get('high') or 0) > 0
            if str(action.get('source') or '') == 'mail' and str(action.get('notice_family') or '') == 'request-ready':
                owner_required = False
            if 'spamhaus' in ref_lower or 'suricata' in ref_lower:
                owner_required = True
            evidence = []
            if action.get('evidence'): evidence.append(action['evidence'])
            if isinstance(action.get('related_evidence'), list): evidence.extend(action['related_evidence'][:20])
            existing = db.execute('SELECT id FROM executive_reviews WHERE source_system=? AND source_ref=?', ('outstanding-actions', ref)).fetchone()
            db.execute('''INSERT INTO executive_reviews(id,source_system,source_ref,category,title,summary,severity,state,owner_required,recommended_action,evidence_json,first_seen_at_utc,updated_at_utc,resolved_at_utc)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
                          ON CONFLICT(source_system,source_ref) DO UPDATE SET category=excluded.category,title=excluded.title,summary=excluded.summary,severity=excluded.severity,state=excluded.state,owner_required=excluded.owner_required,recommended_action=excluded.recommended_action,evidence_json=excluded.evidence_json,updated_at_utc=excluded.updated_at_utc,resolved_at_utc=NULL''',
                       (rid,'outstanding-actions',ref,category_for(str(action.get('source') or '')),str(action.get('title') or ref)[:500],str(action.get('detail') or '')[:2000],str(action.get('priority') or 'medium'),'open',1 if owner_required else 0,review_recommendation(action),json.dumps(evidence,sort_keys=True),now,now))
            if existing: updated += 1
            else: inserted += 1
        active = db.execute("SELECT source_ref FROM executive_reviews WHERE source_system='outstanding-actions' AND state='open'").fetchall()
        for row in active:
            if str(row['source_ref']) not in seen:
                db.execute("UPDATE executive_reviews SET state='resolved',resolved_at_utc=?,updated_at_utc=? WHERE source_system='outstanding-actions' AND source_ref=?", (now,now,row['source_ref']))
                resolved += 1
        # Existing AVA action proposals are part of the same review experience.
        proposals = db.execute("SELECT id,capability,summary,authority_class,authorization,reason,status,updated_at_utc FROM action_proposals WHERE status IN ('awaiting_confirmation','blocked','approved')").fetchall()
        for row in proposals:
            ref = str(row['id']); rid = hash_id('review','action-proposal:'+ref)
            owner = row['status'] in {'awaiting_confirmation','blocked'}
            db.execute('''INSERT INTO executive_reviews(id,source_system,source_ref,category,title,summary,severity,state,owner_required,recommended_action,evidence_json,first_seen_at_utc,updated_at_utc,resolved_at_utc)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
                          ON CONFLICT(source_system,source_ref) DO UPDATE SET title=excluded.title,summary=excluded.summary,severity=excluded.severity,state=excluded.state,owner_required=excluded.owner_required,recommended_action=excluded.recommended_action,updated_at_utc=excluded.updated_at_utc,resolved_at_utc=NULL''',
                       (rid,'action-proposal',ref,'approval',str(row['summary'])[:500],str(row['reason'])[:2000],'high' if row['authority_class'] in {'restricted','attended','conditional'} else 'medium','open',1 if owner else 0,'Approve or decline through the existing bounded authority gate; AVA cannot bypass this control.', '[]',str(row['updated_at_utc'] or now),now))
    return {'inserted':inserted,'updated':updated,'resolved':resolved}


def maturity(action_level: str, runs: int, success_rate: float | None, failures: int) -> tuple[str, str]:
    level = action_level.upper()
    if level == 'READ-ONLY': return 'Observe', 'Read-only observer; no promotion needed for mutation authority.'
    if level == 'REVIEW-REQUIRED': return 'Recommend', 'Prepares findings and escalates decisions; keep review gate unless policy explicitly changes.'
    if level == 'AUTO-STAGE':
        if runs >= 20 and (success_rate or 0) >= .98 and failures <= 1:
            return 'Prepare', 'Strong staging reliability; eligible for policy review before any additional autonomous authority.'
        return 'Prepare', 'May prepare/stage bounded work but does not independently cross approval boundaries.'
    if level == 'AUTO-FIX':
        if runs >= 20 and (success_rate or 0) >= .98 and failures <= 1:
            return 'Verified Auto', 'High observed reliability inside its existing bounded AUTO-FIX authority.'
        return 'Routine Auto', 'May perform its registered routine remediation; continue measuring before Verified Auto status.'
    return 'Observe', 'No broader autonomous maturity has been established.'


def record_timer_observations(store: OfficeManagerStore, automation: dict[str,Any]) -> int:
    now=utc_now(); inserted=0
    timers=automation.get('timers') if isinstance(automation.get('timers'),list) else []
    by_timer={str(t.get('timer')):t for t in timers if isinstance(t,dict) and t.get('timer')}
    with store.connect() as db:
        members=db.execute('SELECT member_id,timer_unit FROM executive_team_members WHERE active=1 AND timer_unit IS NOT NULL').fetchall()
        for member in members:
            timer=by_timer.get(str(member['timer_unit']))
            if not timer or not timer.get('last_run'): continue
            run_ref=str(timer['last_run']); raw=str(timer.get('last_result') or 'unknown')
            result='success' if raw in {'success','done'} and str(timer.get('exit_status') or '0') in {'0',''} else ('failure' if raw not in {'success','done','unknown'} else raw)
            cur=db.execute('INSERT OR IGNORE INTO executive_team_run_observations(member_id,run_ref,result,observed_at_utc) VALUES(?,?,?,?)',(member['member_id'],run_ref,result,now))
            if cur.rowcount: inserted+=1
    return inserted


def refresh_team_metrics(store: OfficeManagerStore) -> int:
    now=utc_now(); count=0
    with store.connect() as db:
        members=db.execute('SELECT member_id,action_level FROM executive_team_members WHERE active=1').fetchall()
        for member in members:
            mid=str(member['member_id'])
            rows=db.execute('SELECT state,attempt_count,finished_at_utc FROM executive_workflow_steps WHERE member_id=?',(mid,)).fetchall()
            obs=db.execute('SELECT result,run_ref FROM executive_team_run_observations WHERE member_id=?',(mid,)).fetchall()
            workflow_runs=len(rows); workflow_success=sum(1 for r in rows if r['state']=='completed'); workflow_failures=sum(1 for r in rows if r['state'] in {'failed','blocked'})
            observed_runs=len(obs); observed_success=sum(1 for r in obs if r['result']=='success'); observed_failures=sum(1 for r in obs if r['result']=='failure')
            runs=workflow_runs+observed_runs; success=workflow_success+observed_success; failures=workflow_failures+observed_failures; retries=sum(max(0,int(r['attempt_count'] or 0)-1) for r in rows)
            rate=(success/runs) if runs else None
            last_success=max([str(r['finished_at_utc']) for r in rows if r['state']=='completed' and r['finished_at_utc']]+[str(r['run_ref']) for r in obs if r['result']=='success'], default=None)
            last_failure=max([str(r['finished_at_utc']) for r in rows if r['state'] in {'failed','blocked'} and r['finished_at_utc']]+[str(r['run_ref']) for r in obs if r['result']=='failure'], default=None)
            mat,rec=maturity(str(member['action_level']),runs,rate,failures)
            db.execute('''INSERT INTO executive_team_metrics(member_id,maturity_level,run_count,success_count,failure_count,retry_count,success_rate,last_success_at_utc,last_failure_at_utc,recommendation,updated_at_utc)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET maturity_level=excluded.maturity_level,run_count=excluded.run_count,success_count=excluded.success_count,failure_count=excluded.failure_count,retry_count=excluded.retry_count,success_rate=excluded.success_rate,last_success_at_utc=excluded.last_success_at_utc,last_failure_at_utc=excluded.last_failure_at_utc,recommendation=excluded.recommendation,updated_at_utc=excluded.updated_at_utc''',
                       (mid,mat,runs,success,failures,retries,rate,last_success,last_failure,rec,now)); count+=1
    return count


def refresh_source_health(store: OfficeManagerStore) -> dict[str,int]:
    nowdt=datetime.now(timezone.utc); now=utc_now(); stats=Counter()
    if not CATALOG.is_file(): return {'missing_catalog':1}
    src=sqlite3.connect(CATALOG); src.row_factory=sqlite3.Row
    rows=src.execute('SELECT id,provider,name,runtime_access,last_sync_at,last_status,last_error,enabled FROM library_sources WHERE enabled=1 ORDER BY provider,name').fetchall(); src.close()
    with store.connect() as db:
        for r in rows:
            last=parse_dt(r['last_sync_at']); age=((nowdt-last).total_seconds()/3600) if last else None
            expected=2.0 if r['runtime_access']=='connector_required' else 6.0
            raw=str(r['last_status'] or 'unknown')
            if raw in {'error','failed'}: state='error'; issue=str(r['last_error'] or 'source reported an error')
            elif raw=='deferred': state='deferred'; issue='Source is registered but its server-side connector/bridge is not currently autonomous.'
            elif age is None: state='unknown'; issue='No successful synchronization timestamp is available.'
            elif age > expected*2: state='stale'; issue=f'No source synchronization observed for {age:.1f} hours; expected within about {expected:.1f} hours.'
            else: state='healthy'; issue=None
            stats[state]+=1
            db.execute('''INSERT INTO executive_source_health(source_id,provider,name,state,last_sync_at_utc,age_hours,expected_hours,issue,updated_at_utc)
                          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET provider=excluded.provider,name=excluded.name,state=excluded.state,last_sync_at_utc=excluded.last_sync_at_utc,age_hours=excluded.age_hours,expected_hours=excluded.expected_hours,issue=excluded.issue,updated_at_utc=excluded.updated_at_utc''',
                       (r['id'],r['provider'],r['name'],state,r['last_sync_at'],age,expected,issue,now))
    return dict(stats)


def refresh_accounting_completeness(store: OfficeManagerStore) -> dict[str,int]:
    now=utc_now(); stats=Counter()
    if not CATALOG.is_file(): return {'missing_catalog':1}
    db=sqlite3.connect(CATALOG); db.row_factory=sqlite3.Row
    rows=db.execute("SELECT vendor_name,document_kind,issue_date,period_start FROM accounting_document_facts WHERE vendor_name IS NOT NULL AND trim(vendor_name)<>'' AND document_kind IN ('statement','bill')").fetchall(); db.close()
    groups: dict[tuple[str,str], set[str]] = defaultdict(set)
    for r in rows:
        mk=month_key(r['period_start']) or month_key(r['issue_date'])
        if mk: groups[(str(r['vendor_name']).strip(),str(r['document_kind']).strip())].add(mk)
    with store.connect() as out:
        out.execute('DELETE FROM executive_accounting_completeness')
        for (vendor,kind), periods in groups.items():
            ordered=sorted(periods); missing=[]; state='learning'
            if len(ordered)>=3:
                expected=months_between(ordered[0],ordered[-1]); missing=[m for m in expected if m not in periods]
                state='gaps' if missing else 'complete'
            stats[state]+=1
            key=hash_id('acct',vendor.lower()+':'+kind)
            out.execute('INSERT INTO executive_accounting_completeness(key,vendor_name,document_kind,observed_periods,first_period,last_period,missing_periods_json,state,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?)',
                        (key,vendor,kind,len(ordered),ordered[0] if ordered else None,ordered[-1] if ordered else None,json.dumps(missing),state,now))
    return dict(stats)


def refresh_entity_profiles(store: OfficeManagerStore) -> int:
    if not CONTACTS.is_file(): return 0
    src=sqlite3.connect(CONTACTS); src.row_factory=sqlite3.Row
    acct=Counter()
    if CATALOG.is_file():
        c=sqlite3.connect(CATALOG); c.row_factory=sqlite3.Row
        for r in c.execute("SELECT lower(trim(vendor_name)) vendor,count(*) c FROM accounting_document_facts WHERE vendor_name IS NOT NULL GROUP BY lower(trim(vendor_name))"): acct[str(r['vendor'])]=int(r['c'])
        c.close()
    entities=src.execute('SELECT id,entity_type,canonical_name,display_name,lifecycle_status,verification_status FROM contact_entities ORDER BY canonical_name').fetchall(); now=utc_now()
    has_rel=table_exists(src,'contact_relationships')
    with store.connect() as out:
        out.execute('DELETE FROM executive_entity_profiles')
        for e in entities:
            eid=int(e['id']); name=str(e['canonical_name'])
            points=[dict(r) for r in src.execute('''SELECT cp.point_type,COALESCE(cp.display_value,cp.normalized_value) value,ca.assertion_type,ca.confidence,cp.lifecycle_status FROM contact_assertions ca JOIN contact_points cp ON cp.id=ca.contact_point_id WHERE ca.entity_id=? ORDER BY cp.point_type,ca.confidence LIMIT 40''',(eid,)).fetchall()]
            rels=[]
            if has_rel:
                rels=[dict(r) for r in src.execute('''SELECT cr.relationship_type,cr.confidence,cr.lifecycle_status,CASE WHEN cr.left_entity_id=? THEN r.canonical_name ELSE l.canonical_name END related_name,CASE WHEN cr.left_entity_id=? THEN r.entity_type ELSE l.entity_type END related_type FROM contact_relationships cr LEFT JOIN contact_entities l ON l.id=cr.left_entity_id LEFT JOIN contact_entities r ON r.id=cr.right_entity_id WHERE cr.left_entity_id=? OR cr.right_entity_id=? ORDER BY cr.lifecycle_status,cr.relationship_type LIMIT 40''',(eid,eid,eid,eid)).fetchall()]
            evidence_rows=[dict(r) for r in src.execute('''SELECT DISTINCT pr.id provenance_id,pr.source_name,pr.source_reference,pr.source_page,pr.verification_status,pr.source_document_id FROM contact_assertions ca JOIN assertion_evidence ae ON ae.assertion_id=ca.id JOIN provenance_records pr ON pr.id=ae.provenance_id WHERE ca.entity_id=?''',(eid,)).fetchall()]
            if table_exists(src,'contact_attestations'):
                evidence_rows.extend(dict(r) for r in src.execute('''SELECT DISTINCT pr.id provenance_id,pr.source_name,pr.source_reference,pr.source_page,pr.verification_status,pr.source_document_id FROM contact_attestations att JOIN provenance_records pr ON pr.id=att.provenance_id WHERE att.entity_id=? OR att.contact_point_id IN (SELECT DISTINCT contact_point_id FROM contact_assertions WHERE entity_id=?)''',(eid,eid)).fetchall())
            evidence_by_id={int(r['provenance_id']):r for r in evidence_rows}
            provenance_count=len(evidence_by_id)
            document_count=len({int(r['source_document_id']) for r in evidence_by_id.values() if r.get('source_document_id') is not None})
            docs=[]
            for pid in sorted(evidence_by_id,reverse=True)[:24]:
                r=dict(evidence_by_id[pid]); r.pop('provenance_id',None); docs.append(r)
            detail={'display_name':e['display_name'],'contact_points':points,'relationships':rels,'evidence':docs}
            out.execute('''INSERT INTO executive_entity_profiles(entity_key,entity_id,entity_type,canonical_name,verification_status,lifecycle_status,contact_points,relationships,provenance_count,document_count,accounting_documents,detail_json,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (f"{e['entity_type']}:{eid}",eid,e['entity_type'],name,e['verification_status'],e['lifecycle_status'],len(points),len(rels),provenance_count,document_count,acct[name.lower().strip()],json.dumps(detail,sort_keys=True),now))
    src.close(); return len(entities)


def refresh_hygiene(store: OfficeManagerStore, automation: dict[str,Any]) -> int:
    now=utc_now(); findings=[]
    timers=automation.get('timers') if isinstance(automation.get('timers'),list) else []
    for t in timers:
        if not isinstance(t,dict) or not t.get('custom'): continue
        if str(t.get('enabled'))=='disabled':
            findings.append((hash_id('hygiene','disabled:'+str(t.get('timer'))),'retirement-candidate',str(t.get('timer')),'candidate','Custom automation is disabled; review whether it is intentionally staged or superseded.','Review in Automation Center; retire only after dependency and rollback checks.'))
    # Known AVA supersessions are explicit rather than inferred.
    findings.extend([
      ('hygiene-ava-operations-reader','superseded-tool','AVA Operations Reader','retired','Superseded by Edge1 MCP Read and no longer exposed to AVA.','Retain rollback/audit code; do not re-enable as a parallel tool path.'),
      ('hygiene-legacy-gateway-patchers','superseded-tool','Legacy AVA gateway patchers','retired','v0.3.x patchers are fail-closed retirement stubs.','Keep retired unless an audited rollback specifically requires historical code.'),
    ])
    with store.connect() as db:
        db.execute('DELETE FROM executive_automation_hygiene')
        db.executemany('INSERT INTO executive_automation_hygiene(id,category,subject,state,rationale,recommended_action,updated_at_utc) VALUES(?,?,?,?,?,?,?)',[(a,b,c,d,e,f,now) for a,b,c,d,e,f in findings])
    return len(findings)


def refresh_templates_and_lifecycle(store: OfficeManagerStore) -> tuple[int,int]:
    now=utc_now(); data=load_json(TEMPLATES); caps=load_json(CAPABILITIES); templates=data.get('templates') if isinstance(data.get('templates'),list) else []
    with store.connect() as db:
        db.execute('DELETE FROM executive_workflow_templates')
        for t in templates:
            db.execute('INSERT INTO executive_workflow_templates(id,name,category,description,workflow_id,trigger_examples_json,state,owner_gate,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?)',
                       (t['id'],t['name'],t['category'],t['description'],t.get('workflow_id'),json.dumps(t.get('trigger_examples') or []),t['state'],t['owner_gate'],now))
        db.execute('DELETE FROM executive_automation_lifecycle')
        for c in caps.get('capabilities',[]):
            db.execute('INSERT INTO executive_automation_lifecycle(object_type,object_id,stage,version,validation_state,rollback_ref,notes,updated_at_utc) VALUES(?,?,?,?,?,?,?,?)',('capability',c['id'],'production','v1','registered',None,'Bounded capability registered in config/ava-executive-capabilities.json.',now))
        for w in caps.get('workflows',[]):
            db.execute('INSERT INTO executive_automation_lifecycle(object_type,object_id,stage,version,validation_state,rollback_ref,notes,updated_at_utc) VALUES(?,?,?,?,?,?,?,?)',('workflow',w['id'],'production' if w.get('autonomous') else 'candidate','v1','registered',None,'Versioned AVA workflow definition.',now))
        for t in templates:
            db.execute('INSERT INTO executive_automation_lifecycle(object_type,object_id,stage,version,validation_state,rollback_ref,notes,updated_at_utc) VALUES(?,?,?,?,?,?,?,?)',('template',t['id'],t['state'],'v1','registered',None,'AVA workflow template; owner gate='+t['owner_gate'],now))
        for oid,note in [('ava-operations-reader','Superseded by edge1_mcp_read.'),('legacy-ava-gateway-patchers','Superseded by the 0.4.3 MCP gateway deployment.')]:
            db.execute('INSERT INTO executive_automation_lifecycle(object_type,object_id,stage,version,validation_state,rollback_ref,notes,updated_at_utc) VALUES(?,?,?,?,?,?,?,?)',('tool',oid,'retired','legacy','retained_for_rollback',None,note,now))
        life=int(db.execute('SELECT COUNT(*) FROM executive_automation_lifecycle').fetchone()[0])
    return len(templates),life


def refresh_why(store: OfficeManagerStore) -> int:
    now=utc_now(); count=0
    with store.connect() as db:
        runs=db.execute('SELECT id,workflow_id,trigger_type,trigger_ref,state,error_summary,created_at_utc FROM executive_workflow_runs ORDER BY created_at_utc DESC LIMIT 500').fetchall()
        for run in runs:
            steps=db.execute('SELECT step_key,capability,member_id,state,attempt_count FROM executive_workflow_steps WHERE run_id=? ORDER BY created_at_utc,step_key',(run['id'],)).fetchall()
            action='; '.join(f"{s['capability']} → {s['member_id']} ({s['state']}, attempts={s['attempt_count']})" for s in steps) or 'No capability dispatched.'
            outcome=str(run['state']) + ((': '+str(run['error_summary'])) if run['error_summary'] else '')
            approval='not required' if run['state']=='completed' else ('required after bounded retry/policy failure' if run['state']=='failed' else 'not yet determined')
            wid='why-'+str(run['id'])
            db.execute('''INSERT INTO executive_why_events(id,object_type,object_id,trigger_text,policy_text,action_text,outcome_text,owner_approval,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(id) DO UPDATE SET trigger_text=excluded.trigger_text,policy_text=excluded.policy_text,action_text=excluded.action_text,outcome_text=excluded.outcome_text,owner_approval=excluded.owner_approval''',
                       (wid,'workflow',run['id'],f"{run['trigger_type']}: {run['trigger_ref']}",f"Registered workflow {run['workflow_id']}; only versioned bounded capabilities within team authority ceilings may run.",action[:4000],outcome[:2000],approval,str(run['created_at_utc'] or now))); count+=1
    return count


def refresh_briefing(store: OfficeManagerStore, automation: dict[str,Any], source_stats: dict[str,int]) -> dict[str,Any]:
    nowdt=datetime.now(timezone.utc); now=utc_now(); since=(nowdt-timedelta(hours=24)).isoformat()
    with store.connect() as db:
        workflows={r['state']:int(r['c']) for r in db.execute('SELECT state,COUNT(*) c FROM executive_workflow_runs WHERE created_at_utc>=? GROUP BY state',(since,))}
        reviews_open=int(db.execute("SELECT COUNT(*) FROM executive_reviews WHERE state='open' AND owner_required=1").fetchone()[0])
        attention=[dict(r) for r in db.execute("SELECT title,summary,severity,category,recommended_action FROM executive_reviews WHERE state='open' AND owner_required=1 ORDER BY CASE severity WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,updated_at_utc DESC LIMIT 6")]
        completed=int(db.execute("SELECT COUNT(*) FROM work_items WHERE state='completed' AND updated_at_utc>=?",(since,)).fetchone()[0])
        team={r['health_state']:int(r['c']) for r in db.execute('SELECT health_state,COUNT(*) c FROM executive_team_members WHERE active=1 GROUP BY health_state')}
        acct_gaps=int(db.execute("SELECT COUNT(*) FROM executive_accounting_completeness WHERE state='gaps'").fetchone()[0])
    imported=changed=indexed=preserved=0; accounting_new=0
    if CATALOG.is_file():
        cat=sqlite3.connect(CATALOG); cat.row_factory=sqlite3.Row
        r=cat.execute('SELECT COALESCE(SUM(new_items),0),COALESCE(SUM(changed_items),0),COALESCE(SUM(indexed),0),COALESCE(SUM(preserved),0) FROM library_sync_runs WHERE started_at>=?',(since,)).fetchone(); imported,changed,indexed,preserved=map(int,r)
        accounting_new=int(cat.execute('SELECT COUNT(*) FROM accounting_document_facts WHERE updated_at>=?',(since,)).fetchone()[0]); cat.close()
    contacts_updated=0
    if CONTACTS.is_file():
        c=sqlite3.connect(CONTACTS); contacts_updated=int(c.execute('SELECT COUNT(*) FROM contact_entities WHERE updated_at>=?',(since,)).fetchone()[0]); c.close()
    summary={'period_hours':24,'workflows_completed':workflows.get('completed',0),'workflows_failed':workflows.get('failed',0),'work_items_completed':completed,'documents_new':imported,'documents_changed':changed,'documents_indexed':indexed,'evidence_preserved':preserved,'contacts_updated':contacts_updated,'accounting_documents_updated':accounting_new,'accounting_completeness_gaps':acct_gaps,'owner_actions_required':reviews_open,'automation_failures':int((automation.get('summary') or {}).get('failed_or_non_success') or 0),'source_health':source_stats,'team_health':team,'attention':attention,'owner_action_required':reviews_open>0}
    day=nowdt.date().isoformat(); bid='daily:'+day
    with store.connect() as db:
        db.execute('''INSERT INTO executive_briefings(id,briefing_type,period_start_utc,period_end_utc,title,summary_json,owner_action_count,created_at_utc) VALUES(?,?,?,?,?,?,?,?)
                      ON CONFLICT(id) DO UPDATE SET period_start_utc=excluded.period_start_utc,period_end_utc=excluded.period_end_utc,summary_json=excluded.summary_json,owner_action_count=excluded.owner_action_count''',
                   (bid,'daily',(nowdt-timedelta(hours=24)).isoformat(),now,'AVA Daily Executive Briefing',json.dumps(summary,sort_keys=True),reviews_open,now))
    return summary


def build_status(store: OfficeManagerStore, extra: dict[str,Any]) -> dict[str,Any]:
    with store.connect() as db:
        counts={
          'reviews_open':int(db.execute("SELECT COUNT(*) FROM executive_reviews WHERE state='open'").fetchone()[0]),
          'reviews_owner':int(db.execute("SELECT COUNT(*) FROM executive_reviews WHERE state='open' AND owner_required=1").fetchone()[0]),
          'team_metrics':int(db.execute('SELECT COUNT(*) FROM executive_team_metrics').fetchone()[0]),
          'source_health':int(db.execute('SELECT COUNT(*) FROM executive_source_health').fetchone()[0]),
          'entity_profiles':int(db.execute('SELECT COUNT(*) FROM executive_entity_profiles').fetchone()[0]),
          'accounting_completeness':int(db.execute('SELECT COUNT(*) FROM executive_accounting_completeness').fetchone()[0]),
          'hygiene_items':int(db.execute('SELECT COUNT(*) FROM executive_automation_hygiene').fetchone()[0]),
          'workflow_templates':int(db.execute('SELECT COUNT(*) FROM executive_workflow_templates').fetchone()[0]),
          'why_events':int(db.execute('SELECT COUNT(*) FROM executive_why_events').fetchone()[0]),
        }
    return {'contract':'wwcx.ava-operations-intelligence.v1','generated_at':utc_now(),'state':'healthy','summary':counts,**extra,'mutation_scope':'ava-office-projection-only'}


def run() -> dict[str,Any]:
    store=OfficeManagerStore(OFFICE)
    automation=load_json(AUTOMATION); outstanding=load_json(OUTSTANDING)
    review=refresh_reviews(store,outstanding)
    timer_observations=record_timer_observations(store,automation)
    team=refresh_team_metrics(store)
    sources=refresh_source_health(store)
    accounting=refresh_accounting_completeness(store)
    entities=refresh_entity_profiles(store)
    hygiene=refresh_hygiene(store,automation)
    templates,lifecycle=refresh_templates_and_lifecycle(store)
    why=refresh_why(store)
    briefing=refresh_briefing(store,automation,sources)
    status=build_status(store,{'run':{'reviews':review,'timer_observations':timer_observations,'team_members':team,'source_states':sources,'accounting':accounting,'entities':entities,'hygiene':hygiene,'templates':templates,'lifecycle_records':lifecycle,'why_events':why},'briefing':briefing})
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(status,indent=2,sort_keys=True)+'\n',encoding='utf-8'); STATUS.chmod(0o644)
    return status


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--json',action='store_true'); args=p.parse_args()
    result=run(); print(json.dumps(result if args.json else result['summary'],sort_keys=True)); return 0

if __name__=='__main__': raise SystemExit(main())
