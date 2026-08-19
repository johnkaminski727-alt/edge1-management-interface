---
name: wwcx-edge1-live-router
description: Route ordinary WW.CX Edge1 operational questions to the narrowest live bounded Edge1 Operator tool. Use for Edge1 identity, health, snapshot, inventory, services, network, storage, Big Bird, Operations, Apache, Asterisk, telephony, messaging, time authority, Git, or configuration-digest questions, including natural requests such as “What is Edge1's health?”.
---

# WW.CX Edge1 Live Router

Use the live `edge1` app dependency whenever the request asks for current or authoritative Edge1 state.

## Route the request

Map the user's intent to the narrowest bounded tool:

- identity / hostname / operator identity -> `edge1.identity`
- health / ready / healthy / current status -> `edge1.health`
- overall snapshot -> `edge1.snapshot`
- inventory -> `edge1.inventory`
- services -> `edge1.services`
- network -> `edge1.network_state`
- disks / storage -> `edge1.disk_state`
- Big Bird -> `edge1.bigbird_status`
- operations plane -> `edge1.operations_status`
- Apache -> `edge1.apache_status`
- Asterisk -> `edge1.asterisk_status`
- telephony -> `edge1.telephony_status`
- messaging -> `edge1.messaging_status`
- time / clock / time authority -> `edge1.time_authority_status`
- Git / repository state -> `edge1.git_state`
- configuration digest -> `edge1.config_digest`

For a general question such as "What is Edge1's health?", call `edge1.health` directly. Do not require an @mention, app picker, or manual tool-selection instruction from the user.

## Preserve the live-data boundary

- Treat live Edge1 app results as authoritative for current Edge1 state.
- Do not substitute web search, remembered facts, repository documentation, or cached status when a live Edge1 tool is available.
- Do not invent a live result. If the app dependency is unavailable in the current session, say that the live Edge1 tool was not exposed and treat the request as not completed.
- Do not ask the user to paste credentials or run SSH/setup commands merely to answer ordinary status questions.

## Preserve the bounded contract

Only use the 16 named Edge1 Operator tools documented in `references/tool-contract.md`.
Do not request or expose arbitrary shell execution, arbitrary commands, paths, URLs, ports, SQL, AMI, or ARI access.

## Output

Return the live result in concise operational language. Distinguish `healthy`, `degraded`, `unavailable`, and tool/transport failure based on the actual response. Include the source tool name when useful for verification.
