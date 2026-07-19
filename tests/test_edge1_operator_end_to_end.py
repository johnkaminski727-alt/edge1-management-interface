"""End-to-end validation checks for the Edge1 Operator request path.

This test verifies that the major service boundaries are importable together.
"""


def test_edge1_operator_components_import():
    from server import edge1_operator_entrypoint
    from server import edge1_operator_mcp_adapter
    from server import edge1_operator_dispatch
    from server import edge1_operator_transport

    assert edge1_operator_entrypoint is not None
    assert edge1_operator_mcp_adapter is not None
    assert edge1_operator_dispatch is not None
    assert edge1_operator_transport is not None
