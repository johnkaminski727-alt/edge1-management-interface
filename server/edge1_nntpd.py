#!/usr/bin/env python3
"""Run the standalone Edge1 NNTP listener (laboratory/development use)."""

from __future__ import annotations

import argparse

from edge1_comms.config import load_config
from edge1_comms.nntp import NntpServer
from edge1_comms.storage import CommsStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    store = CommsStore(cfg.database_path, password_iterations=cfg.security.password_iterations)
    with NntpServer((cfg.nntp.host, cfg.nntp.port), cfg, store) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
