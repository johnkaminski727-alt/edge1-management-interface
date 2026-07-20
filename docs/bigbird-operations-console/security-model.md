# BigBird Operations Console Security Model

## Current Controls

- HMAC SHA-256 authentication
- timestamp validation
- nonce replay protection
- private credential storage
- read-only monitoring boundary

## Separation of Responsibilities

Monitoring:
read-only visibility

Analytics:
read-only reporting

Management:
separately authorized controlled operations

These capabilities must remain separated.
