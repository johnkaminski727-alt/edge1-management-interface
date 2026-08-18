import json

from tools.library_reconciliation_index import load_mapping, scan, write_outputs


def test_unknown_items_default_to_retain_review(tmp_path):
    (tmp_path / "Pasted text.md").write_text("unique fact\n", encoding="utf-8")
    rows = scan(tmp_path, {})
    assert len(rows) == 1
    assert rows[0]["deletion_eligibility"] == "review-required"
    assert rows[0]["unresolved_status"] == "unresolved"


def test_deletion_eligibility_requires_duplicate_canonical_and_reconciliation(tmp_path):
    item = tmp_path / "edge1-old-handoff.md"
    item.write_text("same\n", encoding="utf-8")
    initial = scan(tmp_path, {})[0]
    mapping = {initial["sha256"]: {"duplicate_of": "sha256:authoritative", "canonical_retained_record": "/07 - Project Big Bird Continuation Handoff.md", "repository_representation": "docs/edge1-operator/13-completion-status.md", "unique_value_reconciled": True}}
    row = scan(tmp_path, mapping)[0]
    assert row["project"] == "Edge1"
    assert row["deletion_eligibility"] == "eligible-after-independent-verification"
    assert row["unresolved_status"] == "resolved-pending-disposition"


def test_outputs_never_claim_destructive_action(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "bigbird-evidence.txt").write_text("evidence", encoding="utf-8")
    rows = scan(root, {})
    out = tmp_path / "index.json"
    csv_out = tmp_path / "index.csv"
    write_outputs(rows, out, csv_out)
    payload = json.loads(out.read_text())
    assert payload["destructive_actions_performed"] is False
    assert csv_out.exists()
    assert (root / "bigbird-evidence.txt").exists()


def test_mapping_must_be_object(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text("[]", encoding="utf-8")
    try:
        load_mapping(path)
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("non-object mapping must fail")
