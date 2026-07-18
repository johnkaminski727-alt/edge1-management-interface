# WW.CX Engineering Agent Instructions

These instructions govern automated and human engineering work in this repository.

## Authority

Work under `AUTONOMOUS_ENGINEERING_AUTHORIZATION.md`. Routine, safe, reversible repository decisions do not require repeated approval.

## Required workflow

1. Verify the current repository, branch, and relevant implementation before changing files.
2. Prefer focused, reviewable changes with accurate documentation.
3. Never expose secrets, credentials, private records, production data, or unredacted configuration.
4. Run the most relevant available validation before claiming completion.
5. Use branches and pull requests for substantive work.
6. Do not force-push shared branches or rewrite shared history.
7. Treat production changes as separate from repository preparation. Require a bounded change, validated prerequisites, backup or rollback, and health checks.
8. Record material decisions, risks, limitations, and operator-controlled actions.

## Definition of done

A milestone is complete only when implementation, documentation, validation, commit, push, pull-request handling, merge when authorized, and final verification are complete or a genuine external blocker is recorded.

## Repository role

This repository currently hosts the bootstrap seed for the WW.CX Autonomous Engineering Platform. The framework should later be promoted to its dedicated canonical repository and referenced by WW.CX, Big Bird, Edge1, Spirit Creek Gardens, and related projects.
