#!/usr/bin/env python3
"""Production-readiness validation for WW.CX Edge1 Communications Relay."""
from __future__ import annotations
import base64,json,secrets,socket,sqlite3,sys,tempfile,threading,urllib.request
from dataclasses import replace
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1];SERVER_ROOT=REPO_ROOT/'server';sys.path.insert(0,str(SERVER_ROOT))
from edge1_comms.config import ConfigError,ListenerConfig,RelayConfig,config_from_dict
from edge1_comms.config_control import apply_candidate,rollback_last,stage_config
from edge1_comms.control import ControlServer
from edge1_comms.irc import IrcServer,parse_irc_line
from edge1_comms.nntp import NntpServer,parse_range
from edge1_comms.runtime import AuthThrottle,TokenBucket
from edge1_comms.storage import CommsStore
TEST_SECRET=secrets.token_urlsafe(24)
def check(c,m):
    if not c:raise AssertionError(m)
def send_line(s,line):s.sendall((line+'\r\n').encode())
def recv_some(s):return s.recv(8192)
def recv_until(s,marker,limit=30):
    data=bytearray()
    for _ in range(limit):
        chunk=s.recv(4096)
        if not chunk:break
        data.extend(chunk)
        if marker in data:break
    return bytes(data)
def start(server):t=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.02},daemon=True);t.start();return t
def stop(server,t):server.shutdown();server.server_close();t.join(2);check(not t.is_alive(),'server did not stop')
def validate_config():
    p=json.loads((REPO_ROOT/'config/comms-relay.example.json').read_text());cfg=config_from_dict(p);check(cfg.security.max_connections_per_ip<cfg.security.max_connections,'unsafe connection defaults');check(cfg.security.password_iterations>=600000,'password default not hardened');unsafe=json.loads(json.dumps(p));unsafe['network_exposure']['enabled']=True;unsafe['listeners']['irc']['host']='0.0.0.0';unsafe['listeners']['irc']['tls']=False
    try:config_from_dict(unsafe);raise AssertionError('plaintext public bind accepted')
    except ConfigError:pass
    control=json.loads(json.dumps(p));control['listeners']['control']['host']='0.0.0.0'
    try:config_from_dict(control);raise AssertionError('public control bind accepted')
    except ConfigError:pass
def validate_config_control(tmp):
    example=REPO_ROOT/'config/comms-relay.example.json';state=tmp/'cc';target=tmp/'run.json';old=json.loads(example.read_text());old['network_name']='OLD';target.write_text(json.dumps(old));check(len(stage_config(example,state)['sha256'])==64,'candidate hash missing');a=apply_candidate(state,target);check(a['backup'],'backup missing');rollback_last(state,target);check(json.loads(target.read_text())['network_name']=='OLD','rollback failed')
def validate_runtime():
    bucket=TokenBucket(1,2);check(bucket.allow() and bucket.allow() and not bucket.allow(),'token bucket failed');throttle=AuthThrottle(2);check(throttle.allowed('x'),'initial throttle denied');throttle.failure('x');throttle.failure('x');check(not throttle.allowed('x'),'auth throttle failed');throttle.success('x');check(throttle.allowed('x'),'auth throttle did not reset')
def validate_storage(tmp):
    db=tmp/'comms.sqlite3';store=CommsStore(db,password_iterations=100000,min_password_length=12,default_news_days=10,irc_history_days=2,audit_days=2)
    try:store.add_account('short','tiny',['user']);raise AssertionError('short password accepted')
    except ValueError:pass
    store.add_account('john',TEST_SECRET,['founder']);check(store.authenticate('john',TEST_SECRET,protocol='test') is not None,'authentication failed')
    with sqlite3.connect(db) as c:check(c.execute('PRAGMA journal_mode').fetchone()[0].lower()=='wal','WAL not active');check(c.execute("SELECT password_iterations FROM accounts WHERE username='john'").fetchone()[0]==100000,'per-account iterations missing')
    acc=store.get_account('john');check(acc and store.can_post(acc,'wwcx.announce'),'founder moderation failed');article=store.post_article(group_name='wwcx.test',author='John <john@users.ww.cx>',account='john',subject='storage',body='body');check(article['message_id'].startswith('<'),'message id missing');store.record_irc('#old','john','john','privmsg','old');store.audit('john','test','old',None,'ok',{})
    with store.connect() as c:c.execute("UPDATE irc_history SET created_at_utc='2000-01-01T00:00:00Z'");c.execute("UPDATE audit SET created_at_utc='2000-01-01T00:00:00Z'");c.execute("UPDATE articles SET created_at_utc='2000-01-01T00:00:00Z'")
    removed=store.prune_retention();check(removed['articles']==1 and removed['irc_history']==1 and removed['audit']>=1,'retention prune failed');return store
def auth_cfg(tmp):
    base=RelayConfig();return replace(base,database_path=str(tmp/'comms.sqlite3'),security=replace(base.security,password_iterations=100000,idle_timeout_seconds=30,max_connections=16,max_connections_per_ip=4,command_rate_per_second=50,command_burst=100),retention=replace(base.retention,maintenance_interval_seconds=60))
def test_irc(cfg,store):
    server=IrcServer(('127.0.0.1',0),cfg,store,listener=ListenerConfig('127.0.0.1',16667));t=start(server)
    try:
        s=socket.create_connection(server.server_address,timeout=2);s.settimeout(2);send_line(s,'CAP LS 302');check(b'sasl' in recv_until(s,b' CAP * LS '),'CAP missing sasl');send_line(s,'NICK john');send_line(s,'USER john 0 * :John');send_line(s,'CAP REQ :sasl');recv_until(s,b' CAP * ACK ');send_line(s,'AUTHENTICATE PLAIN');recv_until(s,b'AUTHENTICATE +');payload=base64.b64encode(('john\x00john\x00'+TEST_SECRET).encode()).decode();send_line(s,'AUTHENTICATE '+payload);check(b' 903 ' in recv_until(s,b' 903 '),'SASL failed');send_line(s,'CAP END');check(b' 001 john ' in recv_until(s,b' 001 john '),'registration failed');send_line(s,'JOIN #edge1');check(b' 366 john #edge1 ' in recv_until(s,b' 366 john #edge1 '),'JOIN failed');send_line(s,'MODE #edge1 +m');check(b'MODE #edge1 +m' in recv_until(s,b'MODE #edge1 +m'),'operator mode failed');send_line(s,'QUIT :done');s.close()
    finally:stop(server,t)
def test_nntp(cfg,store):
    server=NntpServer(('127.0.0.1',0),cfg,store,listener=ListenerConfig('127.0.0.1',1119));t=start(server)
    try:
        s=socket.create_connection(server.server_address,timeout=2);s.settimeout(2);check(recv_some(s).startswith(b'200 '),'greeting missing');send_line(s,'AUTHINFO USER john');check(recv_some(s).startswith(b'381 '),'USER rejected');send_line(s,'AUTHINFO PASS '+TEST_SECRET);check(recv_some(s).startswith(b'281 '),'PASS rejected');send_line(s,'POST');check(recv_some(s).startswith(b'340 '),'POST rejected');s.sendall(b'From: Spoof <spoof@example.test>\r\nSubject: Production validation\r\nNewsgroups: wwcx.announce\r\n\r\nhello\r\n.\r\n');check(recv_some(s).startswith(b'240 '),'moderated founder post failed');rows=store.articles_for_group('wwcx.announce');check(rows[-1]['author'].startswith('john <john@users.ww.cx>'),'authenticated From not canonicalized');check(rows[-1]['headers']['X-WWCX-Authenticated-User']=='john','authenticated header missing');send_line(s,'QUIT');s.close()
    finally:stop(server,t)
    anon=replace(cfg,security=replace(cfg.security,require_auth=False,allow_anonymous_nntp_read=True,allow_anonymous_nntp_post=True));server=NntpServer(('127.0.0.1',0),anon,store,listener=ListenerConfig('127.0.0.1',1119));t=start(server)
    try:
        s=socket.create_connection(server.server_address,timeout=2);s.settimeout(2);recv_some(s);send_line(s,'POST');recv_some(s);s.sendall(b'From: Anonymous <anon@example.test>\r\nSubject: denied\r\nNewsgroups: wwcx.announce\r\n\r\nhello\r\n.\r\n');check(recv_some(s).startswith(b'440 '),'anonymous moderated post was accepted');s.close()
    finally:stop(server,t)
def test_control(cfg,store,tmp):
    web=tmp/'web';web.mkdir();(web/'index.html').write_text('ok');server=ControlServer(('127.0.0.1',0),cfg,store,web_root=web,irc_summary=lambda:{'connected_users':0,'channels':[]});t=start(server)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{server.server_address[1]}/healthz',timeout=2) as r:p=json.loads(r.read())
        check(p['status']=='ok' and p['version']=='1.0.0','healthz failed')
    finally:stop(server,t)
def main():
    validate_config();validate_runtime();check(parse_range('4-9')==(4,9),'range parser failed');check(parse_irc_line(':a PING :b')[2]=='PING','IRC parser failed')
    with tempfile.TemporaryDirectory(prefix='edge1-comms-') as name:
        tmp=Path(name);validate_config_control(tmp);store=validate_storage(tmp);cfg=auth_cfg(tmp);cfg.validate();test_irc(cfg,store);test_nntp(cfg,store);test_control(cfg,store,tmp)
    print('PASS validate_comms_relay production readiness');return 0
if __name__=='__main__':raise SystemExit(main())
