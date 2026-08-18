# WW.CX Messaging Gateway

Provider-neutral SMS/MMS gateway staged separately from FreePBX and Asterisk.

## Safety boundary

This milestone does not change live trunks, transports, firewall rules, DNS, production certificates, carrier profiles, or telephone-number routing. It provides an internal development service and carrier simulator only.

## Capabilities

- Health and readiness endpoints
- Normalized inbound and outbound SMS/MMS event model
- Idempotent simulator intake
- In-memory development event store and PostgreSQL persistence
- Management status and pause/resume controls
- Authenticated bounded conversation reads for operator/Private-AI context
- Local `prepared_not_sent` reply artifacts through the BigBird messaging facade
- Spirit Creek Telegraph Office operator window
- Arbitrary operator-controlled sender identity
- SMS/MMS simulator dispatch receipts and ledger
- Optional browser-coordinate attestation with explicit consent
- Server UTC and client-observed time metadata
- Content and media SHA-256 digests
- PGP-ready armored ciphertext and fingerprint metadata
- Fail-closed MMS media quarantine metadata foundation
- Automated API tests

## MMS media quarantine foundation

MMS media is treated as held by default. The gateway does not fetch provider media URLs through the AI/read surface and does not expose those URLs in quarantine records.

`app/media_quarantine.py` models these states:

- `quarantined_missing_digest`
- `quarantined_pending_scan`
- `scanned_clean_held`
- `quarantined_malicious`
- `quarantined_scan_error`

A trusted scanner may be supplied later by the deployment integration. Until then, media remains `quarantined_pending_scan`. Even an explicit clean scanner result remains `scanned_clean_held`; this module never authorizes release. Actual quarantine storage, malware-engine integration, release workflow, and retention policy remain separate runtime/privileged work.

SMS without media reports quarantine as not applicable rather than inventing malware semantics.

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

- PGP cryptographic operations are not performed by the gateway; only pre-encrypted armored payloads and fingerprints are accepted.
- Clock synchronization fields are modeled, but host NTP state must be populated by the deployment integration.
- Coordinates are an attestation with a source and accuracy radius, not proof of identity.
- MMS quarantine is metadata/fail-closed policy only until private storage and a trusted scanner are attached.
- No live carrier traffic is enabled.

## Next controlled milestones

1. Add a durable queue and worker process.
2. Add a trusted local PGP client or hardware-backed key-agent integration.
3. Populate NTP synchronization and offset from the Edge1 host health service.
4. Implement Telnyx and Bandwidth signature adapters behind the provider interface.
5. Attach private MMS quarantine storage and malware scanning behind the fail-closed foundation.
6. Build the FreePBX user/DID adapter without changing voice routing.
7. Expose a public webhook only after reverse-proxy, WAF, TLS, firewall, and rollback review.
