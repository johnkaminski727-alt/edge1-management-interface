#!/usr/bin/env python3

"""Validate the public-authority source manifest and staged source metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "data" / "registry" / "sources" / "public-authorities"
MANIFEST = SOURCE_ROOT / "source-manifest.json"

REQUIRED_SOURCE_FIELDS = {
    "id",
    "authority",
    "dataset",
    "purpose",
    "landing_page",
    "retrieval",
    "status",
    "precedence",
}


def fail(message: str) -> None:
    raise SystemExit(f"public authority source validation failed: {message}")


def valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_artifact_metadata(source_id: str) -> None:
    metadata_path = SOURCE_ROOT / source_id / "artifact-metadata.json"
    if not metadata_path.exists():
        return

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = {"source_id", "retrieved_at", "source_url", "filename", "sha256", "bytes"}
    missing = sorted(required - set(metadata))
    if missing:
        fail(f"{metadata_path}: missing fields {missing}")
    if metadata["source_id"] != source_id:
        fail(f"{metadata_path}: source_id does not match directory")
    if not valid_https_url(metadata["source_url"]):
        fail(f"{metadata_path}: source_url must be HTTPS")

    artifact = metadata_path.parent / metadata["filename"]
    if not artifact.exists():
        fail(f"{metadata_path}: declared artifact does not exist: {artifact.name}")
    data = artifact.read_bytes()
    if len(data) != metadata["bytes"]:
        fail(f"{metadata_path}: byte count mismatch")
    digest = hashlib.sha256(data).hexdigest()
    if digest != metadata["sha256"]:
        fail(f"{metadata_path}: SHA-256 mismatch")


def main() -> None:
    if not MANIFEST.exists():
        fail(f"missing manifest: {MANIFEST}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0":
        fail("unsupported schema_version")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        fail("sources must be a non-empty list")

    seen_ids: set[str] = set()
    seen_precedence: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            fail(f"sources[{index}] must be an object")
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
        if missing:
            fail(f"sources[{index}] missing fields {missing}")

        source_id = source["id"]
        if source_id in seen_ids:
            fail(f"duplicate source id: {source_id}")
        seen_ids.add(source_id)

        if not isinstance(source["purpose"], list) or not source["purpose"]:
            fail(f"{source_id}: purpose must be a non-empty list")
        if not valid_https_url(source["landing_page"]):
            fail(f"{source_id}: landing_page must be HTTPS")
        for optional_url in ("download_url", "updates_page"):
            if optional_url in source and not valid_https_url(source[optional_url]):
                fail(f"{source_id}: {optional_url} must be HTTPS")

        precedence = source["precedence"]
        if precedence in seen_precedence:
            fail(f"duplicate precedence value: {precedence}")
        seen_precedence.add(precedence)
        validate_artifact_metadata(source_id)

    expected = {
        "un-m49",
        "statcan-sccai-2022",
        "statcan-sccai-history",
        "iana-tzdb",
        "iana-root-zone",
        "iana-language-subtags",
        "itu-e164",
        "unicode-cldr",
    }
    missing_expected = sorted(expected - seen_ids)
    if missing_expected:
        fail(f"missing expected sources: {missing_expected}")

    print(f"Validated {len(sources)} public authority source definitions")


if __name__ == "__main__":
    main()
