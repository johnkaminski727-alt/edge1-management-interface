"""Edge1 Operator service entrypoint.

Provides the stable application boundary for launching the operator stack.
The transport, adapter, registry, dispatcher, and runtime layers remain
independent so deployment and testing can evolve separately.
"""

from __future__ import annotations

import time

from edge1_operator_transport import Edge1OperatorTransport


class ServiceOperator:
    """Minimal long-running operator service boundary."""

    def __init__(self) -> None:
        self.transport = Edge1OperatorTransport(dispatcher=None)

    def health_check(self) -> dict[str, str]:
        return {"status": "ready"