"""Edge1 Operator tool registry.

Keeps MCP-visible capabilities separate from runtime execution.
"""

TOOLS = {
    "edge1.health": {
        "access": "read",
        "description": "Return operator health and identity information.",
        "handler": "health",
    },
    "edge1.system_status": {
        "access": "read",
        "description": "Return bounded system status information.",
        "handler": "system_status",
    },
    "edge1.exec": {
        "access": "controlled_write",
        "description": "Execute approved bounded operations.",
        "handler": "execute",
    },
}


def list_tools():
    return TOOLS
