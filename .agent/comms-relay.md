# Edge1 Communications Relay State

Last implementation validation: 2026-08-15  
Feature branch: `feature/edge1-comms-relay`  
Base: `c9e3a7a734c4cd75a4c2e3d7e6260aa578b1bb36`

## Implemented

- shared SQLite account, authorization, newsgroup, article, IRC-history, and audit store;
- PBKDF2-HMAC-SHA256 credentials with per-account random salts;
- IRC listener with IRCv3 CAP/SASL flow, registration, channels, topics, messages, names, and WHO;
- NNTP reader/poster with authentication, group listing, article retrieval, overview, navigation, and posting;
- moderated-group authorization;
- explicit rejection of NNTP federation commands;
- optional retained IRC channel history and operator-triggered IRC-to-NNTP archival;
- loopback read-only control HTTP API and responsive browser console;
- operator CLI for accounts, groups, articles, audit, archival, configuration validation/diff/stage/apply/rollback;
- candidate configuration backups and rollback evidence;
- safe loopback example configuration;
- systemd sandbox unit and dry-run-first installer;
- protocol integration validator and runbook.

## Safety state

No Edge1 runtime deployment, service start, DNS, firewall, certificate, authentication integration, public listener, IRC federation, NNTP federation, or external communication traffic was performed as part of repository implementation.

Default laboratory listeners:

- IRC `127.0.0.1:16667`;
- NNTP `127.0.0.1:1119`;
- control `127.0.0.1:8099`.

Public plaintext binds are rejected by configuration validation. Control cannot be configured for a non-loopback bind.

## Next operational gates

1. merge repository implementation after CI/review;
2. install on Edge1 without starting and inspect paths/ownership;
3. activate loopback-only service under explicit operational authority and run local acceptance;
4. separately approve and provision TLS identity, DNS/firewall/listener exposure, account policy, and compatibility testing before Internet-facing IRC/NNTP;
5. keep federation disabled until an allowlisted peer/trust design is approved.
