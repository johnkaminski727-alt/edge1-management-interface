# WW.CX Edge1 Operations Center

## Purpose

The Edge1 Operations Center provides read-only infrastructure visibility.

It is separate from Store Admin and administrative control surfaces.

## Modules

- Security Operations
- Mining Operations
- Bitcoin Operations
- VPN Access Registration summary

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

VPN registration:

`/var/www/edge1-status/vpn-access-registration.json`

The VPN registration export is aggregate-only and always reports whether
enforcement is active. Detailed device and acceptance records remain behind
the authenticated loopback Operations API.

## Web Exposure

Apache serves:

`/edge1-status/`

through the `edge1-status` alias.

## Design Principles

- Read-only by default
- Evidence-driven operations
- Controlled actions through Edge1 Operations API
- Separate from Store Admin
