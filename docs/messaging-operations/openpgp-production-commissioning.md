# WW.CX OpenPGP production commissioning

## Current boundary

The OpenPGP application and isolated crypto service are installed in fail-closed mode. The service runs as `wwcx-openpgp`, uses `/var/lib/wwcx-openpgp/gnupg`, exposes only `/run/wwcx-openpgp/crypto.sock`, and does not support private-key export. Signing, encryption, and decryption remain disabled until acceptance succeeds.

## Production identity

Initial identity: `John Kaminski <john@ww.cx>`.

Recommended hierarchy:

- offline/recovery-capable certification primary key;
- dedicated signing subkey;
- dedicated encryption subkey;
- primary validity target: 5 years;
- operational subkey validity target: 2 years;
- revocation material created and stored separately from Edge1.

The primary recovery key should be created outside the online mail runtime. Import only the operational secret material needed by Edge1 into the isolated `wwcx-openpgp` GNUPG home. Do not place secret key material in Git, Contacts, Mail Room, AVA, web roots, logs, or ordinary backups.

## Manual secret-key handoff

Secret-key creation/import is intentionally outside the ChatGPT shell boundary. After the operator imports the approved production operational secret key into `/var/lib/wwcx-openpgp/gnupg` as `wwcx-openpgp`, return to the automated acceptance sequence below.

No private-key export is required for normal commissioning.

## Automated acceptance after import

1. Run `tools/messaging/openpgp_commissioning_status.py` and confirm the isolated service reports at least one secret key while all live operations are still disabled.
2. Export **only the public key** from the approved offline/public source to a temporary public `.asc` file.
3. Register it against Contact point `696` (`john@ww.cx`) with `tools/messaging/register_openpgp_public_key.py --public-key-file <public.asc> --mode sign_only`.
4. Publish the verified public key with `tools/messaging/publish_openpgp_public_key.py --contact-point-id 696 --slug john-wwcx`.
5. Re-run `openpgp_commissioning_status.py`; require `ready_for_sign_only=true` before activation.
6. Enable `sign_enabled=true` only. Keep encryption and decryption false.
7. Restart `wwcx-openpgp-crypto.service` and perform a controlled local PGP/MIME signed-message test.
8. Verify the detached signature using a separate public-key-only verification context.
9. Verify DKIM remains independent and unchanged.
10. Only after signing acceptance, consider per-recipient encryption.

## Encryption policy

Contacts may use these modes:

- `disabled`
- `sign_only`
- `encrypt_if_verified_key`
- `require_encryption`

Encryption must never occur without a verified recipient public key. `require_encryption` must fail closed rather than fall back to plaintext.

## Inbound encrypted mail

Encrypted originals are archived first and preserved. Ciphertext is held from normal correspondence ingestion until the isolated decryptor is commissioned. Decrypted content must be malware/security scanned before becoming readable Mail Room/AVA content. Decrypted working copies are not persisted by default.

## Rollback

If signing acceptance fails:

- set `sign_enabled=false`;
- restart `wwcx-openpgp-crypto.service`;
- leave the public key/fingerprint in Contacts only if its identity verification is still valid;
- do not enable encryption/decryption;
- preserve signed-message acceptance evidence without message plaintext or secret-key material.
