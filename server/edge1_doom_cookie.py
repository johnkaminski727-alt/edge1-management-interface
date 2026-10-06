"""Fuck You Cookie (TM): defensive denial evidence; never grants access."""
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from pathlib import Path

NAME = "__Host-wwcx_doom"
DURATIONS = (172800, 604800, 2592000, 63115200)
QUALIFY = {"console_scope_required", "scope_missing", "scope is not authorized", "csrf_invalid"}
class DoomStore:
    def __init__(self, path, key, now=time.time):
        if len(key) < 32: raise ValueError("signing key too short")
        self.path, self.key, self.now = str(path), key, now
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS subjects(id TEXT PRIMARY KEY, tier INTEGER NOT NULL DEFAULT 0,
                strikes INTEGER NOT NULL DEFAULT 0, window_start REAL NOT NULL DEFAULT 0,
                blocked_until REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS addresses(ip TEXT PRIMARY KEY, subject TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL,
                previous TEXT NOT NULL, digest TEXT NOT NULL);
            """)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db: yield db
        finally: db.close()
    def sign(self, ident):
        return ident+"."+hmac.new(self.key, ident.encode(), hashlib.sha256).hexdigest()
    def marker(self, raw):
        if len(raw)>8192: return None
        try:
            jar=SimpleCookie(); jar.load(raw)
            value=jar[NAME].value if NAME in jar else ""
            ident, signature=value.split(".")
            if not re.fullmatch("[a-f0-9]{48}",ident): return None
            if hmac.compare_digest(self.sign(ident),value): return ident
        except (ValueError, KeyError): pass
        return None
    def _subject(self, db, ip, raw, create):
        address=str(ipaddress.ip_address(ip))
        saved=db.execute("SELECT subject FROM addresses WHERE ip=?",(address,)).fetchone()
        marked=self.marker(raw)
        known=db.execute("SELECT id FROM subjects WHERE id=?",(marked,)).fetchone() if marked else None
        # Preserve an existing address's history: a fresh cookie cannot reset it.
        ident=saved[0] if saved else known[0] if known else None
        if ident is None and create:
            ident=secrets.token_hex(24)
            db.execute("INSERT INTO subjects(id) VALUES(?)",(ident,))
        if ident and create and not saved:
            db.execute("INSERT INTO addresses VALUES(?,?)",(address,ident))
        return ident
    def _audit(self, db, event):
        payload=json.dumps(event,sort_keys=True,separators=(",",":"))
        row=db.execute("SELECT digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous=row[0] if row else "0"*64
        digest=hmac.new(self.key,(previous+payload).encode(),hashlib.sha256).hexdigest()
        db.execute("INSERT INTO events(payload,previous,digest) VALUES(?,?,?)",(payload,previous,digest))
    def blocked(self, ip, raw=""):
        with self.connect() as db:
            # Check BOTH marker and address, so an already known IP cannot conceal a banned marker.
            ids=[]
            saved=db.execute("SELECT subject FROM addresses WHERE ip=?",(str(ipaddress.ip_address(ip)),)).fetchone()
            if saved: ids.append(saved[0])
            marked=self.marker(raw)
            if marked: ids.append(marked)
            until=max([db.execute("SELECT blocked_until FROM subjects WHERE id=?",(i,)).fetchone()[0]
                       for i in set(ids) if db.execute("SELECT id FROM subjects WHERE id=?",(i,)).fetchone()] or [0])
            return until if until>self.now() else 0
    def denial(self, ip, raw, path, method, reason, agent="", request_id=""):
        if reason not in QUALIFY: return None
        now=self.now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ident=self._subject(db,ip,raw,True)
            tier,strikes,start,until=db.execute(
                "SELECT tier,strikes,window_start,blocked_until FROM subjects WHERE id=?",(ident,)).fetchone()
            if until>now: return {"blocked_until":until,"cookie":None}
            if now-start>=600: strikes,start=0,now
            strikes+=1
            blocked=False
            if strikes>=4:
                until=now+DURATIONS[min(tier,len(DURATIONS)-1)]
                tier=min(tier+1,len(DURATIONS)); strikes=0; start=now; blocked=True
            db.execute("UPDATE subjects SET tier=?,strikes=?,window_start=?,blocked_until=? WHERE id=?",
                       (tier,strikes,start,until,ident))
            self._audit(db,{"timestamp":now,"event":"block" if blocked else "denial","subject":ident,
                "source_ip":str(ipaddress.ip_address(ip)),"path":path.split("?")[0][:512],
                "method":method[:16],"reason":reason,"user_agent":agent[:512],
                "request_id":request_id[:128],"tier":tier,"strikes":strikes,"blocked_until":until})
            cookie=(NAME+"="+self.sign(ident)+"; Path=/; Max-Age=63115200; Secure; HttpOnly; SameSite=Strict") if blocked else None
            return {"blocked_until":until,"cookie":cookie}
    def release(self, ident, actor, reason):
        if not actor or not reason: raise ValueError("actor and reason required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT id FROM subjects WHERE id=?",(ident,)).fetchone(): raise ValueError("unknown subject")
            db.execute("UPDATE subjects SET blocked_until=0,strikes=0,window_start=0 WHERE id=?",(ident,))
            self._audit(db,{"timestamp":self.now(),"event":"operator_release","subject":ident,
                "actor":actor[:128],"reason":reason[:512],"escalation_history_preserved":True})
    def verify(self):
        previous="0"*64
        with self.connect() as db:
            for payload,prev,digest in db.execute("SELECT payload,previous,digest FROM events ORDER BY seq"):
                expected=hmac.new(self.key,(previous+payload).encode(),hashlib.sha256).hexdigest()
                if prev!=previous or not hmac.compare_digest(expected,digest): return False
                previous=digest
        return True

class DoomGuard:
    def __init__(self, store): self.store=store
    def handle(self, adapter, request):
        from .edge1_security_auth_http_types import HttpResponse
        headers={k.lower():v for k,v in request.headers.items()}
        ip=headers.get("x-edge1-client-ip","")
        trusted=(request.remote_addr in {"127.0.0.1","::1"} and request.scheme=="https"
                 and request.host==adapter.config.allowed_host)
        try: ip=str(ipaddress.ip_address(ip))
        except ValueError: trusted=False
        original=headers.get("x-edge1-original-path",request.path).split("?")[0]
        protected=(original.startswith("/edge1-ops/") or original.startswith("/api/contacts/") or original=="/")
        exempt=original in {adapter.config.routes["health"],adapter.config.routes["exchange"],
            adapter.config.routes["logout"],"/edge1-ops/account/api"}
        applicable=trusted and protected and not exempt
        if applicable and self.store.blocked(ip,headers.get("cookie","")):
            return adapter._json(403,{"error":"forbidden"})
        response=adapter.handle(request)
        reason=next((v for k,v in response.headers if k=="X-Edge1-Denial-Reason"),"")
        clean=tuple((k,v) for k,v in response.headers if k!="X-Edge1-Denial-Reason")
        if applicable and response.status==403 and reason in QUALIFY:
            result=self.store.denial(ip,headers.get("cookie",""),original,request.method,reason,
                    headers.get("user-agent",""),headers.get("x-edge1-request-id",""))
            if result and result["cookie"]: clean+= (("Set-Cookie",result["cookie"]),)
        return HttpResponse(response.status,clean,response.body)
