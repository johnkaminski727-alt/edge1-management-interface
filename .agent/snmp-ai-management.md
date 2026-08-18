# SNMP + AI Management Workstream

Last updated: 2026-08-18

## Objective

Implement the WW.CX / Edge1 SNMP Management and AI Operations Platform as a private-first Operations Center workstream with SNMPv3 preferred, bounded automation, auditable evidence and no secret values in Git.

## Repository state

Implementation branch: `feature/snmp-ai-management-platform-20260818`  
Base: repository `main` at `7ca3b8360de740d844edcb8c598b1988407a16e5`.  
Draft PR: `#410`.

## Implemented in repository branch

- SQLite inventory, interface, telemetry, event, alert, MIB, polling-profile, topology, action-proposal and audit stores.
- SNMPv3-authPriv credential-reference model with private-mode checks and no inventory secret values.
- Net-SNMP GET/WALK/BULK wrapper foundation with redacted failures.
- bounded CIDR discovery preview and authenticated SNMP probe logic;
- standard system polling plus interface inventory and 64-bit counter collection where available;
- counter wrap/reset/reboot math and statistical anomaly helper;
- trap normalization and duplicate suppression with `snmptrapd` handoff;
- MIB object store, lookup/search and Net-SNMP module import path;
- default deterministic alert policies with open-alert deduplication;
- evidence-labelled topology links that distinguish confirmed from inferred evidence;
- cross-resource search;
- evidence-backed deterministic AI/provider abstraction boundary;
- deterministic action-class policy and proposal audit;
- loopback-only HMAC-authenticated SNMP API with devices/interfaces/metrics/events/alerts/MIBs/discovery/topology/search/AI/actions/audit resources;
- integrated polling/interface/alert/retention cycle;
- Operations Center SNMP page;
- hardened systemd service/timer and reversible staged installer assets;
- operator/security documentation and rollback runbook.

## Validation

Local isolated validation on 2026-08-18:

- `tests/validate_snmp_platform.py`: 10/10 passed;
- `tests/validate_snmp_services.py`: 7/7 passed;
- Python core/API/services/cycle/trap-handler modules compile;
- JSON configuration/API contract templates parse.

These are repository validations only, not production acceptance.

## External blocker

No authenticated Edge1 execution path is available in the current tool environment. Therefore host preflight, package inspection/installation, production checkout verification, current database/monitoring-stack reconciliation, Net-SNMP live checks, controlled SNMPv3 poll, trap/inform delivery, systemd activation, listener/firewall verification, Operations Center publication, runtime security review and unrelated-service health validation remain unexecuted. The optional Edge1 SNMP agent/AgentX decision also requires this live inspection. Do not mark the platform production-complete until those checks are performed through an authenticated Edge1 path.

## IANA PEN state

No WW.CX Private Enterprise Number is claimed in repository code or documentation. Public IANA searches performed during this work did not establish an assigned PEN for WW.CX / Christmas Island Worldwide; this remains a verification item before any externally standardized custom enterprise OID tree is published.

## Security notes

No SNMP credentials, community strings, API secrets or private runtime evidence are stored here. No firewall, DNS, SSH, authentication, routing, certificate or telecommunications change has been made by this repository-only work.
