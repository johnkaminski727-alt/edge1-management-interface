#!/usr/bin/env python3
"""Run the unified WW.CX Edge1 IRC, NNTP and read-only control services."""

from __future__ import annotations

import argparse
import signal
import threading
from pathlib import Path

from edge1_comms.config import load_config
from edge1_comms.control import ControlServer
from edge1_comms.irc import IrcServer
from edge1_comms.nntp import NntpServer
from edge1_comms.storage import CommsStore


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "web" / "comms-relay"


def parser() -> argparse.ArgumentParser:
    item = argparse.ArgumentParser(description=__doc__)
    item.add_argument("--config", help="Path to comms-relay JSON configuration")
    return item


def main() -> int:
    args = parser().parse_args()
    cfg = load_config(args.config)
    store = CommsStore(cfg.database_path, password_iterations=cfg.security.password_iterations)
    servers = []
    if cfg.irc.enabled:
        servers.append(IrcServer((cfg.irc.host, cfg.irc.port), cfg, store))
    if cfg.nntp.enabled:
        servers.append(NntpServer((cfg.nntp.host, cfg.nntp.port), cfg, store))
    if cfg.control.enabled:
        irc = next((server for server in servers if isinstance(server, IrcServer)), None)
        servers.append(
            ControlServer(
                (cfg.control.host, cfg.control.port),
                cfg,
                store,
                web_root=WEB_ROOT,
                irc_summary=irc.hub.summary if irc is not None else None,
            )
        )
    if not servers:
        raise SystemExit("no listeners are enabled")
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    threads = [threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    store.audit(None, "control", "service.start", cfg.server_name, "ok", {"listeners": len(servers)})
    stop.wait()
    for server in servers:
        server.shutdown()
        server.server_close()
    for thread in threads:
        thread.join(timeout=2)
    store.audit(None, "control", "service.stop", cfg.server_name, "ok", {})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
