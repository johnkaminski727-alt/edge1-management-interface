from __future__ import annotations
import json,os,re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .edge1_egress_registry import list_services,list_audit,update_service
HOST='127.0.0.1';PORT=int(os.environ.get('EDGE1_EGRESS_ADMIN_PORT','8797'));ORIGIN='https://edge1.ww.cx'
STATUS=Path('/var/lib/edge1-egress/status.json');RUNTIME=Path('/var/lib/edge1-egress/runtime.json')
SERVICE_RE=re.compile(r'^/api/services/([a-z0-9][a-z0-9-]{1,63})$')
def read_json(p,default):
 try:return json.loads(p.read_text())
 except Exception:return default
def send(h,status,payload):
 b=json.dumps(payload,separators=(',',':')).encode();h.send_response(status);h.send_header('Content-Type','application/json; charset=utf-8');h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Content-Length',str(len(b)));h.end_headers();h.wfile.write(b)
class Handler(BaseHTTPRequestHandler):
 server_version='Edge1EgressAdmin/1'
 def log_message(self,*a):return
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/healthz':return send(self,200,{'ok':True})
  if p.path=='/api/status':return send(self,200,{'gateways':read_json(STATUS,{}),'runtime':read_json(RUNTIME,{}),'services':list_services()})
  if p.path=='/api/services':return send(self,200,{'services':list_services()})
  if p.path=='/api/audit':
   q=parse_qs(p.query);return send(self,200,{'audit':list_audit(limit=int((q.get('limit') or ['40'])[0]))})
  return send(self,404,{'error':'not_found'})
 def do_POST(self):
  m=SERVICE_RE.fullmatch(urlparse(self.path).path)
  if not m:return send(self,404,{'error':'not_found'})
  if self.headers.get('Origin')!=ORIGIN:return send(self,403,{'error':'origin_denied'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<2 or n>8192:raise ValueError('invalid body length')
   body=json.loads(self.rfile.read(n));
   if not isinstance(body,dict):raise ValueError('body must be object')
   if body.get('fail_mode','closed')!='closed':raise ValueError('only fail-closed routing is currently commissioned')
   if 'gateway' in body and body['gateway']!='direct':
    st=read_json(STATUS,{})
    ok=any(g.get('pool')==body['gateway'] and g.get('healthy') for g in st.get('gateways',[]))
    if not ok: raise ValueError('selected gateway is not currently healthy')
   item,changed=update_service(m.group(1),body,request_id=self.headers.get('X-Edge1-Request-ID') or 'browser-request')
   return send(self,200,{'ok':True,'service':item,'changed_fields':changed})
  except KeyError:return send(self,404,{'error':'service_not_found'})
  except (ValueError,json.JSONDecodeError) as e:return send(self,400,{'error':'validation_failed','detail':str(e)})
  except Exception:return send(self,500,{'error':'update_failed'})
def main():ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
if __name__=='__main__':main()
