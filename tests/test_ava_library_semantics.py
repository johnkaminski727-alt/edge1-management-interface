from contextlib import closing
import hashlib
import json
import sqlite3
import unittest
from unittest import mock
import test_ava_library_retrieval as fixtures
from server import ava_library_semantics as semantic

class AvaSemanticLibraryTests(unittest.TestCase):
    search = fixtures.AvaLibraryRetrievalTests.search
    def setUp(self):
        fixtures.AvaLibraryRetrievalTests.setUp(self)
        semantic.query_vector.cache_clear()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("CREATE TABLE ava_chunk_embeddings(chunk_id INTEGER PRIMARY KEY,model TEXT,text_sha256 TEXT,vector_json TEXT)")
            for row in c.execute("SELECT c.id,d.title,c.text FROM chunks c JOIN documents d ON d.id=c.document_id").fetchall():
                vector=[1.0]+[0.0]*511
                c.execute("INSERT INTO ava_chunk_embeddings VALUES (?,?,?,?)",(row[0],semantic.INDEX_MODEL,semantic.fingerprint(row[1],row[2]),json.dumps(vector)))

    def rank(self,query="restore connection",collections=("operations",),lexical=()):
        return semantic.rerank(self.db,query,collections,list(lexical),api_key="test",engine=self.engine)

    def test_semantic_candidates_cannot_cross_collections_or_expose_secrets(self):
        with mock.patch.object(semantic,"query_vector",return_value=(1.0,)+ (0.0,)*511):
            rows=self.rank()
        self.assertTrue(rows)
        self.assertNotIn("private",[r.document_id for r in rows])
        self.assertNotIn("unsafe",[r.document_id for r in rows])

    def test_stale_vectors_are_excluded(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("UPDATE chunks SET text='Changed content'")
        with mock.patch.object(semantic,"query_vector") as vector:
            self.assertEqual(self.rank(),[])
            vector.assert_not_called()

    def test_embedding_provider_failure_preserves_lexical_evidence(self):
        lexical=self.search("VPN")
        with mock.patch.object(semantic,"query_vector",side_effect=OSError("offline")):
            self.assertEqual(self.rank(lexical=lexical),lexical)

    def test_secret_query_never_calls_embedding_provider(self):
        with mock.patch.object(semantic,"query_vector") as vector:
            self.assertEqual(self.rank("password="+"fake"),[])
            vector.assert_not_called()

    def test_semantic_reads_do_not_mutate_library(self):
        before=self.db.read_bytes()
        with mock.patch.object(semantic,"query_vector",return_value=(1.0,)+ (0.0,)*511):
            self.rank()
        self.assertEqual(self.db.read_bytes(),before)

    def test_query_embeddings_are_cached(self):
        with mock.patch.object(semantic,"vectors",return_value=[[1.0]+[0.0]*511]) as embed:
            semantic.query_vector("same query","test")
            semantic.query_vector("same query","test")
            self.assertEqual(embed.call_count,1)
