"""Basic contract checks for Edge1 Operator assets."""

from pathlib import Path


def test_operator_assets_present():
    root = Path(__file__).parents[1]
    assert (root / "server" / "edge1_operator_mcp.py").exists()
    assert (root / "docs" / "edge1-operator" / "03-mcp-tool-contract.md").exists()


def test_operator_policy_files_present():
    root = Path(__file__).parents[1]
    assert (root / "docs" / "edge1-operator" / "05-acceptance-checklist.md").exists()
    assert (root / "docs" / "edge1-operator" / "07-bootstrap-procedure.md").exists()
