#!/usr/bin/env python3
"""Import shared-host Time Authority tools using syntax supported by Python 3.6."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = [
    ("ntp_rtt_probe_compat", ROOT / "tools" / "time_authority" / "ntp_rtt_probe.py"),
    ("nts_ke_probe_compat", ROOT / "tools" / "time_authority" / "nts_ke_probe.py"),
    ("build_public_time_status_compat", ROOT / "tools" / "time_authority" / "build_public_time_status.py"),
]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    loaded = {name: load(name, path) for name, path in TOOLS}
    collector = loaded["ntp_rtt_probe_compat"]
    encoded = collector.encode_ntp_timestamp(0.0)
    assert len(encoded) == 8
    assert abs(collector.decode_ntp_timestamp(encoded)) < 0.001
    assert loaded["nts_ke_probe_compat"].SCHEMA_VERSION == 1
    assert loaded["build_public_time_status_compat"].SCHEMA_VERSION == 1
    print("time authority shared-host Python 3.6 compatibility validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
