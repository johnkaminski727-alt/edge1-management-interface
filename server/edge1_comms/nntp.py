"""NNTP reader/poster service for the Edge1 Communications Relay."""
from __future__ import annotations
import email,email.policy,socket,socketserver,ssl
from typing import Any
from .config import ListenerConfig,RelayConfig
from .runtime import AuthThrottle,BoundedThreadingTCPServer,TokenBucket
from .storage import Account,CommsStore
def dot_stuff(lines):return [('.'+line) if line.startswith('.') else line for line in lines]
def parse_range(value):
    if '-' not in value:
        try:number=int(value)
        except ValueError:return None,None
        return number,number
    left,right=value.split('-',1)
    try:return int(left) if left else None,int(right) if right else None
    except ValueError:return None,None
class NntpRequestHandler(socketserver.StreamRequestHandler):
    server:'NntpServer'
    def setup(self):super().setup();self.account=None;self.pending_user=None;self.group=None;self.current_article=None;self._rate=TokenBucket(self.server.cfg.security.command_rate_per_second,self.server.cfg.security.command_burst)
    def send_line(self,text):
        try:self.wfile.write((text+'\r\n').encode('utf-8',errors='replace'));self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,OSError):pass
    def multiline(self,status,lines):self.send_line(status);[self.send_line(line) for line in dot_stuff(lines)];self.send_line('.')
    def handle(self):
        self.send_line(f'200 {self.server.cfg.server_name} WW.CX NNTP service ready - posting requires authorization')
        while True:
            try:raw=self.rfile.readline(self.server.cfg.security.max_line_bytes+1)
            except (socket.timeout,TimeoutError,OSError):self.send_line('400 idle timeout');return
            if not raw:return
            if len(raw)>self.server.cfg.security.max_line_bytes:self.send_line('500 command line too long');return
            if not self._rate.allow():self.server.store.audit(self.account.username if self.account else None,'nntp','rate_limit',None,'denied',{});self.send_line('400 command rate exceeded');return
            text=raw.decode('utf-8',errors='replace').rstrip('\r\n')
            if not text:self.send_line('500 empty command');continue
            command,_,argument=text.partition(' ');command=command.upper();argument=argument.strip()
            if command=='QUIT':self.send_line('205 closing connection');return
            if command=='CAPABILITIES':self.handle_capabilities()
            elif command=='MODE' and argument.upper()=='READER':self.send_line('200 reader mode')
            elif command=='AUTHINFO':self.handle_authinfo(argument)
            elif command=='LIST':self.handle_list(argument)
            elif command=='GROUP':self.handle_group(argument)
            elif command in {'ARTICLE','HEAD','BODY','STAT'}:self.handle_article(command,argument)
            elif command in {'OVER','XOVER'}:self.handle_over(argument)
            elif command=='NEXT':self.handle_move(1)
            elif command=='LAST':self.handle_move(-1)
            elif command=='POST':self.handle_post()
            elif command in {'IHAVE','CHECK','TAKETHIS'}:self.send_line('502 federation disabled by local policy')
            else:self.send_line('500 command not recognized')
    def handle_capabilities(self):self.multiline('101 capability list follows',['VERSION 2','READER','POST','AUTHINFO USER','OVER','LIST ACTIVE NEWSGROUPS OVERVIEW.FMT','IMPLEMENTATION WW.CX-Edge1-Comms/1.0'])
    def can_read(self):return self.account is not None or self.server.cfg.security.allow_anonymous_nntp_read
    def handle_authinfo(self,argument):
        peer=str(self.client_address[0])
        if not self.server.auth_throttle.allowed(peer):self.send_line('481 authentication temporarily rate limited');return
        sub,_,value=argument.partition(' ');sub=sub.upper()
        if sub=='USER' and value:self.pending_user=value.strip()[:64];self.send_line('381 password required');return
        if sub=='PASS' and self.pending_user:
            account=self.server.store.authenticate(self.pending_user,value,protocol='nntp');self.pending_user=None
            if account is None:self.server.auth_throttle.failure(peer);self.send_line('481 authentication rejected');return
            self.server.auth_throttle.success(peer);self.account=account;self.send_line('281 authentication accepted');return
        self.send_line('501 syntax: AUTHINFO USER name / AUTHINFO PASS password')
    def handle_list(self,argument):
        if not self.can_read():self.send_line('480 authentication required');return
        variant=argument.upper() if argument else 'ACTIVE';groups=self.server.store.list_groups()
        if variant in {'','ACTIVE'}:self.multiline('215 list of newsgroups follows',[f"{r['name']} {r['high']} {r['low']} {'m' if r['moderated'] else 'y'}" for r in groups])
        elif variant=='NEWSGROUPS':self.multiline('215 descriptions follow',[f"{r['name']} {r['description']}" for r in groups])
        elif variant=='OVERVIEW.FMT':self.multiline('215 information follows',['Subject:','From:','Date:','Message-ID:','References:',':bytes',':lines'])
        else:self.send_line('501 unsupported LIST variant')
    def handle_group(self,name):
        if not self.can_read():self.send_line('480 authentication required');return
        info=self.server.store.group_info(name)
        if info is None:self.send_line('411 no such newsgroup');return
        self.group=name;self.current_article=int(info['low']) if int(info['low'])>0 else None;self.send_line(f"211 {info['count']} {info['low']} {info['high']} {name}")
    def resolve_article(self,argument):
        if argument.startswith('<') and argument.endswith('>'):return self.server.store.get_article(message_id=argument)
        if argument:
            try:number=int(argument)
            except ValueError:return None
            return self.server.store.get_article(group_name=self.group,article_id=number) if self.group else None
        if self.group and self.current_article is not None:return self.server.store.get_article(group_name=self.group,article_id=self.current_article)
        return None
    @staticmethod
    def article_header_lines(article):
        headers=article['headers'];preferred=['From','Subject','Newsgroups','Message-ID','Date','References'];lines=[];seen=set()
        for name in preferred:
            if name in headers and headers[name]:lines.append(f'{name}: {headers[name]}');seen.add(name.lower())
        for name,value in sorted(headers.items()):
            if name.lower() not in seen and value:lines.append(f'{name}: {value}')
        return lines
    def handle_article(self,command,argument):
        if not self.can_read():self.send_line('480 authentication required');return
        article=self.resolve_article(argument)
        if article is None:self.send_line('430 no such article found' if argument.startswith('<') else '423 no such article number in this group');return
        self.current_article=int(article['id']);code={'ARTICLE':220,'HEAD':221,'BODY':222,'STAT':223}[command];status=f"{code} {article['id']} {article['message_id']} article follows"
        if command=='STAT':self.send_line(status);return
        headers=self.article_header_lines(article);body=str(article['body']).splitlines();self.multiline(status,headers if command=='HEAD' else body if command=='BODY' else headers+['']+body)
    def handle_over(self,argument):
        if not self.can_read():self.send_line('480 authentication required');return
        if not self.group:self.send_line('412 no newsgroup selected');return
        if argument:
            start,end=parse_range(argument)
            if start is None and end is None:self.send_line('501 invalid range');return
        else:start=end=self.current_article
        lines=[]
        for row in self.server.store.articles_for_group(self.group,start=start,end=end,limit=5000):
            body=str(row['body']);lines.append('\t'.join([str(row['id']),str(row['subject']),str(row['author']),str(row['date_rfc5322']),str(row['message_id']),str(row['references_text'] or ''),str(len(body.encode())),str(len(body.splitlines()))]))
        self.multiline('224 overview information follows',lines)
    def handle_move(self,direction):
        if not self.group:self.send_line('412 no newsgroup selected');return
        ids=[int(x['id']) for x in self.server.store.articles_for_group(self.group,limit=5000)]
        if not ids:self.send_line('420 no current article selected');return
        if self.current_article not in ids:self.current_article=ids[0]
        else:
            index=ids.index(self.current_article)+direction
            if index<0 or index>=len(ids):self.send_line('421 no next article' if direction>0 else '422 no previous article');return
            self.current_article=ids[index]
        article=self.server.store.get_article(group_name=self.group,article_id=self.current_article)
        if article:self.send_line(f"223 {article['id']} {article['message_id']} article retrieved")
    def handle_post(self):
        if self.account is None and not self.server.cfg.security.allow_anonymous_nntp_post:self.send_line('480 authentication required');return
        self.send_line('340 send article; end with <CR-LF>.<CR-LF>');collected=[];total=0
        while True:
            try:raw=self.rfile.readline(self.server.cfg.security.max_line_bytes+1)
            except (socket.timeout,TimeoutError,OSError):self.send_line('441 posting failed - timeout');return
            if not raw:return
            if len(raw)>self.server.cfg.security.max_line_bytes:self.send_line('441 posting failed - line too long');return
            if raw in {b'.\r\n',b'.\n'}:break
            if raw.startswith(b'..'):raw=raw[1:]
            total+=len(raw)
            if total>self.server.cfg.security.max_article_bytes:self.send_line('441 posting failed - article too large');return
            collected.append(raw)
        raw_article=b''.join(collected).decode('utf-8',errors='replace')
        try:message=email.message_from_string(raw_article,policy=email.policy.default)
        except (TypeError,ValueError):self.send_line('441 posting failed - invalid article');return
        groups=[x.strip().lower() for x in str(message.get('Newsgroups','')).split(',') if x.strip()]
        if len(groups)!=1:self.send_line('441 posting failed - exactly one Newsgroups value is required');return
        group=groups[0];info=self.server.store.group_info(group)
        if info is None:self.send_line('441 posting failed - unknown newsgroup');return
        if self.account is None:
            if info['moderated']:self.send_line('440 anonymous posting is not permitted for moderated groups');return
        elif not self.server.store.can_post(self.account,group):self.send_line('440 posting not permitted for this group');return
        subject=str(message.get('Subject','')).strip();supplied_author=str(message.get('From','')).strip()
        if not subject or not supplied_author:self.send_line('441 posting failed - From and Subject are required');return
        author=supplied_author if self.account is None else f'{self.account.username} <{self.account.username}@users.ww.cx>';body=message.get_body(preferencelist=('plain',)) if message.is_multipart() else message
        try:body_text=body.get_content() if body is not None else ''
        except (LookupError,UnicodeError):self.send_line('441 posting failed - invalid text encoding');return
        if not isinstance(body_text,str):self.send_line('441 posting failed - text article required');return
        extra={}
        for key,value in message.items():
            if key.lower().startswith('x-') and key.lower() not in {'x-authenticated-user','x-wwcx-authenticated-user'}:extra[key]=str(value)
        if self.account is not None:extra['X-WWCX-Authenticated-User']=self.account.username
        try:article=self.server.store.post_article(group_name=group,author=author,account=self.account.username if self.account else None,subject=subject,body=body_text.rstrip('\r\n'),references=str(message.get('References','')).strip(),extra_headers=extra,message_id=str(message.get('Message-ID','')).strip() or None,server_name=self.server.cfg.server_name)
        except Exception as exc:self.server.store.audit(self.account.username if self.account else None,'nntp','post',group,'error',{'error_type':type(exc).__name__});self.send_line('441 posting failed');return
        self.send_line(f"240 article received {article['message_id']}")
class NntpServer(BoundedThreadingTCPServer):
    def __init__(self,address,cfg,store,listener=None):
        self.cfg=cfg;self.store=store;self.listener=listener or cfg.nntp;self.auth_throttle=AuthThrottle(cfg.security.auth_failures_per_minute);super().__init__(address,NntpRequestHandler,bind_and_activate=False);self.configure_runtime_limits(max_connections=cfg.security.max_connections,max_connections_per_ip=cfg.security.max_connections_per_ip,idle_timeout_seconds=cfg.security.idle_timeout_seconds);self.server_bind();self.server_activate()
        if self.listener.tls:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.options|=ssl.OP_NO_COMPRESSION;context.load_cert_chain(self.listener.cert_file or '',self.listener.key_file or '');self.socket=context.wrap_socket(self.socket,server_side=True)
