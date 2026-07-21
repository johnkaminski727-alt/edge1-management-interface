# Production Node Staging Architecture

## Model

A production node is built as a reproducible sibling of Edge1 and promoted through explicit lifecycle states. Staging software on a host does not itself authorize the host to carry production traffic.

## Components

- **Node manifest:** non-secret machine contract and safety flags.
- **Manifest validator:** dependency-free guard that rejects production-impact enablement in the staging profile.
- **Host preflight:** read-only evidence capture for host facts, commands, listeners, and failed units.
- **Runbook:** promotion prerequisites, evidence requirements, and rollback posture.
- **Repository tests:** ensure the public example remains passive and unsafe changes fail validation.

## Trust boundaries

The repository contains sanitized examples only. Host identities, credentials, certificates, private addresses, production databases, customer data, carrier assignments, and unredacted diagnostics stay outside the public repository.

## Initial deployment posture

The first candidate should be passive, privately reachable, monitored, backed up, and unable to originate customer calls or messages. It should use test integrations or read-only replicas until a separate promotion decision is approved.
