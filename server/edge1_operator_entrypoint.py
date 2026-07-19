"""Edge1 Operator service entrypoint.

Provides a stable application boundary for launching the operator stack.
The transport, adapter, registry, dispatcher, and runtime layers remain
independent so deployment and testing can evolve separately.
"""

from __future__ import annotations

from edge1_operator_transport import OperatorTransport


def build_operator() -> OperatorTransport:
    """Construct the operator service boundary."""
    return OperatorTransport()


def main() -> int:
    """Start the operator process placeholder."""
    operator = build_operator()
    operator.health_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
