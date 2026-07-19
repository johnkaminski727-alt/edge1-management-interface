from pathlib import Path

from server.edge1_operator_audit import sanitize, write_event


def test_write_event(tmp_path: Path):
    path = write_event(str(tmp_path), {"event": "test"})
    assert path.exists()
    assert '"event": "test"' in path.read_text()


def test_sanitize_redacts_headers():
    value = sanitize("Authorization: secret")
    assert "[redacted]" in value
