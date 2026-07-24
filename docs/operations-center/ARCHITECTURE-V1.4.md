# WW.CX Edge1 Operations Center v1.4 Architecture

## Flow

Subsystems

Security
Bitcoin
Mining
Inventory
Network
Messaging
Telephony
Carrier

        |

        v

Exporters

        |

        v

Operations Artifacts

        |

        +----------------+
        |                |
        v                v

Health Model       Timeline

        |

        v

Incident Context

        |

        +--------------+
        |              |
        v              v

Daily Summary     Reports

        |

        v

Operations Center UI

        |

        v

Validation Suite


## Design Principles

- Read-only operational visibility
- Evidence driven
- No hidden mutations
- Separate administration from observation
- Reproducible deployment
