"""Standards-oriented IRC server for the Edge1 Communications Relay."""
from __future__ import annotations
import base64,socket,socketserver,ssl,threading
from dataclasses import dataclass,field
from typing import Any
from .config import ListenerConfig,RelayConfig
from .runtime import AuthThrottle,BoundedThreadingTCPServer,TokenBucket
from .storage import Account,CommsStore
SUPPORTED_CAPS=('sasl',)
def parse_irc_line(line:str)->tuple[dict[str,str],str|None,str,list[str]]:
    tags={};prefix=None;rest=line.strip('\r\n')
    if rest.startswith('@'):
        tag_text,_,rest=rest.partition(' ')
        for item in tag_text[1:].split(';'):key,sep,value=item.partition('=');tags[key]=value if sep else ''
    if rest.startswith(':'):prefix_text,_,rest=rest.partition(' ');prefix=prefix_text[1:]
    trailing=None
    if ' :' in rest:middle,trailing=rest.split(' :',1);pieces=middle.split()
    else:pieces=rest.split()
    if not pieces:return tags,prefix,'',[]
    params=pieces[1:]
    if trailing is not None:params.append(trailing)
    return tags,prefix,pieces[0].upper(),params
def _is_operator(state:'IrcClientState')->bool:return state.account is not None and (state.account.has_role('moderator') or state.account.has_role('irc-operator'))
@dataclass
class IrcClientState:
    handler:Any;nick:str|None=None;username:str|None=None;realname:str|None=None;account:Account|None=None;cap_negotiating:bool=False;caps:set[str]=field(default_factory=set);sasl_waiting:bool=False;registered:bool=False;channels:set[str]=field(default_factory=set)
    @property
    def mask(self)->str:return f"{self.nick or '*'}!{self.username or 'unknown'}@edge1"
@dataclass
class IrcChannel:
    name:str;topic:str='';moderated:bool=False;members:dict[int,IrcClientState]=field(default_factory=dict)
class IrcHub:
    def __init__(self,cfg,store):self.cfg=cfg;self.store=store;self._lock=threading.RLock();self.clients={};self.channels={}
    def add_client(self,state):
        with self._lock:self.clients[id(state)]=state
    def remove_client(self,state,reason='Client quit'):
        with self._lock:
            for channel_name in list(state.channels):
                channel=self.channels.get(channel_name.lower())
                if channel:self._broadcast_locked(channel,f':{state.mask} QUIT :{reason}',exclude=state);channel.members.pop(id(state),None);self.channels.pop(channel_name.lower(),None) if not channel.members else None
            state.channels.clear();self.clients.pop(id(state),None)
        self.store.audit(state.account.username if state.account else None,'irc','disconnect',state.nick,'ok',{})
    def find_nick(self,nick):
        with self._lock:
            for client in self.clients.values():
                if client.nick and client.nick.lower()==nick.lower():return client
        return None
    def join(self,state,name):
        key=name.lower()
        with self._lock:
            channel=self.channels.get(key)
            if channel is None:channel=IrcChannel(name=name);self.channels[key]=channel
            channel.members[id(state)]=state;state.channels.add(channel.name);self._broadcast_locked(channel,f':{state.mask} JOIN :{channel.name}');return channel
    def part(self,state,channel,reason):
        with self._lock:self._broadcast_locked(channel,f':{state.mask} PART {channel.name} :{reason}');channel.members.pop(id(state),None);state.channels.discard(channel.name);self.channels.pop(channel.name.lower(),None) if not channel.members else None
    def kick(self,actor,channel,target,reason):
        with self._lock:self._broadcast_locked(channel,f':{actor.mask} KICK {channel.name} {target.nick or "*"} :{reason}');channel.members.pop(id(target),None);target.channels.discard(channel.name)
    def broadcast(self,channel,line,exclude=None):
        with self._lock:self._broadcast_locked(channel,line,exclude=exclude)
    @staticmethod
    def _broadcast_locked(channel,line,exclude=None):
        for member in list(channel.members.values()):
            if member is not exclude:member.handler.send_line(line)
    def channel(self,name):
        with self._lock:return self.channels.get(name.lower())
    def summary(self):
        with self._lock:return {'connected_users':sum(1 for c in self.clients.values() if c.registered),'channels':[{'name':c.name,'members':len(c.members),'topic':c.topic,'moderated':c.moderated} for c in sorted(self.channels.values(),key=lambda x:x.name.lower())]}
class IrcRequestHandler(socketserver.StreamRequestHandler):
    server:'IrcServer'
    def setup(self):super().setup();self._write_lock=threading.Lock();self._rate=TokenBucket(self.server.cfg.security.command_rate_per_second,self.server.cfg.security.command_burst);self.state=IrcClientState(handler=self);self.server.hub.add_client(self.state)
    def finish(self):
        try:self.server.hub.remove_client(self.state)
        finally:super().finish()
    def send_line(self,line):
        payload=(line[:self.server.cfg.security.max_line_bytes-2]+'\r\n').encode('utf-8',errors='replace')
        try:
            with self._write_lock:self.wfile.write(payload);self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,OSError):pass
    def numeric(self,code,text):self.send_line(f':{self.server.cfg.server_name} {code:03d} {self.state.nick or "*"} {text}')
    def handle(self):
        while True:
            try:raw=self.rfile.readline(self.server.cfg.security.max_line_bytes+1)
            except (socket.timeout,TimeoutError,OSError):self.send_line(f':{self.server.cfg.server_name} ERROR :Connection timed out');return
            if not raw:return
            if len(raw)>self.server.cfg.security.max_line_bytes:self.send_line(f':{self.server.cfg.server_name} ERROR :Line too long');return
            if not self._rate.allow():self.server.store.audit(self.state.account.username if self.state.account else None,'irc','rate_limit',self.state.nick,'denied',{});self.send_line(f':{self.server.cfg.server_name} ERROR :Rate limit exceeded');return
            line=raw.decode('utf-8',errors='replace').rstrip('\r\n')
            if not line:continue
            _,_,command,params=parse_irc_line(line)
            if command=='CAP':self.handle_cap(params)
            elif command=='AUTHENTICATE':self.handle_authenticate(params)
            elif command=='NICK':self.handle_nick(params)
            elif command=='USER':self.handle_user(params)
            elif command=='PING':token=params[-1] if params else self.server.cfg.server_name;self.send_line(f':{self.server.cfg.server_name} PONG {self.server.cfg.server_name} :{token}')
            elif command=='PONG':pass
            elif command=='QUIT':return
            elif not self.state.registered:self.numeric(451,':You have not registered')
            else:self.handle_registered(command,params)
    def handle_cap(self,params):
        if not params:return
        sub=params[0].upper()
        if sub=='LS':self.state.cap_negotiating=True;self.send_line(f':{self.server.cfg.server_name} CAP * LS :{" ".join(SUPPORTED_CAPS)}')
        elif sub=='REQ' and len(params)>=2:
            requested={x for x in params[-1].split() if x}
            if requested.issubset(SUPPORTED_CAPS):self.state.caps.update(requested);self.send_line(f':{self.server.cfg.server_name} CAP * ACK :{" ".join(sorted(requested))}')
            else:self.send_line(f':{self.server.cfg.server_name} CAP * NAK :{" ".join(sorted(requested))}')
        elif sub=='END':self.state.cap_negotiating=False;self.try_register()
    def handle_authenticate(self,params):
        peer=str(self.client_address[0])
        if not self.server.auth_throttle.allowed(peer):self.numeric(904,':SASL temporarily rate limited');return
        if not params:self.numeric(904,':SASL authentication failed');return
        token=params[0]
        if token.upper()=='PLAIN':self.state.sasl_waiting=True;self.send_line('AUTHENTICATE +');return
        if not self.state.sasl_waiting:self.numeric(904,':SASL authentication failed');return
        self.state.sasl_waiting=False
        try:
            parts=base64.b64decode(token,validate=True).decode().split('\x00')
            if len(parts)!=3:raise ValueError()
            authcid,password=parts[1],parts[2]
        except (ValueError,UnicodeError):self.server.auth_throttle.failure(peer);self.numeric(904,':SASL authentication failed');return
        account=self.server.store.authenticate(authcid,password,protocol='irc')
        if account is None:self.server.auth_throttle.failure(peer);self.numeric(904,':SASL authentication failed');return
        self.server.auth_throttle.success(peer);self.state.account=account;self.numeric(900,f'{self.state.nick or "*"}!{self.state.username or "unknown"}@edge1 {account.username} :You are now logged in');self.numeric(903,':SASL authentication successful');self.try_register()
    def handle_nick(self,params):
        if not params:self.numeric(431,':No nickname given');return
        nick=params[0][:32];allowed='[]\\`_^{|}-'
        if not nick or not (nick[0].isalpha() or nick[0] in allowed) or any(not(c.isalnum() or c in allowed) for c in nick[1:]):self.numeric(432,f'{nick} :Erroneous nickname');return
        existing=self.server.hub.find_nick(nick)
        if existing is not None and existing is not self.state:self.numeric(433,f'{nick} :Nickname is already in use');return
        old_mask,old_nick=self.state.mask,self.state.nick;self.state.nick=nick
        if old_nick and self.state.registered:
            for name in list(self.state.channels):
                channel=self.server.hub.channel(name)
                if channel:self.server.hub.broadcast(channel,f':{old_mask} NICK :{nick}')
        self.try_register()
    def handle_user(self,params):
        if len(params)<4:self.numeric(461,'USER :Not enough parameters');return
        if self.state.registered:self.numeric(462,':You may not reregister');return
        username=params[0][:32]
        if not username or any(c in username for c in ' \r\n@!'):self.numeric(461,'USER :Invalid username');return
        self.state.username=username;self.state.realname=params[3][:128];self.try_register()
    def try_register(self):
        if self.state.registered or self.state.cap_negotiating or not self.state.nick or not self.state.username:return
        if self.state.account is None and (self.server.cfg.security.require_auth or not self.server.cfg.security.allow_anonymous_irc):return
        self.state.registered=True;self.numeric(1,f':Welcome to {self.server.cfg.network_name} IRC, {self.state.mask}');self.numeric(2,f':Your host is {self.server.cfg.server_name}');self.numeric(5,f'CHANTYPES=# PREFIX=(o)@ NETWORK={self.server.cfg.network_name} CASEMAPPING=ascii :are supported by this server');self.server.store.audit(self.state.account.username if self.state.account else None,'irc','connect',self.state.nick,'ok',{})
    def handle_registered(self,command,params):
        actions={'JOIN':self.handle_join,'PART':self.handle_part,'TOPIC':self.handle_topic,'NAMES':self.handle_names,'WHO':self.handle_who,'KICK':self.handle_kick,'MODE':self.handle_mode}
        if command in {'PRIVMSG','NOTICE'}:self.handle_message(command,params)
        elif command in actions:actions[command](params)
        else:self.numeric(421,f'{command} :Unknown command')
    def handle_join(self,params):
        if not params:self.numeric(461,'JOIN :Not enough parameters');return
        for name in params[0].split(',')[:16]:
            if len(self.state.channels)>=64:self.numeric(405,f'{name} :You have joined too many channels');break
            if not name.startswith('#') or len(name)>64 or any(c in name for c in ' ,\r\n'):self.numeric(403,f'{name} :No such channel');continue
            channel=self.server.hub.join(self.state,name);self.numeric(332 if channel.topic else 331,f'{channel.name} :{channel.topic or "No topic is set"}');self.send_names(channel)
            if self.server.cfg.retention.irc_history_enabled:self.server.store.record_irc(channel.name,self.state.account.username if self.state.account else None,self.state.nick or '*','join',None)
    def handle_part(self,params):
        if not params:self.numeric(461,'PART :Not enough parameters');return
        channel=self.server.hub.channel(params[0])
        if channel is None or id(self.state) not in channel.members:self.numeric(442,f'{params[0]} :You are not on that channel');return
        self.server.hub.part(self.state,channel,params[1] if len(params)>1 else 'Leaving')
    def handle_message(self,command,params):
        if len(params)<2:self.numeric(461,'PRIVMSG :Not enough parameters') if command=='PRIVMSG' else None;return
        target,text=params[0],params[1];line=f':{self.state.mask} {command} {target} :{text}'
        if target.startswith('#'):
            channel=self.server.hub.channel(target)
            if channel is None:self.numeric(403,f'{target} :No such channel');return
            if id(self.state) not in channel.members:self.numeric(404,f'{target} :Cannot send to channel');return
            if channel.moderated and not _is_operator(self.state):self.numeric(404,f'{target} :Cannot send to moderated channel');return
            self.server.hub.broadcast(channel,line,exclude=self.state)
            if command=='PRIVMSG' and self.server.cfg.retention.irc_history_enabled:self.server.store.record_irc(channel.name,self.state.account.username if self.state.account else None,self.state.nick or '*','privmsg',text)
        else:
            peer=self.server.hub.find_nick(target)
            if peer is None:self.numeric(401,f'{target} :No such nick');return
            peer.handler.send_line(line)
        self.server.store.audit(self.state.account.username if self.state.account else None,'irc',command.lower(),target,'ok',{'bytes':len(text.encode())})
    def handle_topic(self,params):
        if not params:self.numeric(461,'TOPIC :Not enough parameters');return
        channel=self.server.hub.channel(params[0])
        if channel is None:self.numeric(403,f'{params[0]} :No such channel');return
        if len(params)==1:self.numeric(332 if channel.topic else 331,f'{channel.name} :{channel.topic or "No topic is set"}');return
        if id(self.state) not in channel.members:self.numeric(442,f'{channel.name} :You are not on that channel');return
        channel.topic=params[1][:390];self.server.hub.broadcast(channel,f':{self.state.mask} TOPIC {channel.name} :{channel.topic}');self.server.store.audit(self.state.account.username if self.state.account else None,'irc','topic',channel.name,'ok',{'bytes':len(channel.topic.encode())})
    def handle_mode(self,params):
        if not params or not params[0].startswith('#'):self.numeric(461,'MODE :Not enough parameters');return
        channel=self.server.hub.channel(params[0])
        if channel is None:self.numeric(403,f'{params[0]} :No such channel');return
        if len(params)==1:self.numeric(324,f'{channel.name} {"+m" if channel.moderated else "+"}');return
        if not _is_operator(self.state):self.numeric(482,f'{channel.name} :You are not a channel operator');return
        mode=params[1]
        if mode not in {'+m','-m'}:self.numeric(472,f'{mode} :is unknown mode char to me');return
        channel.moderated=mode=='+m';self.server.hub.broadcast(channel,f':{self.state.mask} MODE {channel.name} {mode}')
    def handle_kick(self,params):
        if len(params)<2:self.numeric(461,'KICK :Not enough parameters');return
        channel=self.server.hub.channel(params[0])
        if channel is None:self.numeric(403,f'{params[0]} :No such channel');return
        if not _is_operator(self.state):self.numeric(482,f'{channel.name} :You are not a channel operator');return
        target=self.server.hub.find_nick(params[1])
        if target is None or id(target) not in channel.members:self.numeric(441,f'{params[1]} {channel.name} :They are not on that channel');return
        self.server.hub.kick(self.state,channel,target,params[2] if len(params)>2 else self.state.nick or 'operator')
    def handle_names(self,params):
        if params:
            channel=self.server.hub.channel(params[0])
            if channel:self.send_names(channel)
    def send_names(self,channel):
        names=' '.join(sorted(('' if not _is_operator(member) else '@')+(member.nick or '*') for member in channel.members.values()));self.numeric(353,f'= {channel.name} :{names}');self.numeric(366,f'{channel.name} :End of /NAMES list')
    def handle_who(self,params):
        if not params:return
        channel=self.server.hub.channel(params[0])
        if channel:
            for member in list(channel.members.values()):self.numeric(352,f'{channel.name} {member.username or "unknown"} edge1 {self.server.cfg.server_name} {member.nick or "*"} H :0 {member.realname or ""}')
        self.numeric(315,f'{params[0]} :End of /WHO list')
class IrcServer(BoundedThreadingTCPServer):
    def __init__(self,address,cfg,store,listener=None):
        self.cfg=cfg;self.store=store;self.hub=IrcHub(cfg,store);self.listener=listener or cfg.irc;self.auth_throttle=AuthThrottle(cfg.security.auth_failures_per_minute);super().__init__(address,IrcRequestHandler,bind_and_activate=False);self.configure_runtime_limits(max_connections=cfg.security.max_connections,max_connections_per_ip=cfg.security.max_connections_per_ip,idle_timeout_seconds=cfg.security.idle_timeout_seconds);self.server_bind();self.server_activate()
        if self.listener.tls:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.options|=ssl.OP_NO_COMPRESSION;context.load_cert_chain(self.listener.cert_file or '',self.listener.key_file or '');self.socket=context.wrap_socket(self.socket,server_side=True)
