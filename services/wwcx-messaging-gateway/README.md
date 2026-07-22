# WW.CX Messaging Gateway

Provider-neutral SMS/MMS gateway staged separately from FreePBX and Asterisk.

## Safety boundary

This milestone does not change live trunks, transports, firewall rules, DNS, production certificates, carrier profiles, or telephone-number routing. It provides an internal development service and carrier simulator only.

## Capabilities

- Health and readiness endpoints
- Normalized inbound and outbound SMS/MMS event model
- Idempotent simulator intake
- In-memory development event store
- Management status and pause/resume controls
- Spirit Creek Telegraph Office operator window
- Arbitrary operator-controlled sender identity
- SMS/MMS simulator dispatch receipts and ledger
- Optional browser-coordinate attestation with explicit consent
- Server UTC and client-observed time metadata
- Content and media SHA-256 digests
- PGP-ready armored ciphertext and fingerprint metadata
- Automated API tests

## Spirit Creek Telegraph Office

Open:

```text
http://127.0.0.1:8092/telegraph-office
```

The window requires the simulator token for dispatch. It can collect present coordinates only after the operator selects the location option and grants browser permission.

PGP private keys and passphrases are deliberately not accepted by the gateway. Encryption and decryption must occur in a trusted local client. Paste only armored ciphertext and public fingerprints into the operator window. This prevents the simulator service and ordinary logs from becoming a private-key repository.

Endpoints:

```text
POST /v1/telegraph/dispatch
GET  /v1/telegraph/ledger
```

The ledger records message IDs, routing metadata, timestamps, verification digests, coordinate attestations, and PGP fingerprints. It does not intentionally expose private keys or passphrases.

## Run locally

```bash
cd services/wwcx-messaging-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export WWCX_SIMULATOR_TOKEN=development-only
uvicorn app.main:app --reload --port 8092
```

Run tests:

```bash
pytest
```

## Current limitations

- The development ledger is in memory and resets on restart.
- PGP cryptographic operations are not performed by the gateway; only pre-encrypted armored payloads and fingerprints are accepted.
- Clock synchronization fields are modeled, but host NTP state must be populated by the deployment integration.
- Coordinates are an attestation with a source and accuracy radius, not proof of identity.
- No live carrier traffic is enabled.

## Next controlled milestones

1. Replace the in-memory store with PostgreSQL and an immutable raw-event table.
2. Add a durable queue and worker process.
3. Add a trusted local PGP client or hardware-backed key-agent integration.
4. Populate NTP synchronization and offset from the Edge1 host health service.
5. Implement Telnyx and Bandwidth signature adapters behind the provider interface.
6. Add private MMS quarantine storage and malware scanning.
7. Build the FreePBX user/DID adapter without changing voice routing.
8. Expose a public webhook only after reverse-proxy, WAF, TLS, firewall, and rollback review.
