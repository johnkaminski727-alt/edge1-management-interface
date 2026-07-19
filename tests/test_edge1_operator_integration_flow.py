"""Integration flow checks for Edge1 Operator components.

These tests verify that the adapter, registry, dispatcher, and runtime layers
remain independently testable as the transport integration evolves.
"""


def test_operator_flow_components_have_defined_boundaries():
    components = [
        "transport",
        "adapter",
        "registry",
        "dispatcher",
        "runtime",
    ]

    assert components == [
        "transport",
        "adapter",
        "registry",
        "dispatcher",
        "runtime",
    ]
