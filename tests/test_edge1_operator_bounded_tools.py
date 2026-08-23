import json
from pathlib import Path

import pytest

from server.edge1_operator_mcp_adapter import MCPAdapter
from server.edge1_operator_mcp_protocol import TOOLS
from server.edge1_operator_operations_client import Edge1OperationsClient, OperationsClientError
from server.edge1_operator_runtime import Edge1OperatorRuntime, READ_ONLY_ACTIONS
from server.edge1_operator_tool_registry import TOOLS as REGISTRY_TOOLS


class FakeClient:
    def __init__(self):
        self.actions = []

    def health(self):
        return {
            "status": "ok",
            "actions": 20,
            "mutations_enabled": False,
            "mutation_gates": {"telephony_safe_controls": False},
        }

    def run_action(self, action, parameters=None):
        self.actions.append(action)
        return {"action": action, "status": "succeeded", "event_id": "test"}


def test_operations_client_rejects_non_loopback_urls(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"x" * 32)
    with pytest.raises(ValueError, match="loopback"):
        Edge1OperationsClient(base_url="http://edge1.ww.cx:8097", secret_file=secret)


def test_operations_client_rejects_unexposed_action(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"x" * 32)
    client = Edge1OperationsClient(secret_file=secret, allowed_actions={"bigbird.health"})
    with pytest.raises(OperationsClientError, match="not exposed"):
        client.run_action("repository.fetch")


def test_runtime_maps_tools_to_fixed_actions():
    client = FakeClient()
    runtime = Edge1OperatorRuntime(client=client)
    payload = runtime.network_state()
    assert [item["action"] for item in payload["results"]] == list(READ_ONLY_ACTIONS["network_state"])
    assert client.actions == list(READ_ONLY_ACTIONS["network_state"])


def test_adapter_rejects_arbitrary_parameters_on_read_tools():
    adapter = MCPAdapter(Edge1OperatorRuntime(client=FakeClient()))
    names = adapter.list_tools()
    assert "edge1.exec" not in names
    assert "edge1.inventory" in names
    assert "edge1.config_digest" in names
    assert "edge1.telephony_console_reload" in names
    assert adapter.call_tool("edge1.health").status == "ok"
    denied = adapter.call_tool("edge1.network_state", command="ip addr")
    assert denied.status == "error"
    assert denied.payload == {"message": "parameters_not_accepted"}


def test_public_protocol_registry_match_and_internal_tools_stay_adapter_only():
    protocol_names = sorted(item["name"] for item in TOOLS)
    adapter_names = MCPAdapter(Edge1OperatorRuntime(client=FakeClient())).list_tools()
    assert protocol_names == sorted(REGISTRY_TOOLS)
    assert set(protocol_names).issubset(adapter_names)
    assert "agent.turn.status" in adapter_names
    assert "agent.turn.handoff" in adapter_names
    assert "agent.turn.status" not in protocol_names
    assert "agent.turn.handoff" not in protocol_names
    assert all(item["inputSchema"].get("additionalProperties") is False for item in TOOLS)


def test_read_only_tool_actions_are_non_mutating_in_allowlist():
    config = json.loads(Path("config/edge1-operations-allowlist.json").read_text())
    actions = config["actions"]
    for action_group in READ_ONLY_ACTIONS.values():
        for action in action_group:
            assert action in actions
            assert actions[action]["mutating"] is False
    assert actions["repository.fetch"]["mutating"] is True
    assert actions["security.rules.reload"]["mutating"] is True
    assert actions["telephony.console.reload_safe"]["mutating"] is True
    assert actions["telephony.console.reload_safe"]["mutation_gate"] == "telephony_safe_controls"
