from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / "deploy/edge1-operator/edge1-operator-mcp.service").read_text(encoding="utf-8")
SOURCE = (ROOT / "server/edge1_operator_http.py").read_text(encoding="utf-8")


def test_service_starts_loopback_http_transport_only():
    assert "server.edge1_operator_http --host 127.0.0.1 --port 8098" in SERVICE
    assert "--host 0.0.0.0" not in SERVICE
    assert "NoNewPrivileges=true" in SERVICE
    assert "ProtectSystem=strict" in SERVICE
    assert "ProtectHome=true" in SERVICE


def test_transport_requires_external_secret_file_and_no_embedded_secret():
    assert "/etc/edge1-operator/mcp-token" in SOURCE
    assert "EDGE1_OPERATOR_MCP_TOKEN_FILE" in SOURCE
    assert "Bearer {token}" in SOURCE
    assert "token = \"" not in SOURCE


def test_no_generic_execution_surface_in_transport_or_service():
    combined = SOURCE + SERVICE
    for token in ("edge1.exec", "shell=True", "os.system", "subprocess", "bash -c", "sh -c"):
        assert token not in combined
