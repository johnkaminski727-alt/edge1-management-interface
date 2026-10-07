#!/usr/bin/env python3
"""Bounded first-party research for pending organization contact enrichment.

Reads only already-known organization domains. It never searches the open web,
submits forms, or mutates Unified Contacts. Unique first-party findings are
staged on the maintenance enrichment row as REVIEW_REQUIRED evidence.
"""
from __future__ import annotations
import argparse, html, ipaddress, json, os, re, socket, sqlite3, ssl, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

CONTACTS=Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
STATE=Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
OUTPUT=Path('/var/www/edge1-status/contact-enrichment-research/status.json')
USER_AGENT='WWCX-Contact-Enrichment/1.0 (+read-only first-party research)'
MAX_BYTES=512*1024
PATHS=('/', '/contact', '/contact-us', '/about')
FREE_DOMAINS={'gmail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','sasktel.net'}
EMAIL_RE=re.compile(r'(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63})(?![\w.-])',re.I)
PHONE_RE=re.compile(r'(?<!\d)(\+?\d[\d().\-\s]{6,}\d)(?!\d)')
POSTAL_RE=re.compile(r'\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTVWXYZ][ -]?\d[ABCEGHJ-NPRSTVWXYZ]\d)\b',re.I)
PROVINCE_RE=r'(?:Alberta|British Columbia|Manitoba|New Brunswick|Newfoundland(?: and Labrador)?|Nova Scotia|Ontario|Prince Edward Island|Quebec|Québec|Saskatchewan|Northwest Territories|Nunavut|Yukon|AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)'
TAG_RE=re.compile(r'<[^>]+>')
SCRIPT_RE=re.compile(r'<(script|style)\b[^>]*>.*?</\1>',re.I|re.S)


def utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def host(value):
    value=str(value or '').strip().lower()
    if '@' in value: return value.rsplit('@',1)[1].strip('.')
    if '://' not in value: value='https://'+value
    try: return (urllib.parse.urlsplit(value).hostname or '').lower().removeprefix('www.')
    except ValueError: return ''
def global_host(name):
    try: infos=socket.getaddrinfo(name,443,type=socket.SOCK_STREAM)
    except OSError: return False
    addrs={x[4][0] for x in infos}
    if not addrs: return False
    for value in addrs:
        try:
            ip=ipaddress.ip_address(value)
            if not ip.is_global: return False
        except ValueError: return False
    return True
def allowed_host(candidate, base):
    candidate=(candidate or '').lower().rstrip('.'); base=base.lower().rstrip('.')
    return candidate in {base,'www.'+base}

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self,base): super().__init__(); self.base=base
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urllib.parse.urlsplit(newurl); h=(u.hostname or '').lower()
        if u.scheme!='https' or not allowed_host(h,self.base) or not global_host(h):
            raise urllib.error.HTTPError(newurl,code,'redirect outside approved first-party boundary',headers,fp)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def safe_fetch(url, base, timeout=8):
    u=urllib.parse.urlsplit(url); h=(u.hostname or '').lower()
    if u.scheme!='https' or not allowed_host(h,base) or not global_host(h): raise ValueError('unsafe first-party URL')
    opener=urllib.request.build_opener(SafeRedirect(base),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,text/plain;q=0.8,*/*;q=0.1'})
    with opener.open(req,timeout=timeout) as r:
        final=urllib.parse.urlsplit(r.geturl()); final_host=(final.hostname or '').lower()
        if not allowed_host(final_host,base): raise ValueError('off-domain final URL')
        ctype=(r.headers.get_content_type() or '').lower()
        if ctype not in {'text/html','text/plain'}: raise ValueError('unsupported content type')
        raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('response too large')
        charset=r.headers.get_content_charset() or 'utf-8'
        return raw.decode(charset,errors='replace'),r.geturl()
def robots_allows(base,path):
    try:
        text,_=safe_fetch(f'https://{base}/robots.txt',base,timeout=5)
        rp=urllib.robotparser.RobotFileParser(); rp.set_url(f'https://{base}/robots.txt'); rp.parse(text.splitlines())
        return rp.can_fetch(USER_AGENT,f'https://{base}{path}')
    except urllib.error.HTTPError as exc:
        return exc.code in {404,410}
    except Exception:
        return False
def clean_text(raw):
    raw=SCRIPT_RE.sub(' ',raw); raw=TAG_RE.sub(' ',raw); raw=html.unescape(raw)
    return re.sub(r'\s+',' ',raw).strip()
def norm_phone(value):
    value=str(value).strip(); digits=re.sub(r'\D','',value)
    if not 7<=len(digits)<=15:return ''
    if value.startswith('+'):return '+'+digits
    if len(digits)==10:return '+1'+digits
    if len(digits)==11 and digits.startswith('1'):return '+'+digits
    return ''
def relevant_name(text,name):
    words=[w.casefold() for w in re.findall(r'[A-Za-z0-9]+',name or '') if len(w)>=4 and w.casefold() not in {'incorporated','limited','corporation','company'}]
    low=text.casefold()
    return bool(words and any(w in low for w in words[:4]))
def concise_address(text, match):
    compact=re.sub(r'\s','',match.group(1).upper())
    if len(compact)!=6:
        return None
    formatted=compact[:3]+' '+compact[3:]
    postal_pattern=re.escape(compact[:3])+r'[ -]?'+re.escape(compact[3:])
    a=max(0,match.start()-180); b=min(len(text),match.end()+28); snippet=text[a:b]
    name_chars=r"[A-Za-z][A-Za-z .'-]"
    po_pattern=(r"\b((?:P\.?\s*O\.?\s*Box|PO Box|Box)\s+\d+[A-Za-z0-9-]*\s*,?\s+"
                +name_chars+r"{1,55},?\s+"+PROVINCE_RE+r"\s+"+postal_pattern+r"(?:\s+Canada)?)\b")
    po=re.search(po_pattern,snippet,re.I)
    if po:
        value=re.sub(r'\s+',' ',po.group(1)).strip(' ,.;')
        return POSTAL_RE.sub(formatted,value,count=1)
    street_pattern=(r"\b(\d{1,6}\s+[A-Za-z0-9 .'#-]{2,70}?(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Drive|Dr\.?|Boulevard|Blvd\.?|Highway|Hwy\.?|Lane|Ln\.?|Court|Ct\.?)"
                    r"\s*,?\s+"+name_chars+r"{1,45},?\s+"+PROVINCE_RE+r"\s+"+postal_pattern+r"(?:\s+Canada)?)\b")
    street=re.search(street_pattern,snippet,re.I)
    if street:
        value=re.sub(r'\s+',' ',street.group(1)).strip(' ,.;')
        return POSTAL_RE.sub(formatted,value,count=1)
    return None

def extract_page(raw,url,base):
    text=clean_text(raw); low=text.casefold(); result={'emails':set(),'phones':set(),'postals':{},'text':text[:12000],'url':url}
    for e in EMAIL_RE.findall(text):
        e=e.casefold(); d=host(e)
        if d==base or d.endswith('.'+base): result['emails'].add(e)
    for m in PHONE_RE.finditer(text):
        value=norm_phone(m.group(1))
        if value: result['phones'].add(value)
    for m in POSTAL_RE.finditer(text):
        code=re.sub(r'\s','',m.group(1).upper()); address=concise_address(text,m)
        if address: result['postals'][code]=address
    return result

def known_domains(db,entity_id):
    rows=db.execute("SELECT cp.point_type,cp.normalized_value FROM contact_assertions ca JOIN contact_points cp ON cp.id=ca.contact_point_id WHERE ca.entity_id=? AND cp.lifecycle_status='active'",(entity_id,)).fetchall()
    explicit=[]; email=[]
    for row in rows:
        d=host(row['normalized_value'])
        if not d or '.' not in d:continue
        if row['point_type'] in {'domain','website'}:explicit.append(d)
        elif row['point_type']=='email' and d not in FREE_DOMAINS:email.append(d)
    return sorted(set(explicit or email))
def ensure_columns(db):
    cols={r[1] for r in db.execute('PRAGMA table_info(enrichment_queue)')}
    for definition in ('proposed_value TEXT','evidence_json TEXT','research_confidence TEXT','research_checked_at TEXT'):
        name=definition.split()[0]
        if name not in cols: db.execute(f'ALTER TABLE enrichment_queue ADD COLUMN {definition}')
def research_domain(base,name):
    pages=[]; errors=[]
    for path in PATHS:
        if not robots_allows(base,path):
            errors.append({'path':path,'error':'robots_denied_or_unavailable'}); continue
        try:
            raw,url=safe_fetch(f'https://{base}{path}',base)
            page=extract_page(raw,url,base); page['name_relevant']=relevant_name(page['text'],name); pages.append(page)
        except Exception as exc:
            errors.append({'path':path,'error':type(exc).__name__})
    return pages,errors
def choose(task,pages,base,name):
    relevant=[p for p in pages if p['name_relevant']]
    if not relevant:return None
    if task=='find_web_presence': return {'value':f'https://{base}/','confidence':'first_party_public','support':len(relevant)}
    key={'find_phone':'phones','find_email':'emails','find_address':'postals'}.get(task)
    if not key:return None
    counts=Counter(); contexts=defaultdict(list)
    for page in relevant:
        vals=page[key]
        if isinstance(vals,dict): vals=vals.keys()
        for value in vals:
            counts[value]+=1; contexts[value].append(page['url'])
    if not counts:return None
    strongest=[v for v,n in counts.items() if n>=2]
    if len(strongest)!=1:
        # A unique candidate on a contact page is acceptable for review staging.
        contact=[]
        for page in relevant:
            if '/contact' not in urllib.parse.urlsplit(page['url']).path.casefold():continue
            vals=page[key]
            if isinstance(vals,dict): vals=vals.keys()
            contact.extend(vals)
        unique=sorted(set(contact))
        if len(unique)!=1:return None
        strongest=unique
    value=strongest[0]
    if task=='find_address':
        snippets=[]
        for page in relevant:
            if value in page['postals']: snippets.append(page['postals'][value])
        proposed=snippets[0] if snippets else value
    else: proposed=value
    return {'value':proposed,'normalized_key':value,'confidence':'first_party_public','support':counts.get(value,1),'urls':sorted(set(contexts.get(value,[])))[:4]}
def run(limit=25,dry_run=False):
    now=utcnow(); cutoff=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat(timespec='seconds')
    c=sqlite3.connect(f'file:{CONTACTS}?mode=ro',uri=True); c.row_factory=sqlite3.Row
    s=sqlite3.connect(STATE); s.row_factory=sqlite3.Row; ensure_columns(s)
    scan_limit=max(500,limit*20)
    tasks=s.execute("SELECT id,entity_id,task_type,rationale,research_checked_at FROM enrichment_queue WHERE status='pending' AND (research_checked_at IS NULL OR research_checked_at<?) ORDER BY id LIMIT ?",(cutoff,scan_limit)).fetchall()
    stats=Counter(); staged=[]; cache={}; attempted=0
    for task in tasks:
        entity=c.execute("SELECT id,entity_type,canonical_name FROM contact_entities WHERE id=? AND lifecycle_status='active'",(task['entity_id'],)).fetchone()
        if not entity or entity['entity_type']!='organization':
            stats['skipped_non_org']+=1
            if not dry_run:s.execute("UPDATE enrichment_queue SET research_checked_at=?,updated_at=? WHERE id=? AND status='pending'",(now,now,task['id']))
            continue
        domains=known_domains(c,entity['id'])
        if not domains:
            stats['skipped_no_firstparty_domain']+=1
            if not dry_run:s.execute("UPDATE enrichment_queue SET research_checked_at=?,updated_at=? WHERE id=? AND status='pending'",(now,now,task['id']))
            continue
        if attempted>=limit:
            break
        attempted+=1
        found=None; used=None; page_count=0; error_count=0
        for base in domains[:2]:
            if base not in cache: cache[base]=research_domain(base,entity['canonical_name'])
            pages,errors=cache[base]; page_count+=len(pages); error_count+=len(errors)
            candidate=choose(task['task_type'],pages,base,entity['canonical_name'])
            if candidate is not None:
                if found is not None and candidate.get('normalized_key',candidate['value']) != found.get('normalized_key',found['value']):
                    found=None; used=None; stats['ambiguous']+=1; break
                found=candidate; used=base
        evidence={'contract':'wwcx.contact-enrichment-research.v1','entity_id':entity['id'],'entity_name':entity['canonical_name'],'task_type':task['task_type'],'domain':used,'pages_checked':page_count,'fetch_errors':error_count,'source_class':'first_party_public','mutates_contacts':False}
        if found:
            evidence.update({'support':found.get('support',1),'urls':found.get('urls') or ([f'https://{used}/'] if used else [])})
            staged.append({'task_id':task['id'],'entity_id':entity['id'],'task_type':task['task_type'],'value':found['value'],'domain':used})
            stats['staged_review']+=1
            if not dry_run:
                s.execute("UPDATE enrichment_queue SET status='review_required',proposed_value=?,evidence_json=?,research_confidence=?,research_checked_at=?,updated_at=? WHERE id=? AND status='pending'",(found['value'],json.dumps(evidence,sort_keys=True),found['confidence'],now,now,task['id']))
        else:
            stats['no_unique_candidate']+=1
            if not dry_run:s.execute("UPDATE enrichment_queue SET research_checked_at=?,updated_at=? WHERE id=? AND status='pending'",(now,now,task['id']))
        stats['researched']+=1
    if not dry_run:s.commit()
    c.close();s.close()
    payload={'contract':'wwcx.contact-enrichment-research-status.v1','generated_at':now,'state':'healthy','summary':dict(stats),'staged':staged[:50],'boundaries':{'first_party_only':True,'https_only':True,'robots_aware':True,'forms_submitted':False,'contacts_mutated':False,'review_required':True},'dry_run':dry_run}
    if not dry_run:
        OUTPUT.parent.mkdir(parents=True,exist_ok=True); tmp=OUTPUT.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); os.chmod(tmp,0o644); tmp.replace(OUTPUT)
    return payload

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=25);ap.add_argument('--dry-run',action='store_true');a=ap.parse_args();print(json.dumps(run(max(1,min(a.limit,100)),a.dry_run),sort_keys=True))
if __name__=='__main__':main()
