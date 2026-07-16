#!/usr/bin/env python3
"""Validate the Edge1 private library search server behavior."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class MockBackendHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "results": [
                        {
                            "document_id": "live-get",
                            "title": "Live GET result",
                            "collection": "operations",
                            "snippet": "GET backend works",
                        }
                    ]
                }
            ).encode("utf-8")
        )

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "documents": [
                        {
                            "document_id": "live-post",
                            "title": "Live POST result",
                            "collection": "operations",
                            "snippet": "POST backend works",
                        }
                    ]
                }
            ).encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def run_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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

    status, payload = module.search_payload("VPN", "public", 5)
    assert status == 400
    assert payload["error"] == "unsupported_collection"

    server, thread = run_server(module.PrivateLibrarySearchHandler)
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

    backend, backend_thread = run_server(MockBackendHandler)
    old_url = module.os.environ.get("EDGE1_LIBRARY_SEARCH_URL")
    old_method = module.os.environ.get("EDGE1_LIBRARY_SEARCH_METHOD")
    try:
        host, port = backend.server_address
        module.os.environ["EDGE1_LIBRARY_SEARCH_URL"] = f"http://{host}:{port}/search"
        module.os.environ["EDGE1_LIBRARY_SEARCH_METHOD"] = "GET"
        status, payload = module.search_payload("VPN", "operations", 5)
        assert status == 200
        assert payload["mode"] == "live"
        assert payload["results"][0]["id"] == "live-get"

        module.os.environ["EDGE1_LIBRARY_SEARCH_METHOD"] = "POST"
        status, payload = module.search_payload("VPN", "operations", 5)
        assert status == 200
        assert payload["mode"] == "live"
        assert payload["results"][0]["id"] == "live-post"
    finally:
        if old_url is None:
            module.os.environ.pop("EDGE1_LIBRARY_SEARCH_URL", None)
        else:
            module.os.environ["EDGE1_LIBRARY_SEARCH_URL"] = old_url
        if old_method is None:
            module.os.environ.pop("EDGE1_LIBRARY_SEARCH_METHOD", None)
        else:
            module.os.environ["EDGE1_LIBRARY_SEARCH_METHOD"] = old_method
        backend.shutdown()
        backend.server_close()
        backend_thread.join(timeout=5)

    print("private library search server validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

