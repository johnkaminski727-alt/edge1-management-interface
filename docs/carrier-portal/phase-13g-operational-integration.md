# WW.CX Carrier Portal Phase 13G — Operational Integration

## Status

Implementation candidate. Repository validation and deployment verification remain required before completion is declared.

## Purpose

Phase 13G connects the Phase 13F carrier identity plane to the Phase 13D authenticated Edge1 portal API. It adds carrier-scoped, read-only operational views without exposing credentials, private topology, or production mutation controls.

## Architecture

```text
Carrier portal user
        |
Carrier portal API client
        |
HMAC authenticated request
        |
Portal identity resolution
        |
Scope authorization
        |
Carrier tenant filter
        |
San