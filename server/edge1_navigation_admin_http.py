"""Loopback-only HTTP adapter for authenticated Navigation Management."""
from __future__ import annotations
import json, os, re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from .edge1_navigation_admin import list_modules, list_audit, update_module

HOST='127.0.0.1'; PORT=int(os.environ.get('EDGE1_NAV_ADMIN_PORT','8796'))
ORIGIN='https://edge1.ww.cx'
MODULE_PATH=re.compile(r'^/api/modules/([a-z0-9][a-z0-9-]{1,63})$')

def send_json(h,status,payload):
    body=json.dumps(payload,separators=(',',':')).encode()
    h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8')
    h.send_header('Cache-Control','no-store'); h.send_header('X-Content-Type-Options','nosniff')
    h.send_header('Content-Length',str(len(body))); h.end_headers(); h.wfile.write(body)

class Handler(BaseHTTPRequestHandler):
    server_version='Edge1NavigationAdmin/1'
    def log_message(self,fmt,*args): return
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=='/healthz': return send_json(self,200,{'ok':True})
        if parsed.path=='/api/modules': return send_json(self,200,{'modules':list_modules()})
        if parsed.path=='/api/audit':
            q=parse_qs(parsed.query); limit=int((q.get('limit') or ['50'])[0])
            return send_json(self,200,{'audit':list_audit(limit=limit)})
        return send_json(self,404,{'error':'not_found'})
    def do_POST(self):
        m=MODULE_PATH.fullmatch(urlparse(self.path).path)
        if not m: return send_json(self,404,{'error':'not_found'})
        if self.headers.get('Origin') != ORIGIN:
            return send_json(self,403,{'error':'origin_denied'})
        if not self.headers.get('Content-Type','').lower().startswith('application/json'):
            return send_json(self,415,{'error':'content_type_required'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<2 or length>16384: raise ValueError('invalid body length')
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError('body must be an object')
            rid=self.headers.get('X-Edge1-Request-ID') or 'browser-request'
            result=update_module(m.group(1),body,actor='authenticated_admin',request_id=rid,output=None)
            Path('/var/lib/edge1-navigation/refresh.trigger').touch()
            return send_json(self,200,{'ok':True,**result})
        except KeyError: return send_json(self,404,{'error':'module_not_found'})
        except (ValueError,json.JSONDecodeError) as exc: return send_json(self,400,{'error':'validation_failed','detail':str(exc)})
        except Exception: return send_json(self,500,{'error':'update_failed'})

def main():
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    server.serve_forever()
if __name__=='__main__': main()
