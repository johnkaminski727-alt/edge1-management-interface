import tempfile
import unittest
from pathlib import Path
from server.edge1_doom_cookie import DoomStore,DURATIONS,NAME
class TestDoom(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.clock=[1000000.0]
        self.path=Path(self.temp.name)/"state.sqlite"
        self.store=DoomStore(self.path,b"k"*32,lambda:self.clock[0])
    def tearDown(self): self.temp.cleanup()
    def hit(self,ip="192.0.2.1",raw="",reason="scope_missing"):
        return self.store.denial(ip,raw,"/edge1-ops/private?secret=omit","GET",reason,"test")
    def test_escalation_and_active_block_no_advance(self):
        for duration in DURATIONS:
            for n in range(3):
                self.assertIsNone(self.hit()["cookie"]); self.assertFalse(self.store.blocked("192.0.2.1"))
            result=self.hit()
            self.assertEqual(result["blocked_until"],self.clock[0]+duration)
            self.assertIn("HttpOnly",result["cookie"])
            self.assertEqual(self.hit()["blocked_until"],result["blocked_until"])
            self.clock[0]=result["blocked_until"]+1
        self.assertTrue(self.store.verify())
    def test_persistent_ip_and_marker_and_forgery(self):
        for _ in range(4): result=self.hit()
        raw=result["cookie"].split(";")[0]
        reopened=DoomStore(self.path,b"k"*32,lambda:self.clock[0])
        self.assertTrue(reopened.blocked("192.0.2.1"))
        self.assertTrue(reopened.blocked("192.0.2.2",raw))
        self.assertFalse(reopened.blocked("192.0.2.2",raw+"x"))
    def test_window_and_excluded_reasons(self):
        for reason in ["session_missing","session_expired","mutation_scope_locked","not_found"]:
            self.assertIsNone(self.hit(reason=reason))
        for _ in range(3): self.hit()
        self.clock[0]+=601
        self.assertIsNone(self.hit()["cookie"])
    def test_tampering_and_release(self):
        for _ in range(4): result=self.hit()
        ident=self.store.marker(result["cookie"].split(";")[0])
        self.store.release(ident,"operator","false positive")
        self.assertFalse(self.store.blocked("192.0.2.1"))
        self.assertTrue(self.store.verify())
        with self.store.connect() as db: db.execute("UPDATE events SET payload='changed' WHERE seq=1")
        self.assertFalse(self.store.verify())
if __name__=="__main__": unittest.main()

class TestGuard(TestDoom):
    def test_guard_threshold_cookie_and_short_circuit(self):
        from types import SimpleNamespace
        from server.edge1_doom_cookie import DoomGuard
        from server.edge1_security_auth_http_types import HttpRequest,HttpResponse
        class Adapter:
            config=SimpleNamespace(allowed_host="edge1.ww.cx",routes={"health":"/healthz","exchange":"/edge1-ops/session/exchange","logout":"/edge1-ops/session/logout"})
            calls=0
            def handle(self,request):
                self.calls+=1
                return HttpResponse(403,(("X-Edge1-Denial-Reason","scope_missing"),),b"denied")
            def _json(self,status,payload): return HttpResponse(status,(),b"forbidden")
        adapter=Adapter(); guard=DoomGuard(self.store)
        req=HttpRequest("GET","/edge1-ops/session",{"X-Edge1-Client-IP":"192.0.2.1","X-Edge1-Original-Path":"/edge1-ops/status/private/"})
        for _ in range(3): self.assertFalse(any(k=="Set-Cookie" for k,v in guard.handle(adapter,req).headers))
        result=guard.handle(adapter,req)
        self.assertTrue(any(k=="Set-Cookie" for k,v in result.headers))
        self.assertFalse(any(k=="X-Edge1-Denial-Reason" for k,v in result.headers))
        self.assertEqual(guard.handle(adapter,req).status,403)
        self.assertEqual(adapter.calls,4)
    def test_untrusted_headers_never_attribute(self):
        from types import SimpleNamespace
        from server.edge1_doom_cookie import DoomGuard
        from server.edge1_security_auth_http_types import HttpRequest,HttpResponse
        adapter=SimpleNamespace(config=SimpleNamespace(allowed_host="edge1.ww.cx",routes={"health":"/healthz","exchange":"/exchange","logout":"/logout"}),
            handle=lambda req:HttpResponse(403,(("X-Edge1-Denial-Reason","scope_missing"),),b""))
        req=HttpRequest("GET","/edge1-ops/private",{"X-Edge1-Client-IP":"192.0.2.1"},remote_addr="192.0.2.2")
        for _ in range(4): DoomGuard(self.store).handle(adapter,req)
        self.assertFalse(self.store.blocked("192.0.2.1"))
