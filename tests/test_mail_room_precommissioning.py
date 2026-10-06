import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from server.mail_room_access import admin_session
from tools.messaging.mail_room_readiness import backlog
from tools.messaging.mail_room_recovery_rehearsal import counts,digest
from server.mail_room_http import DraftStore,make_handler
from http.server import ThreadingHTTPServer
import threading
import urllib.request
import urllib.error
import sqlite3


class Context(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class PreparationTests(unittest.TestCase):
    def test_session_requires_verified_admin_not_browser_role(self):
        def fetch(context):return lambda *args,**kwargs:Context(json.dumps(context).encode())
        context={'authenticated':True,'source_role':'admin','scopes':['edge1.security.read']}
        self.assertTrue(admin_session({'Cookie':'fixture'},fetch(context)))
        for change in [{'source_role':'operator'},{'source_role':'viewer'},{'authenticated':False},{'scopes':[]}]:
            self.assertFalse(admin_session({'Cookie':'fixture','X-Mail-Role':'admin'},fetch({**context,**change})))
        self.assertFalse(admin_session({},fetch(context)))
        self.assertFalse(admin_session({'Cookie':'fixture'},lambda *a,**k:(_ for _ in ()).throw(OSError())))
    def test_bridge_denies_all_routes_before_accessing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store=DraftStore(Path(directory)/'drafts.sqlite3')
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(None,store,'k'*48,session_check=lambda _:False))
            thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                for route in ['status','drafts','senders','readiness','filter-settings','message/example']:
                    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/edge1-ops/mail-room/api/'+route,headers={'X-Mail-Room-Proxy-Key':'k'*48,'X-Mail-Role':'admin'})
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                    self.assertEqual(error.exception.code,403)
                self.assertEqual(store.list(),[])
            finally:server.shutdown();server.server_close();thread.join()
    def test_unchecked_and_pending_backlog_includes_oldest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);database=root/'security.sqlite3'
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE decisions(message_hash TEXT,state TEXT)');db.execute("INSERT INTO decisions VALUES('checked','released')")
            for key in ['checked','new','pending']:
                p=root/'archive'/'example.test'/key/'metadata.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'normalization':{'message_id_sha256':key}}))
                import os;os.utime(p,(100,100))
            report=backlog(root/'archive',database,2000)
            self.assertEqual(report['pending_or_unchecked'],2)
            self.assertEqual(report['oldest_pending_age_seconds'],1900)
            self.assertIn('pending_mail_older_than_15_minutes',report['warnings'])
            report=backlog(root/'archive',root/'missing.sqlite3',2000)
            self.assertIsNone(report['classification_counts'])
            self.assertIn('security_store_unavailable',report['warnings'])
    def test_restored_integrity_and_hash_detect_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.sqlite3'
            with sqlite3.connect(path) as db:db.execute('CREATE TABLE drafts(body TEXT)');db.execute("INSERT INTO drafts VALUES('private fixture')")
            self.assertEqual(counts(path),{'drafts':1});before=digest(path)
            path.write_bytes(b'corrupt')
            self.assertNotEqual(digest(path),before)
            with self.assertRaises(sqlite3.DatabaseError):counts(path)

if __name__=='__main__':unittest.main()
