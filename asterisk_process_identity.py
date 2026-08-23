"""Compatibility import for the standalone immutable privileged-broker runtime.

Repository code should normally import ``server.asterisk_process_identity``. The
privileged broker is also executed as a standalone script from a root-owned release
that places the same helper beside it, so its top-level import name is intentional.
"""
from server.asterisk_process_identity import *  # noqa: F401,F403
