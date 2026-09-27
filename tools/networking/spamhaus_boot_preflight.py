#!/usr/bin/env python3
"""Read-only boot restoration preflight for a pinned Spamhaus JSON candidate.

This tool never invokes nftables or modifies systemd. A separate approved
deployment may consume the validated candidate; this is not a restoration job.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path

REQUIRED = (
    "drop_v4.json", "drop_v6.json", "spamhaus-candidate.nft",
    "spamhaus_scoped_recovery.py", "source-commit.txt",
    "previous-checkpoint-path.txt",
)


def verify_hashes(stage: Path) -> None:
    manifest = stage / "SHA256SUMS"
    entries = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Malformed checksum manifest")
        if name in entries or "/" in name or name.startswith("."):
            raise ValueError("Unsafe or duplicate manifest filename")
        entries[name] = digest
    if not set(REQUIRED) <= entries.keys():
        raise ValueError("Required staging files missing from manifest")
    for name, expected in entries.items():
        path = stage / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or symlinked candidate file: " + name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Candidate integrity failure: " + name)


def preflight(stage: Path, parser_path: Path, recovery: Path) -> dict:
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError("Staging directory missing or symlinked")
    if os.geteuid() == 0:
        meta = stage.stat()
        if meta.st_uid != 0 or meta.st_mode & 0o077:
            raise ValueError("Staging directory must be root-owned and private")
    verify_hashes(stage)
    if hashlib.sha256(recovery.read_bytes()).digest() != hashlib.sha256(
        (stage / "spamhaus_scoped_recovery.py").read_bytes()
    ).digest():
        raise ValueError("Installed recovery program does not match staged copy")
    spec = importlib.util.spec_from_file_location("spamhaus_feed_candidate", parser_path)
    if spec is None or spec.loader is None:
        raise ValueError("Missing official JSON parser")
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    v4, v4_count = parser.parse_feed(stage / "drop_v4.json", 4)
    v6, v6_count = parser.parse_feed(stage / "drop_v6.json", 6)
    expected = parser.render_candidate(v4, v6).encode("utf-8")
    if (stage / "spamhaus-candidate.nft").read_bytes() != expected:
        raise ValueError("Candidate does not match current validated feeds")
    return {"ipv4_unique": v4_count, "ipv6_unique": v6_count,
            "ipv4_aggregated": len(v4), "ipv6_aggregated": len(v6)}


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--stage", type=Path, required=True)
    args.add_argument("--parser", type=Path, required=True)
    args.add_argument("--recovery", type=Path, required=True)
    parsed = args.parse_args()
    try:
        summary = preflight(parsed.stage, parsed.parser, parsed.recovery)
    except (ValueError, OSError, OverflowError) as exc:
        args.exit(1, "STOP: " + str(exc) + "\n")
    print("PASS: Boot restore candidate integrity and feed age validated")
    for key, value in summary.items():
        print(f"{key}={value}")
    print("CHECK ONLY: no nftables or systemd changes")


if __name__ == "__main__":
    main()
