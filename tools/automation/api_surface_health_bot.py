#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
ACCEPTED=Path('/etc/edge1/api-surface-accepted.json'); UFW_RULES=Path('/etc/ufw/user.rules')
# ENG-023 (operator-approved 2026-10-11): reviewed non-loopback listeners are
# downgraded to info ONLY while live checks hold - socket bound to exactly the
# approved address and the exact UFW rule present. Otherwise they stay high.
def _proc_addr(hexaddr):
    import ipaddress
    raw=bytes.fromhex(hexaddr)
    if len(raw)==4: return str(ipaddress.IPv4Address(raw[::-1]))
    return str(ipaddress.IPv6Address(b''.join(raw[i:i+4][::-1] for i in range(0,16,4))))
def listening_addresses(port):
    found=set()
    for name in ('/proc/net/tcp','/proc/net/tcp6'):
        try: lines=Path(name).read_text().splitlines()[1:]
        except OSError: continue
        for line in lines:
            f=line.split()
            if len(f)<4 or f[3]!='0A': continue
            addr,_,hexport=f[1].partition(':')
            if int(hexport,16)==port: found.add(_proc_addr(addr))
    return found
def load_accepted(path=ACCEPTED):
    try: return json.loads(path.read_text()).get('accepted',[])
    except Exception: return []
def exception_check(x,accepted,ufw_text,listen=listening_addresses):
    entry=next((e for e in accepted if e.get('port')==x.get('port') and e.get('service')==x.get('service')),None)
    if entry is None: return None,'not_listed'
    addrs=listen(int(x.get('port')))
    if addrs!={entry.get('bind_address')}: return entry,f"bind={sorted(addrs) or 'none'} expected={entry.get('bind_address')}"
    rules={l.strip() for l in ufw_text.splitlines()}
    if (entry.get('ufw_rule') or '').strip() not in rules: return entry,'ufw_rule_missing'
    return entry,None
SOURCE=Path('/var/www/edge1-status/api-directory/inventory.json'); STATE=Path('/var/lib/edge1-api-surface-health/state.json'); STATUS=Path('/var/www/edge1-status/api-surface-health/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def active(unit):
    if not unit:return None
    p=subprocess.run(['systemctl','is-active',unit],text=True,capture_output=True,check=False); return p.stdout.strip() or 'unknown'
def build(source=SOURCE,state=STATE,accepted_path=ACCEPTED,ufw_path=UFW_RULES,listen=listening_addresses):
    accepted=load_accepted(accepted_path)
    try: ufw_text=ufw_path.read_text()
    except OSError: ufw_text=''
    data=json.loads(source.read_text()); live=data.get('live_apis',[]); findings=[]; current={f"{x.get('bind_scope')}:{x.get('port')}:{x.get('service') or x.get('process')}" for x in live}
    previous=set()
    try: previous=set(json.loads(state.read_text()).get('listeners',[]))
    except Exception: pass
    added=sorted(current-previous) if previous else []; removed=sorted(previous-current) if previous else []
    for x in live:
        ident=f"{x.get('bind_scope')}:{x.get('port')}"
        if x.get('bind_scope')!='loopback':
            entry,why=exception_check(x,accepted,ufw_text,listen)
            if entry is not None and why is None: findings.append({'kind':'accepted_exposure','severity':'info','subject':ident,'detail':f"service={x.get('service')} bind={entry.get('bind_address')} reason={entry.get('reason')}",'action_level':'NONE'})
            else: findings.append({'kind':'unexpected_exposure','severity':'high','subject':ident,'detail':f"service={x.get('service')} exposure={x.get('exposure')}"+(f" exception_check_failed={why}" if entry is not None else ''),'action_level':'REVIEW-REQUIRED'})
        if x.get('service'):
            statev=active(x['service'])
            if statev!='active': findings.append({'kind':'listener_service_mismatch','severity':'high','subject':ident,'detail':f"{x.get('service')} state={statev} while listener is inventoried",'action_level':'REVIEW-REQUIRED'})
        else: findings.append({'kind':'unattributed_listener','severity':'low','subject':ident,'detail':f"process={x.get('process')} has no mapped systemd unit",'action_level':'REVIEW-REQUIRED'})
        if x.get('access_boundary')=='unknown_review_required': findings.append({'kind':'access_boundary_unknown','severity':'low','subject':ident,'detail':f"service={x.get('service') or x.get('process')}",'action_level':'AUTO-STAGE'})
    for item in added: findings.append({'kind':'listener_added','severity':'medium','subject':item,'detail':'New API-like listener since previous inventory.','action_level':'REVIEW-REQUIRED'})
    for item in removed: findings.append({'kind':'listener_removed','severity':'medium','subject':item,'detail':'API-like listener disappeared since previous inventory.','action_level':'REVIEW-REQUIRED'})
    state.parent.mkdir(parents=True,exist_ok=True); state.write_text(json.dumps({'updated_at':utcnow(),'listeners':sorted(current)},indent=2)+'\n'); state.chmod(0o600)
    state_name='attention' if any(x['severity']=='high' for x in findings) else 'warning' if any(x['severity']=='medium' for x in findings) else 'healthy'
    return {'contract':'wwcx.api-surface-health.v1','generated_at':utcnow(),'state':state_name,'summary':{'listeners':len(live),'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'added':len(added),'removed':len(removed),'unattributed':sum(x['kind']=='unattributed_listener' for x in findings),'accepted':sum(x['kind']=='accepted_exposure' for x in findings)},'findings':findings[:300],'network_mutation_performed':False}
def markdown(d):
    lines=['# API Surface Health','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Listeners: {d['summary']['listeners']} · Findings: {d['summary']['findings']}",'','## Findings','']; lines += [f"- **{x['severity']} · {x['kind']}** — {x['subject']} — {x['detail']}" for x in d['findings']] or ['- None.']; lines += ['','This bot never opens, closes, binds, restarts, or reconfigures network services.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/api-surface-health/current.md','API Surface Health',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
