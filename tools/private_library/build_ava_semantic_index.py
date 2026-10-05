#!/usr/bin/env python3
"""Rebuild the bounded semantic index for the approved operations collection."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"services/bigbird-ai-gateway"))
sys.path.insert(0,str(ROOT/"tools"))
from app import library_engine
from server.ava_library_semantics import build_index
from ava_gateway_signed_acceptance import load_env
if __name__=="__main__":
    env=load_env()
    key=env.get("OPENAI_API_KEY","").strip().strip(chr(34)).strip(chr(39))
    if not key:
        raise SystemExit("Gateway provider credential is not configured.")
    count=build_index(Path("/var/lib/bigbird-ai-library/library.sqlite3"),key,library_engine)
    print("Source-checked semantic Library chunks indexed:",count)
