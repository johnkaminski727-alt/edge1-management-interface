#!/usr/bin/env python3
"""Read-only multi-account Gmail API intake for Edge1 Mail Room.

Uses only gmail.readonly, preserves exact raw RFC822 messages and Gmail label provenance,
maintains restartable full/history cursors, and projects messages through the existing
Mail Room security/archive path. It never sends, deletes, moves, labels, stars, or marks
provider messages read/unread.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, sqlite3, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'server'))
from server.mail_room_security import stage_provider
from mail_correspondence_store import MailCorrespondenceStore
from mail_local_rfc822_source import normalize_rfc822

CONFIG = Path('/etc/wwcx/gmail-mail.json')
STATE_ROOT = Path('/var/lib/wwcx-mail-room/gmail-api')
STATUS = STATE_ROOT / 'status.json'
ARCHIVE_ROOT = Path('/var/lib/wwcx-mail-room/imports/gmail-api')
CORRESPONDENCE = Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')
API = 'https://gmail.googleapis.com/gmail/v1'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
PROVIDER_SOURCE = 'google-gmail-api'
MAX_RAW_BYTES = 150 * 1024 * 1024
MAX_BODY = 90_000

class GmailError(RuntimeError):
    def __init__(self, message, status=None): super().__init__(message); self.status=status

def utcnow(): return datetime.now(timezone.utc).isoformat()
def account_key(account): return hashlib.sha256(account.lower().encode()).hexdigest()[:16]
def source_id(account):
    safe=re.sub(r'[^a-z0-9]+','-',account.lower()).strip('-')[:80]
    return 'gmail-google-api-' + safe

def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.tmp-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path); os.chmod(path,mode)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def save_json(path,value,mode=0o600): atomic_write(path,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode(),mode)
def load_json(path,default=None):
    try: return json.loads(path.read_text())
    except FileNotFoundError: return {} if default is None else default

def read_config(require_client=False):
    value=load_json(CONFIG,{})
    accounts=[]
    for raw in value.get('accounts',[]):
        account=str(raw).strip().lower()
        if not re.fullmatch(r'[^\s@,<>]+@[^\s@,<>]+',account): raise RuntimeError('Invalid Gmail account in configuration')
        if account not in accounts: accounts.append(account)
    credentials_file=Path(str(value.get('credentials_file','/etc/wwcx/gmail-oauth-client.json')))
    client={}
    if credentials_file.is_file() and not credentials_file.is_symlink():
        payload=load_json(credentials_file,{})
        client=payload.get('installed') or payload.get('web') or {}
    if require_client and (not client.get('client_id') or not client.get('client_secret')):
        raise RuntimeError('Google OAuth client credentials file is not installed')
    return {'accounts':accounts,'credentials_file':credentials_file,'client':client}

def paths(account):
    root=STATE_ROOT/account_key(account)
    return root, root/'state.sqlite3', root/'token.json'

def init_account(account):
    root,db_path,_=paths(account); root.mkdir(parents=True,exist_ok=True,mode=0o700)
    (ARCHIVE_ROOT/account_key(account)).mkdir(parents=True,exist_ok=True,mode=0o700)
    with sqlite3.connect(db_path) as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sync_state(id INTEGER PRIMARY KEY CHECK(id=1),phase TEXT NOT NULL DEFAULT 'initial',page_token TEXT,history_id TEXT,last_success TEXT,last_error TEXT,pages INTEGER NOT NULL DEFAULT 0,observed INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO sync_state(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS observations(gmail_id TEXT PRIMARY KEY,thread_id TEXT,history_id TEXT,raw_sha256 TEXT,internet_message_id TEXT,labels_json TEXT NOT NULL,folder_class TEXT NOT NULL,direction TEXT NOT NULL,projection_status TEXT,observed_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS gmail_obs_mid_idx ON observations(internet_message_id);
        CREATE INDEX IF NOT EXISTS gmail_obs_sha_idx ON observations(raw_sha256);
        ''')
    os.chmod(db_path,0o600)

def state_row(account):
    _,db_path,_=paths(account)
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row; return dict(db.execute('SELECT * FROM sync_state WHERE id=1').fetchone())
def update_state(account,**values):
    allowed={'phase','page_token','history_id','last_success','last_error','pages','observed'}; values={k:v for k,v in values.items() if k in allowed}
    if not values:return
    _,db_path,_=paths(account)
    with sqlite3.connect(db_path) as db: db.execute('UPDATE sync_state SET '+','.join(k+'=?' for k in values)+' WHERE id=1',(*values.values(),))

def form_post(url,fields,timeout=45):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(fields).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read(1024*1024))
    except urllib.error.HTTPError as exc:
        data=exc.read(1024*1024)
        try: p=json.loads(data); detail=p.get('error_description') or p.get('error') or f'HTTP {exc.code}'
        except Exception: detail=f'HTTP {exc.code}'
        raise GmailError(str(detail),exc.code) from exc

def token_from_refresh(account):
    cfg=read_config(require_client=True); _,_,token_path=paths(account); cache=load_json(token_path,{})
    refresh=str(cache.get('refresh_token',''))
    if not refresh: raise RuntimeError('Google authorization has not been completed for '+account)
    result=form_post(TOKEN_URL,{'client_id':cfg['client']['client_id'],'client_secret':cfg['client']['client_secret'],'refresh_token':refresh,'grant_type':'refresh_token'})
    if not result.get('access_token'): raise RuntimeError('Google token refresh returned no access token')
    return str(result['access_token'])

def api_request(path_or_url,token,retries=4):
    url=path_or_url if path_or_url.startswith('https://') else API+path_or_url
    for attempt in range(retries):
        req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'Edge1-Mail-Room-Gmail/1.0'})
        try:
            with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read(MAX_RAW_BYTES+2*1024*1024))
        except urllib.error.HTTPError as exc:
            if exc.code in {429,500,503,504} and attempt+1<retries: time.sleep(min(30,2**attempt)); continue
            try: detail=json.loads(exc.read(1024*1024)).get('error',{}).get('message',f'Gmail API HTTP {exc.code}')
            except Exception: detail=f'Gmail API HTTP {exc.code}'
            raise GmailError(detail,exc.code) from exc
        except urllib.error.URLError as exc:
            if attempt+1<retries: time.sleep(min(10,2**attempt)); continue
            raise GmailError('Gmail API network request failed') from exc

def canonical_mid(value): return bool(re.fullmatch(r'<[^<>\r\n\s]+@[^<>\r\n\s]+>',value or '')) and len(value)<=998
class PlainHTML(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True);self.text=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','head'}:self.hidden+=1
        if tag in {'p','br','div','li','tr'} and not self.hidden:self.text.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','head'} and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.text.append(data)
def body_text(message):
    plain=[];html=[]
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition()=='attachment':continue
        try:c=part.get_content()
        except Exception:continue
        if not isinstance(c,str):continue
        if part.get_content_type()=='text/plain':plain.append(c)
        elif part.get_content_type()=='text/html':html.append(c)
    text='\n'.join(plain)
    if not text and html:
        parser=PlainHTML()
        for c in html:
            try:parser.feed(c)
            except Exception:pass
            parser.text.append('\n')
        text=''.join(parser.text)
    return text.replace('\x00','')[:MAX_BODY]
def classify(labels):
    labels=set(labels or [])
    if 'TRASH' in labels or 'DRAFT' in labels:return 'excluded','inbound'
    if 'SPAM' in labels:return 'junk','inbound'
    if 'SENT' in labels:return 'sent','outbound'
    if 'INBOX' in labels:return 'inbox','inbound'
    return 'archive','inbound'
def build_projection(raw,item,account,direction,mid):
    original=BytesParser(policy=policy.default).parsebytes(raw); projected=EmailMessage(policy=policy.default)
    senders=[a for _,a in getaddresses(original.get_all('From',[])) if a.count('@')==1]
    sender=senders[0] if len(senders)==1 else account if direction=='outbound' else None
    if not sender: raise RuntimeError('message sender cannot be normalized')
    recipients=[a for _,a in getaddresses(original.get_all('To',[])+original.get_all('Cc',[])) if a.count('@')==1]
    if not recipients and direction=='inbound':recipients=[account]
    if not recipients:raise RuntimeError('message recipients cannot be normalized')
    projected['From']=sender;projected['To']=', '.join(dict.fromkeys(recipients[:100]));projected['Subject']=str(original.get('Subject',''))[:998].replace('\x00','');projected['Message-ID']=mid
    date=str(original.get('Date','')).strip()
    try:
        parsed=parsedate_to_datetime(date) if date else None
        if parsed is None or parsed.tzinfo is None:raise ValueError()
        projected['Date']=date
    except Exception:
        ms=int(item.get('internalDate') or 0);dt=datetime.fromtimestamp(ms/1000,tz=timezone.utc) if ms else datetime.now(timezone.utc);projected['Date']=dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    for header in ('In-Reply-To','References'):
        tokens=re.findall(r'<[^<>\r\n\s]+@[^<>\r\n\s]+>',str(original.get(header,'')))[:100]
        if tokens:projected[header]=' '.join(tokens)
    projected.set_content(body_text(original));return projected.as_bytes()
def security_bytes(raw,mid):
    original=str(BytesParser(policy=policy.default).parsebytes(raw,headersonly=True).get('Message-ID','')).strip()
    return raw if original==mid else (f'Message-ID: {mid}\r\n'.encode('ascii')+raw)
def archive_original(account,raw,item,folder_class):
    digest=hashlib.sha256(raw).hexdigest();target=ARCHIVE_ROOT/account_key(account)/'objects'/digest[:2]/digest;target.mkdir(parents=True,exist_ok=True,mode=0o700)
    eml=target/'message.eml'
    if not eml.exists():atomic_write(eml,raw)
    elif hashlib.sha256(eml.read_bytes()).hexdigest()!=digest:raise RuntimeError('Gmail archive integrity mismatch')
    metadata=target/'metadata.json'
    if not metadata.exists():save_json(metadata,{'contract':'wwcx.gmail-api-original.v1','account':account,'source':source_id(account),'sha256':digest,'bytes':len(raw),'gmail_id_sha256':hashlib.sha256(str(item.get('id','')).encode()).hexdigest(),'thread_id_sha256':hashlib.sha256(str(item.get('threadId','')).encode()).hexdigest(),'history_id':item.get('historyId'),'labels':sorted(item.get('labelIds') or []),'folder_class':folder_class,'archived_at':utcnow(),'provider_mutations':False})
    return digest
def correspondence_exists(mid):
    with sqlite3.connect(CORRESPONDENCE) as db:return db.execute('SELECT 1 FROM correspondence WHERE message_id=?',(mid,)).fetchone() is not None
def native_raw_exists(digest):
    for meta in Path('/var/lib/wwcx-mail-gateway/inbound').glob('*/*/metadata.json'):
        try:
            if meta.stat().st_size<65536 and json.loads(meta.read_text()).get('rfc822_sha256')==digest:return True
        except (OSError,ValueError):continue
    return False
def mark_observation(account,item,digest,mid,folder_class,direction,status):
    _,db_path,_=paths(account)
    with sqlite3.connect(db_path) as db:db.execute('''INSERT INTO observations(gmail_id,thread_id,history_id,raw_sha256,internet_message_id,labels_json,folder_class,direction,projection_status,observed_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(gmail_id) DO UPDATE SET thread_id=excluded.thread_id,history_id=excluded.history_id,raw_sha256=excluded.raw_sha256,internet_message_id=excluded.internet_message_id,labels_json=excluded.labels_json,folder_class=excluded.folder_class,direction=excluded.direction,projection_status=excluded.projection_status,observed_at=excluded.observed_at''',(str(item.get('id','')),str(item.get('threadId','')),str(item.get('historyId','')),digest,mid,json.dumps(sorted(item.get('labelIds') or []),separators=(',',':')),folder_class,direction,status,utcnow()))
def get_message(account,gmail_id,token):
    item=api_request('/users/me/messages/'+urllib.parse.quote(gmail_id,safe='')+'?format=raw',token)
    raw_s=str(item.get('raw','')); pad='='*((4-len(raw_s)%4)%4)
    try:raw=base64.urlsafe_b64decode((raw_s+pad).encode())
    except Exception as exc:raise RuntimeError('Gmail raw message could not be decoded') from exc
    if not raw or len(raw)>MAX_RAW_BYTES:raise RuntimeError('Gmail raw message exceeds archive limit')
    return item,raw
def process_message(account,gmail_id,token,store):
    item,raw=get_message(account,gmail_id,token);folder_class,direction=classify(item.get('labelIds'))
    if folder_class=='excluded':return 'excluded',str(item.get('historyId') or '')
    digest=archive_original(account,raw,item,folder_class);original_mid=str(BytesParser(policy=policy.default).parsebytes(raw,headersonly=True).get('Message-ID','')).strip();mid=original_mid if canonical_mid(original_mid) else f'<gmail-{digest}@archive.ww.cx>'
    if correspondence_exists(mid) or native_raw_exists(digest):mark_observation(account,item,digest,mid,folder_class,direction,'duplicate');return 'duplicate',str(item.get('historyId') or '')
    scan_raw=security_bytes(raw,mid);stage_provider(scan_raw,account,mid,provider_source=PROVIDER_SOURCE);scan_digest=hashlib.sha256(scan_raw).hexdigest();domain=account.rsplit('@',1)[1].lower();meta_path=Path('/var/lib/wwcx-mail-gateway/inbound')/domain/('imap-'+scan_digest[:24])/'metadata.json'
    if meta_path.exists():
        meta=json.loads(meta_path.read_text());meta.update({'provider_folder':folder_class,'provider_folder_class':folder_class,'provider_account':account,'provider_labels':sorted(item.get('labelIds') or [])});save_json(meta_path,meta)
    projection=build_projection(raw,item,account,direction,mid);normalize_rfc822(projection,store,direction=direction);mark_observation(account,item,digest,mid,folder_class,direction,'imported');return 'imported',str(item.get('historyId') or '')
def full_page(account,token,page_token=None):
    q={'maxResults':'500','includeSpamTrash':'true','q':'-in:trash -in:drafts'}
    if page_token:q['pageToken']=page_token
    return api_request('/users/me/messages?'+urllib.parse.urlencode(q),token)
def history_page(token,history_id,page_token=None):
    q={'startHistoryId':history_id,'maxResults':'500'}
    if page_token:q['pageToken']=page_token
    return api_request('/users/me/history?'+urllib.parse.urlencode(q),token)
def history_ids(payload):
    result=[]
    for h in payload.get('history',[]) or []:
        for key in ('messages','messagesAdded','labelsAdded','labelsRemoved'):
            for entry in h.get(key,[]) or []:
                message=entry.get('message',entry) if isinstance(entry,dict) else {}
                gid=str(message.get('id',''))
                if gid and gid not in result:result.append(gid)
    return result

def account_status(account,running=False,counts=None,error=None):
    init_account(account); row=state_row(account);_,db_path,token_path=paths(account)
    with sqlite3.connect(db_path) as db: totals=dict(db.execute('SELECT projection_status,count(*) FROM observations GROUP BY projection_status').fetchall())
    return {'account':account,'source':source_id(account),'authorization':'configured' if token_path.exists() else 'required','running':running,'historical_complete':row['phase']=='history','backlog':0 if row['phase']=='history' else 'initial_sync_in_progress','last_successful_sync':row.get('last_success'),'state':row,'totals':totals,'last_run_counts':counts or {},'error':error,'provider_mutations':False,'permissions':['gmail.readonly']}
def write_status(running_accounts=None,account_results=None):
    cfg=read_config(); running_accounts=set(running_accounts or []); account_results=account_results or {}; accounts={}
    for a in cfg['accounts']:
        provided=account_results.get(a);accounts[a]=provided or account_status(a,running=a in running_accounts)
    payload={'contract':'wwcx.gmail-api-sync-status.v1','configured':bool(cfg['accounts']),'accounts':accounts,'updated_at':utcnow(),'provider_mutations':False,'permissions':['gmail.readonly']};save_json(STATUS,payload);return payload

def sync_account(account,max_pages,max_messages):
    init_account(account);token=token_from_refresh(account);store=MailCorrespondenceStore(CORRESPONDENCE,source=source_id(account),source_authoritative=True,source_scope='production_native');counts={'imported':0,'duplicate':0,'excluded':0,'errors':0};row=state_row(account);pages=0;observed=int(row.get('observed') or 0);latest_history=str(row.get('history_id') or '')
    try:
        while pages<max_pages and sum(counts.values())<max_messages:
            row=state_row(account);phase=row['phase'];page_token=row.get('page_token')
            if phase=='initial':payload=full_page(account,token,page_token);ids=[str(x.get('id','')) for x in payload.get('messages',[]) if x.get('id')]
            else:
                try:payload=history_page(token,str(row.get('history_id') or ''),page_token)
                except GmailError as exc:
                    if exc.status==404:update_state(account,phase='initial',page_token=None,history_id=None,last_error='history cursor expired; full reconciliation required');continue
                    raise
                ids=history_ids(payload)
            for gid in ids:
                if sum(counts.values())>=max_messages:break
                try:status,hid=process_message(account,gid,token,store);counts[status]=counts.get(status,0)+1;latest_history=max((latest_history,hid),key=lambda x:int(x or '0'))
                except GmailError as exc:
                    if exc.status==404:counts['excluded']+=1;continue
                    counts['errors']+=1
                except Exception:counts['errors']+=1
                observed+=1
            pages+=1;next_token=payload.get('nextPageToken')
            if phase=='initial':
                if next_token:update_state(account,page_token=next_token,last_success=utcnow(),last_error=None,pages=int(row.get('pages') or 0)+1,observed=observed)
                else:
                    profile=api_request('/users/me/profile',token);latest_history=str(profile.get('historyId') or latest_history)
                    if not latest_history:raise RuntimeError('Gmail profile did not return a historyId')
                    update_state(account,phase='history',page_token=None,history_id=latest_history,last_success=utcnow(),last_error=None,pages=int(row.get('pages') or 0)+1,observed=observed);break
            else:
                response_history=str(payload.get('historyId') or latest_history or row.get('history_id') or '')
                if next_token:update_state(account,page_token=next_token,last_success=utcnow(),last_error=None,pages=int(row.get('pages') or 0)+1,observed=observed)
                else:update_state(account,page_token=None,history_id=response_history,last_success=utcnow(),last_error=None,pages=int(row.get('pages') or 0)+1,observed=observed);break
        return account_status(account,False,counts)
    except Exception as exc:
        update_state(account,last_error=(type(exc).__name__+': '+str(exc))[:300]);return account_status(account,False,counts,{'type':type(exc).__name__,'message':str(exc)[:300]})
def sync(account,max_pages,max_messages):
    cfg=read_config();targets=[account.lower()] if account else cfg['accounts']
    if not targets:raise RuntimeError('No Gmail accounts are configured')
    for a in targets:
        if a not in cfg['accounts']:raise RuntimeError('Requested Gmail account is not configured')
    write_status(running_accounts=targets);results={}
    for a in targets:results[a]=sync_account(a,max_pages,max_messages)
    return write_status(account_results=results)
def authorize(account,port):
    cfg=read_config(require_client=True)
    if account.lower() not in cfg['accounts']:raise RuntimeError('Requested Gmail account is not configured')
    if not 1024 <= port <= 65535:raise RuntimeError('OAuth callback port is invalid')
    redirect=f'http://127.0.0.1:{port}/callback';state=base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip('=');result_box={}
    params={'client_id':cfg['client']['client_id'],'redirect_uri':redirect,'response_type':'code','scope':SCOPE,'access_type':'offline','prompt':'consent','include_granted_scopes':'false','login_hint':account,'state':state}
    url=AUTH_URL+'?'+urllib.parse.urlencode(params)
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,format,*args):return
        def do_GET(self):
            parsed=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(parsed.query)
            if parsed.path!='/callback':self.send_response(404);self.end_headers();return
            if query.get('state',[''])[0]!=state:result_box['error']='OAuth state mismatch'
            elif query.get('error'):result_box['error']='Google authorization was not granted'
            elif query.get('code'):result_box['code']=query['code'][0]
            else:result_box['error']='Google callback did not contain an authorization code'
            body=b'Edge1 received the Google authorization response. You may close this browser tab.'
            self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=HTTPServer(('127.0.0.1',port),Callback);server.timeout=1
    print('Open this URL in your browser after establishing the Edge1 SSH loopback tunnel:',flush=True);print(url,flush=True)
    deadline=time.time()+600
    while time.time()<deadline and not result_box:server.handle_request()
    server.server_close()
    if not result_box:raise RuntimeError('Google authorization timed out before the callback arrived')
    if result_box.get('error'):raise RuntimeError(result_box['error'])
    result=form_post(TOKEN_URL,{'client_id':cfg['client']['client_id'],'client_secret':cfg['client']['client_secret'],'code':result_box['code'],'grant_type':'authorization_code','redirect_uri':redirect})
    if not result.get('refresh_token'):raise RuntimeError('Google did not return an offline refresh token')
    root,_,token_path=paths(account);save_json(token_path,{'refresh_token':result['refresh_token'],'scope':result.get('scope',SCOPE),'token_type':result.get('token_type','Bearer'),'updated_at':utcnow()});write_status();print('Google authorization stored on Edge1. No token or authorization code was printed.')
def show_status():
    cfg=read_config()
    for a in cfg['accounts']:init_account(a)
    if not STATUS.exists():write_status()
    print(json.dumps(load_json(STATUS),indent=2,sort_keys=True))
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True);a=sub.add_parser('authorize');a.add_argument('--account',required=True);a.add_argument('--port',type=int,default=8765);s=sub.add_parser('sync');s.add_argument('--account');s.add_argument('--max-pages',type=int,default=20);s.add_argument('--max-messages',type=int,default=1000);sub.add_parser('status');args=p.parse_args();os.umask(0o077)
    if args.cmd=='authorize':authorize(args.account.lower(),args.port)
    elif args.cmd=='sync':print(json.dumps(sync(args.account,max(1,min(args.max_pages,200)),max(1,min(args.max_messages,5000))),sort_keys=True))
    else:show_status()
if __name__=='__main__':main()
