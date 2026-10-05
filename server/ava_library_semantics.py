"""Local, source-hash-checked semantic ranking for AVA's approved Library."""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
import math
import sqlite3
import urllib.request
from functools import lru_cache
from pathlib import Path

MODEL = "text-embedding-3-small"
DIMENSIONS = 512
INDEX_MODEL = MODEL + ":" + str(DIMENSIONS)

def fingerprint(title, text):
    return hashlib.sha256((title + "\n" + text).encode()).hexdigest()

def vectors(texts, api_key):
    if not texts or len(texts) > 64 or any(not t or len(t)>12000 for t in texts):
        raise ValueError("embedding input exceeds bounds")
    req=urllib.request.Request("https://api.openai.com/v1/embeddings",
        data=json.dumps({"model":MODEL,"dimensions":DIMENSIONS,"encoding_format":"float","input":texts}).encode(),
        headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=8) as response:
        raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:
        raise ValueError("embedding response exceeds bounds")
    payload=json.loads(raw)
    rows=sorted(payload["data"],key=lambda row:row["index"])
    out=[row["embedding"] for row in rows]
    if len(out)!=len(texts) or any(len(v)!=DIMENSIONS or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) for v in out):
        raise ValueError("invalid embedding dimensions")
    return out

@lru_cache(maxsize=128)
def query_vector(query, api_key):
    return tuple(vectors([query],api_key)[0])

def build_index(db, api_key, engine):
    with closing(sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True)) as c:
        rows=c.execute("SELECT c.id,d.title,c.text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.collection='operations' AND d.source_path!='operations/private-library-runtime-bootstrap.md' ORDER BY c.id LIMIT 65").fetchall()
    if len(rows)>64:
        raise ValueError("explicit bounded batch required for larger libraries")
    safe=[row for row in rows if not engine.contains_secret(row[1]+"\n"+row[2])]
    embeddings=vectors([row[1]+"\n"+row[2] for row in safe],api_key)
    with closing(sqlite3.connect(db)) as c, c:
        c.execute("CREATE TABLE IF NOT EXISTS ava_chunk_embeddings(chunk_id INTEGER PRIMARY KEY,model TEXT NOT NULL,text_sha256 TEXT NOT NULL,vector_json TEXT NOT NULL)")
        c.execute("DELETE FROM ava_chunk_embeddings WHERE chunk_id IN (SELECT c.id FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.source_path=?)", ("operations/private-library-runtime-bootstrap.md",))
        for row,vector in zip(safe,embeddings):
            c.execute("INSERT INTO ava_chunk_embeddings VALUES (?,?,?,?) ON CONFLICT(chunk_id) DO UPDATE SET model=excluded.model,text_sha256=excluded.text_sha256,vector_json=excluded.vector_json",
                      (row[0],INDEX_MODEL,fingerprint(row[1],row[2]),json.dumps(vector)))
    return len(safe)

def rerank(db, query, collections, lexical, *, api_key, engine, limit=5):
    # No new API request when an index or provider key is absent.
    if not api_key or not query.strip() or engine.contains_secret(query) or not collections:
        return lexical[:limit]
    try:
        with closing(sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True,timeout=3)) as c:
            c.row_factory=sqlite3.Row
            marks=",".join("?" for _ in collections)
            rows=c.execute(f"""SELECT c.id,c.text,c.chunk_index,c.locator,d.id AS document_id,
                       d.collection,d.title,d.source_path,d.classification,d.updated_at,e.text_sha256,e.vector_json
                       FROM ava_chunk_embeddings e JOIN chunks c ON c.id=e.chunk_id
                       JOIN documents d ON d.id=c.document_id
                       WHERE e.model=? AND d.collection IN ({marks})
                       ORDER BY d.updated_at DESC,c.id LIMIT 500""",[INDEX_MODEL,*collections]).fetchall()
        rows=[row for row in rows if fingerprint(row["title"],row["text"])==row["text_sha256"]
              and not engine.contains_secret(row["title"]+"\n"+row["text"]+"\n"+row["source_path"])]
        if not rows:
            return lexical[:limit]
        q=query_vector(query[:256],api_key);qn=math.sqrt(sum(x*x for x in q))
        if not qn:
            return lexical[:limit]
        ranked=[]
        for row in rows:
            vector=json.loads(row["vector_json"])
            if len(vector)!=len(q) or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in vector):
                continue
            vn=math.sqrt(sum(x*x for x in vector))
            score=sum(x*y for x,y in zip(q,vector))/(qn*vn) if vn else 0
            if score<0.25:
                continue
            item=engine.SearchResult(document_id=row["document_id"],collection=row["collection"],title=row["title"],source_path=row["source_path"],
                classification=row["classification"],chunk_index=row["chunk_index"],locator=row["locator"],excerpt=engine._excerpt(row["text"],1200,query),score=score,updated_at=row["updated_at"])
            ranked.append((score,item))
        ranked.sort(key=lambda pair:-pair[0])
        items={};scores={}
        for sequence in (lexical,[item for _,item in ranked]):
            for rank,item in enumerate(sequence):
                key=(item.document_id,item.chunk_index);items[key]=item
                scores[key]=scores.get(key,0)+1/(60+rank)
        return [items[key] for key in sorted(scores,key=lambda k:-scores[k])[:limit]]
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):
        return lexical[:limit]
