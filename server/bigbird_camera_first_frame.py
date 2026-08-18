#!/usr/bin/env python3
"""Bounded first-frame capture probe for Project Big Bird cameras.

The probe is intentionally one-shot and model-neutral. It reads a protected local
JSON configuration, tries only explicitly configured candidate endpoints in a fixed
transport priority, captures one candidate image payload, verifies that the payload
is image-like, and writes SHA-256 evidence. It does not discover credentials, scan
arbitrary networks, start listeners, persist a daemon, or claim that a captured
payload has been visually verified as coming from the physical camera.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_CONFIG = Path(os.environ.get("BIGBIRD_CAMERA_CONFIG", "/etc/bigbird-camera/cameras.json"))
DEFAULT_EVIDENCE_DIR = Path(os.environ.get("BIGBIRD_CAMERA_EVIDENCE_DIR", "/var/lib/bigbird-camera/evidence"))
MAX_HTTP_BYTES = 12 * 1024 * 1024
TIMEOUT_SECONDS = 12

TRANSPORT_PRIORITY = {
    "onvif_rtsp": 10,
    "rtsp": 20,
    "mjpeg": 30,
    "http_snapshot": 40,
    "hls": 50,
    "webrtc": 60,
    "proprietary_local": 70,
}
SUPPORTED_ONE_SHOT = {"rtsp", "mjpeg", "http_snapshot", "hls"}


class CameraProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    transport: str
    uri: str
    username_file: Path | None = None
    password_file: Path | None = None


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_uri(uri: str) -> str:
    parts = urlsplit(uri)
    if parts.username is None and parts.password is None:
        return uri
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _secret_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).resolve()
    root = Path("/etc/bigbird-camera").resolve()
    if path != root and root not in path.parents:
        raise CameraProbeError("credential file must remain under /etc/bigbird-camera")
    return path


def load_camera(config_path: Path, camera_id: str) -> dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    cameras = payload.get("cameras")
    if not isinstance(cameras, list):
        raise CameraProbeError("config cameras must be a list")
    for camera in cameras:
        if camera.get("id") == camera_id:
            if camera.get("enabled") is not True:
                raise CameraProbeError("camera is not enabled")
            return camera
    raise CameraProbeError(f"camera not found: {camera_id}")


def candidates_for(camera: dict[str, Any]) -> list[Candidate]:
    values = camera.get("candidates", [])
    if not isinstance(values, list):
        raise CameraProbeError("camera candidates must be a list")
    result: list[Candidate] = []
    for item in values:
        transport = str(item.get("transport", "")).strip()
        uri = str(item.get("uri", "")).strip()
        if transport not in TRANSPORT_PRIORITY or not uri:
            continue
        parsed = urlsplit(uri)
        if parsed.username is not None or parsed.password is not None:
            raise CameraProbeError("credentials must not be embedded in camera URIs")
        result.append(Candidate(
            transport=transport,
            uri=uri,
            username_file=_secret_path(item.get("username_file")),
            password_file=_secret_path(item.get("password_file")),
        ))
    return sorted(result, key=lambda item: TRANSPORT_PRIORITY[item.transport])


def _read_optional_secret(path: Path | None) -> str | None:
    if path is None:
        return None
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise CameraProbeError(f"empty credential file: {path}")
    return value


def _looks_like_image(path: Path) -> bool:
    head = path.read_bytes()[:16]
    return (
        head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"GIF87a")
        or head.startswith(b"GIF89a")
        or head.startswith(b"RIFF") and b"WEBP" in head
    )


def _http_capture(candidate: Candidate, output: Path) -> None:
    request = Request(candidate.uri, headers={"Accept": "image/*,*/*;q=0.5", "User-Agent": "BigBird-Camera-Probe/1"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(MAX_HTTP_BYTES + 1)
    if len(data) > MAX_HTTP_BYTES:
        raise CameraProbeError("HTTP payload exceeded first-frame limit")
    output.write_bytes(data)


def _ffmpeg_capture(candidate: Candidate, output: Path) -> None:
    argv = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    username = _read_optional_secret(candidate.username_file)
    password = _read_optional_secret(candidate.password_file)
    uri = candidate.uri
    if username is not None or password is not None:
        parsed = urlsplit(uri)
        if parsed.scheme not in {"rtsp", "http", "https"}:
            raise CameraProbeError("credential injection is unsupported for this transport")
        if username is None or password is None:
            raise CameraProbeError("both username_file and password_file are required")
        from urllib.parse import quote
        netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{parsed.hostname or ''}"
        if parsed.port:
            netloc += f":{parsed.port}"
        uri = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    if candidate.transport == "rtsp":
        argv += ["-rtsp_transport", "tcp"]
    argv += ["-i", uri, "-frames:v", "1", "-f", "image2", str(output)]
    result = subprocess.run(argv, text=True, capture_output=True, timeout=TIMEOUT_SECONDS + 8, check=False)
    if result.returncode != 0:
        message = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s]+", lambda m: redact_uri(m.group(0)), result.stderr[-2000:])
        raise CameraProbeError(f"ffmpeg capture failed: {message.strip()}")


def capture(candidate: Candidate, output: Path) -> None:
    if candidate.transport == "http_snapshot":
        _http_capture(candidate, output)
    elif candidate.transport in {"rtsp", "mjpeg", "hls"}:
        _ffmpeg_capture(candidate, output)
    else:
        raise CameraProbeError(f"transport not supported by one-shot probe: {candidate.transport}")
    if not output.exists() or output.stat().st_size == 0:
        raise CameraProbeError("capture produced no frame")
    if not _looks_like_image(output):
        raise CameraProbeError("capture payload is not a recognized image")


def write_evidence(camera_id: str, candidate: Candidate, frame: Path, evidence_dir: Path) -> Path:
    digest = hashlib.sha256(frame.read_bytes()).hexdigest()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)
    record = {
        "contract": "wwcx.bigbird-camera-first-frame.v2",
        "captured_at": utcnow(),
        "camera_id": camera_id,
        "transport": candidate.transport,
        "source": redact_uri(candidate.uri),
        "frame_path": str(frame),
        "frame_bytes": frame.stat().st_size,
        "sha256": digest,
        "verified_image_payload": True,
        "live_camera_pixels_verified": False,
        "visual_verification_required": True,
        "acceptance_state": "pending_visual_verification",
    }
    evidence = evidence_dir / f"{camera_id}-first-frame.json"
    temp = evidence.with_suffix(".json.tmp")
    temp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(evidence)
    return evidence


def run(config_path: Path, camera_id: str, output_dir: Path, evidence_dir: Path) -> dict[str, Any]:
    camera = load_camera(config_path, camera_id)
    candidates = candidates_for(camera)
    if not candidates:
        raise CameraProbeError("no configured camera candidates")
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for candidate in candidates:
        if candidate.transport not in SUPPORTED_ONE_SHOT:
            failures.append({"transport": candidate.transport, "source": redact_uri(candidate.uri), "error": "unsupported_by_probe"})
            continue
        frame = output_dir / f"{camera_id}-first-frame.jpg"
        try:
            capture(candidate, frame)
            evidence = write_evidence(camera_id, candidate, frame, evidence_dir)
            return {
                "status": "frame_captured_pending_visual_verification",
                "camera_id": camera_id,
                "transport": candidate.transport,
                "source": redact_uri(candidate.uri),
                "frame": str(frame),
                "evidence": str(evidence),
                "acceptance_state": "pending_visual_verification",
            }
        except Exception as exc:
            if frame.exists():
                frame.unlink()
            failures.append({"transport": candidate.transport, "source": redact_uri(candidate.uri), "error": str(exc)})
    raise CameraProbeError("all configured first-frame candidates failed: " + json.dumps(failures, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--camera", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/var/lib/bigbird-camera/frames"))
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    try:
        result = run(args.config, args.camera, args.output_dir, args.evidence_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError, CameraProbeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
