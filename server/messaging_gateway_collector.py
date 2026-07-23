#!/usr/bin/env python3
"""
WW.CX Messaging gateway telemetry collector.

This module intentionally performs observation only.
"""

from messaging_health_models import MessagingHealthSnapshot, degraded_snapshot


def collect_gateway_health() -> MessagingHealthSnapshot:
    """
    Return current observed messaging gateway state.

    Initial implementation records the known degraded condition.
    No restart, repair, or messaging operations are performed.
    """
    return degraded_snapshot()


if __name__ == "__main__":
    print(collect_gateway_health().to_dict())
