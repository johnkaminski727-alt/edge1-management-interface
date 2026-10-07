#!/usr/bin/env python3
"""Loopback-only MCP compatibility multiplexer for Edge1.

Fixed routing only:
- edge1_agent_* -> full Agent Shell on 127.0.0.1:8114
- edge1.*       -> bounded Operator MCP on 127.0.0.1:8102
All other MCP lifecycle traffic is proxied to the Agent Shell. tools/list merges
both catalogs. No arbitrary upstream URL, command, path, or tool remapping is accepted.
"""
from __future__ import annotations
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST='127.0.0.1'
PORT=8115
PATH='/mcp'
AGENT=('127.0.0.1',8114)
OPERATOR=('127.0.0.1',8102)
MAX_BODY=1024*1024
PASS_HEADERS=('authorization','accept','content-type','mcp-session-id','mcp-protocol-version','mcp-method','mcp-name','origin')
RETURN_HEADERS=('content-type','mcp-session-id','mcp-protocol-version')

def upstream(target:tuple[str,int], method:str, path:str, body:bytes, headers:dict[str,str])->tuple[int,dict[str,str],bytes]:
    conn=http.client.HTTPConnection(target[0],target[1],timeout=15)
    out={k:v for k,v in headers.items() if k.lower() in PASS_HEADERS}
    out['Host']=f'{target[0]}:{target[1]}'
    conn.request(method,path,body=body,headers=out)
    r=conn.getresponse()
    data=r.read(MAX_BODY+1)
    if len(data)>MAX_BODY: raise RuntimeError('upstream response too large')
    rh={k:v for k,v in r.getheaders()}
    status=r.status
    conn.close()
    return status,rh,data

def parse_json(data:bytes)->dict[str,Any]:
    value=json.loads(data.decode('utf-8'))
    if not isinstance(value,dict): raise ValueError('JSON-RPC payload must be object')
    return value

def json_response(request_id:Any,result:Any)->bytes:
    return json.dumps({'jsonrpc':'2.0','id':request_id,'result':result},separators=(',',':')).encode()

def json_error(request_id:Any,code:int,message:str)->bytes:
    return json.dumps({'jsonrpc':'2.0','id':request_id,'error':{'code':code,'message':message}},separators=(',',':')).encode()

class Handler(BaseHTTPRequestHandler):
    server_version='Edge1MCPCompat/1'
    def log_message(self,fmt,*args):
        super().log_message(fmt,*args)
    def _send(self,status:int,headers:dict[str,str],data:bytes):
        self.send_response(status)
        for k,v in headers.items():
            if k.lower() in RETURN_HEADERS:
                self.send_header(k,v)
        if not any(k.lower()=='content-type' for k in headers):
            self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        if data: self.wfile.write(data)
    def do_GET(self):
        if self.path=='/healthz':
            body=b'{"status":"ok","service":"edge1-mcp-compat-proxy"}'
            self._send(200,{'Content-Type':'application/json'},body); return
        self.send_error(404)
    def do_POST(self):
        if self.path!=PATH: self.send_error(404); return
        try:
            n=int(self.headers.get('Content-Length','0'))
        except ValueError:
            self.send_error(400); return
        if n<0 or n>MAX_BODY: self.send_error(413); return
        body=self.rfile.read(n)
        headers={k:v for k,v in self.headers.items()}
        try:
            msg=parse_json(body)
        except Exception:
            status,rh,data=upstream(AGENT,'POST',PATH,body,headers)
            self._send(status,rh,data); return
        method=msg.get('method')
        request_id=msg.get('id')
        if method=='tools/list':
            try:
                s1,h1,b1=upstream(AGENT,'POST',PATH,body,headers)
                s2,h2,b2=upstream(OPERATOR,'POST',PATH,body,headers)
                if s1>=400: self._send(s1,h1,b1); return
                if s2>=400: self._send(s2,h2,b2); return
                j1=parse_json(b1); j2=parse_json(b2)
                t1=((j1.get('result') or {}).get('tools') or [])
                t2=((j2.get('result') or {}).get('tools') or [])
                seen=set(); tools=[]
                for item in list(t1)+list(t2):
                    if isinstance(item,dict) and isinstance(item.get('name'),str) and item['name'] not in seen:
                        seen.add(item['name']); tools.append(item)
                result={'tools':tools}
                cursor=(j1.get('result') or {}).get('nextCursor') or (j2.get('result') or {}).get('nextCursor')
                if cursor: result['nextCursor']=cursor
                self._send(200,{'Content-Type':'application/json'},json_response(request_id,result)); return
            except Exception:
                self._send(200,{'Content-Type':'application/json'},json_error(request_id,-32603,'Compatibility proxy upstream error')); return
        if method=='tools/call':
            params=msg.get('params') or {}
            name=params.get('name') if isinstance(params,dict) else None
            if isinstance(name,str) and name.startswith('edge1.'):
                target=OPERATOR
            elif isinstance(name,str) and name.startswith('edge1_agent_'):
                target=AGENT
            else:
                self._send(200,{'Content-Type':'application/json'},json_error(request_id,-32601,'Tool not routed')); return
            status,rh,data=upstream(target,'POST',PATH,body,headers)
            self._send(status,rh,data); return
        status,rh,data=upstream(AGENT,'POST',PATH,body,headers)
        self._send(status,rh,data)

def main()->int:
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'Edge1 MCP compatibility proxy on http://{HOST}:{PORT}{PATH}',flush=True)
    server.serve_forever()
    return 0
if __name__=='__main__': raise SystemExit(main())
