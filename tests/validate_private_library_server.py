#!/usr/bin/env python3
"""Validate the Edge1 private library search server behavior."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "server" / "private_library_search_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("private_library_search_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load private_library_search_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    module = load_server_module()

    assert module.clamp_limit(None) == 10
    assert module.clamp_limit("0") == 1
    assert module.clamp_limit("1000") == 25
    assert module.clamp_limit("bad") == 10

    status, payload = module.search_payload("VPN", "operations", 5)
    assert status == 200
    assert payload["collection"] == "operations"
    assert payload["results"], "fixture search should return results"
    assert all(result["collection"] == "operations" for result in payload["results"])

    status, payload = module.search_payload("VPN", "public", 5)
    assert status == 400
    assert payload["error"] == "unsupported_collection"

    server = ThreadingHTTPServer(("127.0.0.1", 0), module.PrivateLibrarySearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        status, payload = fetch_json(
            f"http://{host}:{port}/api/private-library/search?q=rollback&collection=operations&limit=2"
        )
        assert status == 200
        assert payload["query"] == "rollback"
        assert len(payload["results"]) <= 2

        status, payload = fetch_json(
            f"http://{host}:{port}/api/private-library/search?q=rollback&collection=public"
        )
        assert status == 400
        assert payload["error"] == "unsupported_collection"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    print("private library search server validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

