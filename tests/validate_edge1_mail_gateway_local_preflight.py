#!/usr/bin/env python3
"""Validate the read-only Edge1 Mail Gateway Postfix preflight wrapper."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "messaging" / "prepare-edge1-mail-gateway-local-preflight.sh"


def write_executable(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def fake_postconf(*, collision: bool = False) -> str:
    collision_value = "hash:/etc/postfix/existing" if collision else ""
    return f"""#!/bin/sh
set -eu
if [ "$1" = "-n" ]; then
    cat <<'EOF'
inet_interfaces = loopback-only
myhostname = edge1.ww.cx
EOF
    exit 0
fi
if [ "$1" = "-M" ]; then
    echo 'smtp inet n - y - - smtpd'
    exit 0
fi
if [ "$1" = "-h" ]; then
    case "$2" in
        inet_interfaces) echo 'loopback-only' ;;
        myhostname) echo 'edge1.ww.cx' ;;
        mydestination) echo '$myhostname, localhost' ;;
        relay_domains) echo '' ;;
        virtual_alias_domains) echo '' ;;
        virtual_alias_maps) echo '' ;;
        virtual_mailbox_domains) echo '{collision_value}' ;;
        virtual_mailbox_maps) echo '' ;;
        virtual_transport) echo '' ;;
        smtpd_recipient_restrictions) echo 'permit_mynetworks,reject_unauth_destination' ;;
        *) echo '' ;;
    esac
    exit 0
fi
exit 2
"""


def run_preflight(*, public_port25: bool = False, collision: bool = False) -> tuple[subprocess.CompletedProcess[str], pathlib.Path]:
    temporary = tempfile.TemporaryDirectory()
    root = pathlib.Path(temporary.name)
    # Keep the TemporaryDirectory alive by attaching it to the Path wrapper's module-level
    # lifetime through this list until process completion/inspection.
    _TEMP_DIRS.append(temporary)

    fake_bin = root / "bin"
    fake_bin.mkdir()
    write_executable(fake_bin / "postconf", fake_postconf(collision=collision))
    ss_line = (
        "LISTEN 0 100 0.0.0.0:25 0.0.0.0:* users:((postfix,pid=1,fd=1))"
        if public_port25
        else "LISTEN 0 100 127.0.0.1:25 0.0.0.0:* users:((postfix,pid=1,fd=1))"
    )
    write_executable(fake_bin / "ss", f"#!/bin/sh\necho '{ss_line}'\n")

    postfix_etc = root / "postfix"
    postfix_etc.mkdir()
    (postfix_etc / "main.cf").write_text("inet_interfaces = loopback-only\n", encoding="utf-8")
    (postfix_etc / "master.cf").write_text("smtp inet n - y - - smtpd\n", encoding="utf-8")

    output_root = root / "evidence"
    output_root.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "REPO_ROOT": str(ROOT),
            "OUTPUT_ROOT": str(output_root),
            "POSTFIX_ETC": str(postfix_etc),
        }
    )
    result = subprocess.run(
        ["sh", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result, output_root


_TEMP_DIRS: list[tempfile.TemporaryDirectory[str]] = []


def main() -> int:
    syntax = subprocess.run(["sh", "-n", str(SCRIPT)], check=False)
    assert syntax.returncode == 0

    success, output_root = run_preflight()
    assert success.returncode == 0, success.stderr
    evidence_path = pathlib.Path(success.stdout.strip())
    assert evidence_path.parent == output_root
    assert (evidence_path / "README.txt").is_file()
    assert (evidence_path / "current" / "postconf-n.txt").is_file()
    assert (evidence_path / "current" / "postconf-M.txt").is_file()
    assert (evidence_path / "current" / "port25-listeners.txt").read_text().strip().endswith("127.0.0.1:25 0.0.0.0:* users:((postfix,pid=1,fd=1))")
    assert (evidence_path / "current" / "collisions.txt").read_text() == ""
    rendered = evidence_path / "rendered"
    assert "inet_interfaces = loopback-only" in (rendered / "main.cf.fragment").read_text()
    assert "ww.cx OK" not in (rendered / "wwcx-edge1-managed-domains").read_text()
    readme = (evidence_path / "README.txt").read_text()
    assert "No Postfix configuration was edited" in readme
    assert "no DNS/MX state was changed" in readme

    collision, _ = run_preflight(collision=True)
    assert collision.returncode == 0, collision.stderr
    collision_path = pathlib.Path(collision.stdout.strip()) / "current" / "collisions.txt"
    assert "virtual_mailbox_domains=hash:/etc/postfix/existing" in collision_path.read_text()

    public, _ = run_preflight(public_port25=True)
    assert public.returncode != 0
    assert "non-loopback listener" in public.stderr

    content = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "postconf -e",
        "postmap ",
        "systemctl restart",
        "systemctl reload",
        "service postfix",
        "cp $out/rendered",
        "mv $out/rendered",
    ]
    for token in forbidden:
        assert token not in content, token

    print("Edge1 Mail Gateway local preflight validation passed")
    print("Loopback-only state produces evidence without Postfix mutation")
    print("Existing virtual-domain settings are surfaced as collisions")
    print("Non-loopback TCP/25 fails closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
