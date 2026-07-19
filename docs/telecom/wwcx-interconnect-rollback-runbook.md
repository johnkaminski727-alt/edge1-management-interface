# WW.CX SIP Interconnect Rollback Runbook

Status: staging guidance. Commands that change a live host require an approved maintenance window.

## Rollback objective

Remove the new interconnect path without changing existing FreePBX transports, trunks, extensions, or carrier service.

## Preconditions

- Capture the current listener, service, firewall, DNS, and Asterisk state.
- Record every file copied to `/etc/kamailio` or `/etc/asterisk`.
- Keep timestamped backups outside the active configuration directories.
- Confirm console or out-of-band access before public activation.

## Staging rollback

If Kamailio is loopback-only and no Asterisk files were included:

```bash
sudo systemctl stop kamailio
sudo systemctl disable kamailio
sudo ss -lntp | grep ':5061' || true
```

Stopping a loopback-only staging listener should not affect existing Asterisk service.

## Asterisk-template rollback

Only use after verifying the exact include mechanism used during deployment.

1. Remove or comment the dedicated WW.CX include lines.
2. Run configuration checks before reload.
3. Reload only the affected Asterisk modules; do not restart the host blindly.
4. Confirm existing endpoints, registrations, trunks, and calls.

Suggested read-only verification:

```bash
sudo asterisk -rx 'pjsip show transports'
sudo asterisk -rx 'pjsip show endpoints'
sudo asterisk -rx 'pjsip show registrations'
sudo asterisk -rx 'core show channels'
```

## Public listener rollback

If public TCP 5061 was activated:

1. Stop Kamailio.
2. Revert only the dedicated TCP 5061 firewall allowance.
3. Verify no process listens on public TCP 5061.
4. Preserve Apache TCP 443 and existing Asterisk UDP 5060 rules.
5. Withdraw the SIP SRV record as a separate operator-controlled DNS action if the outage will persist.

Do not delete certificates during incident rollback. Preserve them for evidence and diagnosis, with private-key permissions unchanged.

## Validation after rollback

- Existing inbound and outbound FreePBX test calls pass.
- Existing provider registrations remain available.
- Apache HTTPS remains available.
- No public TCP 5061 listener remains.
- The loopback Asterisk backend port is absent unless intentionally retained.
- Logs and the change record include the rollback time, operator, reason, and observed outcome.

## Abort conditions

Stop and escalate if rollback would require changing an unknown FreePBX-generated file, interrupting active emergency traffic, removing a shared certificate, or altering a firewall rule whose ownership is unclear.
