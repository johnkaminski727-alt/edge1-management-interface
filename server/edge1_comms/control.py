"""Loopback-only read-only HTTP control surface for Edge1 Communications Relay."""
from __future__ import annotations
import json,urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from typing import Any,Callable
from .config import RelayConfig,sanitized_config
from .news_reader import list_news_page
from .storage import CommsStore
class ControlHandler(SimpleHTTPRequestHandler):
    server:'ControlServer'
    def __init__(self,*args:Any,**kwargs:Any)->None: server=args[2]; super().__init__(*args,directory=str(server.web_root),**kwargs)
    def log_message(self,format:str,*args:Any)->None:return
    def end_headers(self)->None:
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Security-Policy',"default-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'"); self.send_header('Permissions-Policy','camera=(), geolocation=(), microphone=()'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); super().end_headers()
    def send_json(self,status:HTTPStatus,payload:dict[str,Any]|list[Any])->None:
        body=json.dumps(payload,sort_keys=True,indent=2).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def _limit(self,params:dict[str,list[str]],default:int=100,maximum:int=250)->int:
        try:return max(1,min(int(params.get('limit',[str(default)])[0]),maximum))
        except ValueError:return default
    def _offset(self,params:dict[str,list[str]])->int:
        try:return max(0,min(int(params.get('offset',['0'])[0]),1_000_000))
        except ValueError:return 0
    def _news_sources(self)->list[dict[str,Any]]:
        state={item['source_name']:item for item in self.server.store.list_ingest_state()}
        sources=[]
        for source in sanitized_config(self.server.cfg)['ingestion']['sources']:
            item=dict(source); current=state.get(str(item.get('name')),{}); item['cursor']=current.get('cursor'); item['items']=current.get('items',0); item['updated_at_utc']=current.get('updated_at_utc'); sources.append(item)
        return sources
    def do_GET(self)->None:
        parsed=urllib.parse.urlparse(self.path); params=urllib.parse.parse_qs(parsed.query)
        if parsed.path=='/healthz': self.send_json(HTTPStatus.OK,{'status':'ok','service':'edge1-comms-relay','version':'1.0.0'}); return
        if parsed.path=='/api/comms/status': self.send_json(HTTPStatus.OK,{'service':'edge1-comms-relay','version':'1.0.0','config':sanitized_config(self.server.cfg),'storage':self.server.store.stats(),'irc':self.server.irc_summary(),'federation':{'irc':'disabled','nntp':'disabled'}}); return
        if parsed.path=='/api/comms/news/groups': self.send_json(HTTPStatus.OK,self.server.store.list_groups()); return
        if parsed.path=='/api/comms/news/sources': self.send_json(HTTPStatus.OK,self._news_sources()); return
        if parsed.path.startswith('/api/comms/news/articles/'):
            value=parsed.path.removeprefix('/api/comms/news/articles/')
            try:article_id=int(value)
            except ValueError:self.send_json(HTTPStatus.BAD_REQUEST,{'error':'invalid_article_id'});return
            article=self.server.store.get_news_article(article_id)
            if article is None:self.send_json(HTTPStatus.NOT_FOUND,{'error':'article_not_found'});return
            self.send_json(HTTPStatus.OK,article);return
        prefix='/api/comms/news/groups/'
        if parsed.path.startswith(prefix):
            tail=urllib.parse.unquote(parsed.path[len(prefix):])
            if tail.endswith('/articles'):
                group=tail[:-len('/articles')]
                info=self.server.store.group_info(group)
                if info is None:self.send_json(HTTPStatus.NOT_FOUND,{'error':'group_not_found'});return
                search=params.get('q',[''])[0][:256]
                source=params.get('source',[''])[0][:128]
                page=list_news_page(self.server.store,group,limit=self._limit(params,50,100),offset=self._offset(params),search=search,source=source)
                self.send_json(HTTPStatus.OK,{'group':info,'query':search,'source':source,**page});return
            info=self.server.store.group_info(tail)
            if info is None:self.send_json(HTTPStatus.NOT_FOUND,{'error':'group_not_found'});return
            self.send_json(HTTPStatus.OK,info);return
        irc_prefix='/api/comms/irc/channels/'
        if parsed.path.startswith(irc_prefix) and parsed.path.endswith('/history'):
            channel=urllib.parse.unquote(parsed.path[len(irc_prefix):-len('/history')])
            if not channel.startswith('#') or len(channel)>128:
                self.send_json(HTTPStatus.BAD_REQUEST,{'error':'invalid_channel'});return
            events=[]
            for item in self.server.store.recent_irc(channel,self._limit(params,50,100)):
                events.append({key:item.get(key) for key in ('created_at_utc','event','nick','body')})
            self.send_json(HTTPStatus.OK,{'channel':channel,'events':events,'mode':'read_only'});return
        if parsed.path=='/api/comms/audit':
            self.send_json(HTTPStatus.OK,self.server.store.recent_audit(self._limit(params,100,500))); return
        if parsed.path.startswith('/api/'): self.send_json(HTTPStatus.NOT_FOUND,{'error':'not_found'}); return
        super().do_GET()
    def do_POST(self)->None:self.send_json(HTTPStatus.METHOD_NOT_ALLOWED,{'error':'read_only_control_api'})
    do_PUT=do_POST; do_PATCH=do_POST; do_DELETE=do_POST
class ControlServer(ThreadingHTTPServer):
    daemon_threads=True; allow_reuse_address=True
    def __init__(self,address:tuple[str,int],cfg:RelayConfig,store:CommsStore,*,web_root:str|Path,irc_summary:Callable[[],dict[str,Any]]|None=None)->None:
        self.cfg=cfg;self.store=store;self.web_root=Path(web_root);self._irc_summary=irc_summary;super().__init__(address,ControlHandler)
    def irc_summary(self)->dict[str,Any]:
        if self._irc_summary is None:return {'connected_users':None,'channels':[],'mode':'standalone-control'}
        payload=self._irc_summary();payload['mode']='live';return payload
