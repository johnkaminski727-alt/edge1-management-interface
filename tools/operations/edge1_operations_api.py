#!/usr/bin/env python3
"""G3 private read-only operations endpoint layered on existing G2 candidate API.

Manual, loopback-only SSH-tunnel session; no new privileged background service.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from edge1_candidate_api import CandidateHandler, LocalHTTPServer
from edge1_candidate_store import CandidateStore
from edge1_operations_view import summarize
from edge1_host_metrics import read_metrics


class G3Handler(CandidateHandler):
    def do_GET(self):
        if self._route() != "/api/operations":
            return super().do_GET()
        if not self._authorized():
            return
        result = summarize(self.server.core_path, self.server.security_path)
        result["host"] = read_metrics()
        self.reply(200, result)


class G3Server(LocalHTTPServer):
    def __init__(self, address, ui, store, token, core_path, security_path):
        super().__init__(address, ui, store, token, core_path)
        self.core_path = core_path
        self.security_path = security_path
        self.RequestHandlerClass = G3Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--core", type=Path, default=Path("/var/www/edge1-status/core-status.json"))
    parser.add_argument("--security", type=Path, default=Path("/var/www/edge1-status/network-defense/data/network-defense.json"))
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    os.umask(0o077)
    if not 1024 <= args.port <= 65535:
        parser.error("port out of range")
    if args.token_file.is_symlink() or not args.token_file.is_file() or args.token_file.stat().st_mode & 0o077:
        parser.error("token must be private and not a symlink")
    token = args.token_file.read_text(encoding="ascii").strip()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        parser.error("token format invalid")
    if args.ui.is_symlink() or not args.ui.is_file():
        parser.error("local UI invalid")
    server = G3Server(("127.0.0.1", args.port), args.ui, CandidateStore(args.database),
                      token, args.core, args.security)
    print(f"G3 local-only UI at 127.0.0.1:{args.port}; SSH tunnel required", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
