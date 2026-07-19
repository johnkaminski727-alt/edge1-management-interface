"""Edge1 Operator service entrypoint.

Provides the stable application boundary for launching the operator stack.
The transport, adapter, registry, dispatcher, and runtime layers remain
independent so deployment and testing can evolve separately.
"""

from __future__ import annotations

import time

from edge1_operator_dispatch import OperatorDispatcher
from edge1_operator_m