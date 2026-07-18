#!/usr/bin/env python3
"""Import the shared collector using syntax supported by Python 3.6."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "tools" / "time_authority" / "ntp_rtt_probe.py"


def main():
    spec = importlib.util.spec_from_file_location("ntp_rtt_probe_compat", str(COLLECTOR_PATH))
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load shared-host collector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    encoded = module.encode_ntp_timestamp(0.0)
    assert len(encoded) == 8
    assert abs(module.decode_ntp_timestamp(encoded)) < 0.001
    print("time authority collector compatibility validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
