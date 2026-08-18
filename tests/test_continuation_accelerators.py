import json

import pytest

from tools.continuation_drift import classify_scalar, compare
from tools.continuation_manifest import build_snapshot, load_manifest


def manifest_fixture():
    return {
        "schema": "wwcx-edge1-continuation-v1",
        "repository_heads": {"edge1-management-interface": {"repository": "owner/repo", "expected_head": "SELF"}},
        "live_state": {"bigbird_version": None, "operator_service": None, "operations_api_service": None},
    }


def test_snapshot_resolves_self_without_mutating_source():
    source = manifest_fixture()
    head = "a" * 40
    snapshot = build_snapshot(source, head)
    assert source["repository_heads"]["edge1-management-interface"]["expected_head"] == "SELF"
    edge1 = snapshot["repository_heads"]["edge1-management-interface"]
    assert edge1["expected_head"] == head
    assert edge1["resolved_from"] == "SELF"
    assert snapshot["generator"] == "tools/continuation_manifest.py"


def test_manifest_rejects_wrong_schema(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        load_manifest(path)


def test_scalar_classification_is_conservative():
    assert classify_scalar("x", "x") == "MATCH"
    assert classify_scalar("x", "y") == "DRIFT"
    assert classify_scalar("x", None) == "UNKNOWN"
    assert classify_scalar(None, "x") == "UNKNOWN"
    assert classify_scalar("x", {"status": "not-deployed"}) == "NOT DEPLOYED"


def test_compare_reports_unknown_when_live_state_missing():
    expected = build_snapshot(manifest_fixture(), "b" * 40)
    report = compare(expected, {})
    assert report["overall"] == "UNKNOWN"
    assert report["checks"]["edge1_checkout_head"]["classification"] == "UNKNOWN"


def test_compare_reports_drift_without_writing_anything(tmp_path):
    expected = build_snapshot(manifest_fixture(), "b" * 40)
    live = {"edge1_checkout_head": "c" * 40}
    before = list(tmp_path.iterdir())
    report = compare(expected, live)
    after = list(tmp_path.iterdir())
    assert report["overall"] == "DRIFT"
    assert before == after == []
