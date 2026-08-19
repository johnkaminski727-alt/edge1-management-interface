---
name: business159-operator-router
description: Route ordinary WW.CX Business159 shared-host operational questions to the narrowest live bounded Business159 MCP tool. Use for Business159 identity, health, snapshot, resources, PHP, web/HTTPS, domain/TLS, cron, Git, mail, deployment, Edge1 bridge, logs, storage, or configuration-digest questions, including natural requests such as “Is Business159 healthy?” or “What PHP version are we running?”.
---

# Business159 Operator Router

Use the live `business159-live-shell` MCP dependency for current Business159 state.

## Route to the narrowest tool

- identity/host/account -> `business159.identity`
- health/current status -> `business159.health`
- broad snapshot -> `business159.snapshot`
- inventory -> `business159.inventory`
- storage/quota/resources -> `business159.resources`
- PHP -> `business159.php_status`
- WW.CX HTTP/HTTPS -> `business159.web_status`
- domain/resolution -> `business159.domain_state`
- TLS/certificate -> `business159.tls_status`
- cron/scheduler -> `business159.cron_state`
- Git/repository state -> `business159.git_state`
- mail capability -> `business159.mail_state`
- deployment/current release -> `business159.deployment_status`
- Edge1 snapshot/bridge freshness -> `business159.edge1_bridge_status`
- config hashes -> `business159.config_digest`
- bounded logs -> `business159.logs_summary`

Treat live bounded output as authoritative for current Business159 state. Do not substitute memory, repository docs, or web search when the live tool is available.

Business159 is a cPanel/shared-host account. Never imply root, systemd, firewall, kernel, or unrestricted network administration.

For investigation requiring several related checks, compose the smallest relevant bounded tools or hand off to `business159-shell-operator`; do not jump directly to raw shell.

If the MCP dependency is unavailable, state that live Business159 verification is unavailable in the current session. Never invent a result or ask for passwords/private keys in chat.
