from __future__ import annotations

import subprocess
from pathlib import Path

from .media_quarantine import ScannerUnavailableError, TrustedScanVerdict


CLAMSCAN_PATH = Path("/usr/bin/clamscan")
_FIXED_ARGS = ("--no-summary", "--stdout", "--infected")


class ClamAVScanner:
    """Narrow trusted local scanner adapter for the private MMS quarantine.

    The executable path and command options are fixed in repository code. Callers may
    supply only the already-verified private blob path and the bounded timeout required
    by TrustedMediaScanner; they cannot select an arbitrary executable or options.
    """

    scanner_id = "local:clamav-clamscan"

    def scan(
        self,
        blob_path: Path,
        *,
        sha256: str,
        content_type: str | None,
        timeout_seconds: float,
    ) -> TrustedScanVerdict:
        del sha256, content_type
        if not CLAMSCAN_PATH.is_file():
            raise ScannerUnavailableError("trusted local ClamAV executable is unavailable")
        if not blob_path.is_absolute() or not blob_path.is_file() or blob_path.is_symlink():
            raise RuntimeError("quarantine blob is not a regular absolute file")

        try:
            completed = subprocess.run(
                [str(CLAMSCAN_PATH), *_FIXED_ARGS, str(blob_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=float(timeout_seconds),
                check=False,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("trusted local ClamAV scan timed out") from exc
        except OSError as exc:
            raise ScannerUnavailableError("trusted local ClamAV execution failed") from exc

        if completed.returncode == 0:
            return "clean"
        if completed.returncode == 1:
            return "malicious"
        raise ScannerUnavailableError(
            f"trusted local ClamAV returned non-verdict status {completed.returncode}"
        )
