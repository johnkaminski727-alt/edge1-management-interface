# WW.CX Edge1 Operations Center

## Purpose

The Edge1 Operations Center provides read-only infrastructure visibility.

It is separate from Store Admin and administrative control surfaces.

## Modules

- Security Operations
- Mining Operations
- Bitcoin Operations

## Deployment

Source:

`src/web/operations-center/index.html`

Published by:

`deploy/operations-center/publish.sh`

Destination:

`/var/www/edge1-status/index.html`

## Data Sources

Security:

`/var/www/edge1-status/security-operations.json`

Bitcoin:

`/var/www/edge1-status/bitcoin-wallet.json`

`/var/www/edge1-status/bitcoin-mining.json`

Mining:

`/var/www/edge1-status/mining-operations.json`

## Web Exposure

Apache serves:

`/edge1-status/`

through the `edge1-status` alias.

## Design Principles

- Read-only by default
- Evidence-driven operations
- Controlled actions through Edge1 Operations API
- Separate from Store Admin
