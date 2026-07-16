# AI Filesystem Write Connector Documentation

Date: 2026-07-16
Status: proposed
Owner: John
Implementation manager: Codex / Gus

## Purpose

This document set defines how Edge1 can safely support AI-assisted filesystem
changes while preserving operator control, auditability, and rollback.

## Read First

1. `ADR-EDGE1-002-ai-filesystem-write-connector.md`
2. `operator-runbook.md`
3. `tool-api-contract.md`
4. `threat-model.md`
5. `acceptance-checklist.md`

## Core Principle

The connector is not direct model filesystem access. It is a staged,
policy-bound, operator-approved write path:

```text
AI proposal
  -> stage
  -> inspect and diff
  -> operator approval
  -> root apply processor
  -> verify
  -> audit
  -> rollback if needed
```

## Initial Scope

Initial production scope should be limited to documentation and management
interface files under:

```text
/opt/edge1-management-interface
```

The first live implementation must not write firewall, DNS, VPN, credential,
identity, package manager, or system service configuration directly.

## Current Related Proof

A local proof of concept demonstrated:

- Staging a proposed write to `/opt/edge1-management-interface/README.md`.
- Refusing apply before approval.
- Generating a running-to-candidate diff.
- Approving as an operator.
- Applying with backup and SHA-256 verification.
- Rejecting a forbidden `/etc/passwd` target.
- Emitting JSONL audit events.
