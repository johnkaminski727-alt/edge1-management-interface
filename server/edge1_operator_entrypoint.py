"""Edge1 Operator service entrypoint.

Provides the stable application boundary for launching the operator stack.
The transport, adapter, dispatcher, and runtime layers remain separated
so deployment and testing can evolve independently.
"""

from __future__ import annotations

import json
import time

from edge1_operator_transport import Edge1OperatorTransport


class ServiceOperator:
    """Minimal