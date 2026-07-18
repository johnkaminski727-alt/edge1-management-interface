#!/usr/bin/env python3
"""Exercise positive and negative records-evidence validation paths."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_records_evidence.py"
EXAMPLE_ROOT = ROOT / "examples" / "records-evidence"


def load_validator():
    spec = importlib.util.spec_from_file_location("records_evidence_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load records evidence validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_validator()


def expect_failure(record: dict, message: str) -> None:
    try:
        validator.validate_record_data(record)
    except validator.EvidenceValidationError:
        return
    raise AssertionError(f"validation unexpectedly accepted: {message}")


def main() -> int:
    record_path = EXAMPLE_ROOT / "example-record.json"
    manifest_path = EXAMPLE_ROOT / "manifest.sha256"
    sample_path = EXAMPLE_ROOT / "sample-object.txt"

    validator.validate_package(record_path, EXAMPLE_ROOT, manifest_path)
    source = json.loads(record_path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / "records-evidence.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert "responsible_role" in properties["authoritative_source"]["required"]
    assert {"trigger", "minimum_years", "legal_hold"}.issubset(properties["retention_rule"]["required"])
    assert properties["retention_rule"]["allOf"]
    assert "agent_role" in properties["events"]["items"]["required"]
    assert properties["objects"]["uniqueItems"] is True
    assert "pattern" in properties["objects"]["items"]["properties"]["path"]

    traversal = copy.deepcopy(source)
    traversal["objects"][0]["path"] = "../private.txt"
    expect_failure(traversal, "parent traversal path")

    absolute = copy.deepcopy(source)
    absolute["objects"][0]["path"] = "/etc/passwd"
    expect_failure(absolute, "absolute path")

    hold_destroy = copy.deepcopy(source)
    hold_destroy["retention_rule"]["legal_hold"] = True
    hold_destroy["retention_rule"]["disposition"] = "destroy"
    expect_failure(hold_destroy, "destroy disposition during legal hold")

    missing_role = copy.deepcopy(source)
    del missing_role["events"][0]["agent_role"]
    expect_failure(missing_role, "event without acting role")

    non_utc = copy.deepcopy(source)
    non_utc["created_utc"] = "2026-07-18T08:00:00-04:00"
    expect_failure(non_utc, "non-UTC timestamp")

    duplicate = copy.deepcopy(source)
    duplicate["objects"].append(copy.deepcopy(duplicate["objects"][0]))
    expect_failure(duplicate, "duplicate object path")

    with tempfile.TemporaryDirectory() as raw_tmp:
        package = Path(raw_tmp)
        (package / "sample-object.txt").write_bytes(sample_path.read_bytes())
        bad_digest = copy.deepcopy(source)
        bad_digest["objects"][0]["sha256"] = "0" * 64
        try:
            validator.validate_record_data(bad_digest, package)
        except validator.EvidenceValidationError:
            pass
        else:
            raise AssertionError("validation accepted a mismatched object digest")

        bad_manifest = package / "manifest.sha256"
        bad_manifest.write_text(("0" * 64) + "  sample-object.txt\n", encoding="utf-8")
        try:
            validator.validate_manifest(
                bad_manifest,
                package,
                {source["objects"][0]["path"]: source["objects"][0]["sha256"]},
            )
        except validator.EvidenceValidationError:
            pass
        else:
            raise AssertionError("validation accepted a mismatched manifest digest")

    assert validator.main([
        str(record_path),
        "--package-root",
        str(EXAMPLE_ROOT),
        "--manifest",
        str(manifest_path),
    ]) == 0

    print("records evidence automation validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
