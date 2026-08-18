from pathlib import Path
import subprocess

import pytest

import app.trusted_scanner as trusted_scanner
from app.media_quarantine import ScannerUnavailableError


class Result:
    def __init__(self, returncode: int):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def test_clamav_clean_uses_fixed_command(monkeypatch, tmp_path):
    blob = (tmp_path / "blob.bin").resolve()
    blob.write_bytes(b"clean")
    calls = []

    monkeypatch.setattr(trusted_scanner, "CLAMSCAN_PATH", Path("/usr/bin/clamscan"))
    original_is_file = Path.is_file

    def fake_is_file(path):
        if path == Path("/usr/bin/clamscan"):
            return True
        return original_is_file(path)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result(0)

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    monkeypatch.setattr(subprocess, "run", fake_run)

    verdict = trusted_scanner.ClamAVScanner().scan(
        blob,
        sha256="0" * 64,
        content_type="application/octet-stream",
        timeout_seconds=3.0,
    )
    assert verdict == "clean"
    command, kwargs = calls[0]
    assert command == [
        "/usr/bin/clamscan",
        "--no-summary",
        "--stdout",
        "--infected",
        str(blob),
    ]
    assert kwargs["timeout"] == 3.0
    assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}


def test_clamav_malicious_verdict(monkeypatch, tmp_path):
    blob = (tmp_path / "blob.bin").resolve()
    blob.write_bytes(b"test")
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result(1))
    assert trusted_scanner.ClamAVScanner().scan(
        blob, sha256="0" * 64, content_type=None, timeout_seconds=1.0
    ) == "malicious"


def test_clamav_unavailable_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    with pytest.raises(ScannerUnavailableError):
        trusted_scanner.ClamAVScanner().scan(
            (tmp_path / "missing").resolve(),
            sha256="0" * 64,
            content_type=None,
            timeout_seconds=1.0,
        )


def test_clamav_timeout_fails_closed(monkeypatch, tmp_path):
    blob = (tmp_path / "blob.bin").resolve()
    blob.write_bytes(b"test")
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="clamscan", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(TimeoutError):
        trusted_scanner.ClamAVScanner().scan(
            blob, sha256="0" * 64, content_type=None, timeout_seconds=1.0
        )


def test_clamav_non_verdict_status_fails_closed(monkeypatch, tmp_path):
    blob = (tmp_path / "blob.bin").resolve()
    blob.write_bytes(b"test")
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result(2))
    with pytest.raises(ScannerUnavailableError):
        trusted_scanner.ClamAVScanner().scan(
            blob, sha256="0" * 64, content_type=None, timeout_seconds=1.0
        )


def test_relative_or_symlink_blob_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(trusted_scanner, "CLAMSCAN_PATH", tmp_path / "clamscan")
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    with pytest.raises(RuntimeError):
        trusted_scanner.ClamAVScanner().scan(
            Path("relative.bin"), sha256="0" * 64, content_type=None, timeout_seconds=1.0
        )
