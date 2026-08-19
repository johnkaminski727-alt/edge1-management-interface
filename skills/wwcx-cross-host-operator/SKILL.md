---
name: wwcx-cross-host-operator
description: Diagnose and verify WW.CX workflows that span Edge1 and Business159 as separate privilege domains. Use when Operations Center/Big Bird state is stale or incorrect, when Edge1-to-Business159 publication/bridge freshness is in question, or when a request needs topology, cross-host health, release preflight, or post-release verification across the private control plane and shared-host application plane.
---

# WW.CX Cross-Host Operator

Treat Edge1 and Business159 as one topology with different privilege models.

For cross-host failures, trace the smallest relevant chain:

`Edge1 producer -> sanitized/generated state -> integrity/signing/checksum step -> transfer/publication -> Business159 private storage -> application consumer -> HTTP/UI result`

Use live bounded Edge1 tools for current Edge1 state and live Business159 tools for current Business159 state. Do not infer one host's current state from the other host's documentation.

For Operations Center freshness, compare Edge1 producer evidence with `business159.edge1_bridge_status`; the current Business159 consumer defaults to `/home/wwcxjywl/wwcx-store-private/operations-center/latest.json` and verifies receiver-side checksum or configured HMAC according to the application policy. Never expose signing/verification secret values.

When one side is unavailable, diagnose the reachable side and clearly identify the missing evidence. Do not compensate for a connector outage with unrestricted shell or stale memory.

Keep mutations host-specific: Edge1 changes use the Edge1 authenticated/filesystem workflows; Business159 changes use Business159 deploy/staged-filesystem workflows. DNS, firewall, certificates, authentication, public exposure, and production traffic remain separately gated.
