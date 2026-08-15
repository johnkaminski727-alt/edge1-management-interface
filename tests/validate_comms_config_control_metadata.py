#!/usr/bin/env python3
"""Verify candidate apply/rollback preserves running config filesystem metadata."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'server'))

from edge1_comms.config_control import apply_candidate, rollback_last, stage_config


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def metadata(path: Path) -> tuple[int, int, int]:
    value = path.stat()
    return stat.S_IMODE(value.st_mode), value.st_uid, value.st_gid


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='edge1-config-metadata-') as name:
        tmp = Path(name)
        source = json.loads((REPO_ROOT / 'config' / 'comms-relay.example.json').read_text(encoding='utf-8'))
        running = tmp / 'running.json'
        candidate = tmp / 'candidate-input.json'
        state = tmp / 'state'

        old = json.loads(json.dumps(source))
        old['network_name'] = 'WW.CX OLD'
        running.write_text(json.dumps(old), encoding='utf-8')
        os.chmod(running, 0o640)
        before = metadata(running)

        new = json.loads(json.dumps(source))
        new['network_name'] = 'WW.CX NEW'
        candidate.write_text(json.dumps(new), encoding='utf-8')

        stage_config(candidate, state)
        applied = apply_candidate(state, running)
        check(json.loads(running.read_text(encoding='utf-8'))['network_name'] == 'WW.CX NEW', 'candidate not applied')
        check(metadata(running) == before, f'apply changed target metadata: {before!r} -> {metadata(running)!r}')
        check(applied['preserved_mode'] == '0o640', 'apply record missing preserved mode')
        check(applied['preserved_uid'] == before[1] and applied['preserved_gid'] == before[2], 'apply record missing preserved ownership')

        rolled_back = rollback_last(state, running)
        check(json.loads(running.read_text(encoding='utf-8'))['network_name'] == 'WW.CX OLD', 'rollback did not restore prior config')
        check(metadata(running) == before, f'rollback changed target metadata: {before!r} -> {metadata(running)!r}')
        check(rolled_back['preserved_mode'] == '0o640', 'rollback record missing preserved mode')

    print('PASS validate_comms_config_control_metadata')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
