# Mail Room live reconciliation — 7 October 2026

The operator page displayed contradictory sending text because the live Send workflow had retained draft-only sender labels. Git also lacked the live runtime base modules and several deployed page refinements.

Merged the mail-room-send-auth, mail-room-tabs-wrap, and WW.CX SPF branches into the commissioning branch. Reconciled Mail Room bridge, signed send client, security and reporting modules, and local MTA support from the running releases. Preserved deployed contact suggestions, signature defaults, composer headings, and reading layout. Sender notes now use live gateway status and the selected identity. Versioned asset URLs refresh cached browser assets.

Deployment: deploy/email/mail-room-send/install.sh --update, then deploy/email/mail-room-send/publish-web.sh. Sending policy and identity activation remain in root-owned runtime configuration. The historical single-domain activation script is archived and must not be reapplied to the multi-domain server.

Validation: 49 tests passed in isolated groups, JavaScript syntax passed, unsigned live sends returned 401, and signed malformed requests returned 400 without sending mail. All five mail services were active after deployment. Published HTML, JavaScript, and CSS matched repository source byte for byte. No delivery test messages were sent during this reconciliation.

The send-route test module installs global import mocks; run it separately from the feature tests. Security-update warnings remain visible until their underlying update health is verified. Server acceptance alone does not establish inbox placement or per-domain SPF/DKIM/DMARC results.

Preservation: /var/backups/mail-room-git-sync-20261007T080929Z; runtime rollback: /root/mail-room-send-update-20261007T081156Z; website rollback: /var/backups/mail-room-web-20261007T081219Z. Original uncommitted work is also retained in the named Git stash.

## Operational commissioning acceptance

At 08:20 UTC the configured catch-all policy was completed for all five domains. Runtime previews verified both original-recipient reply identities and the per-domain contact default; john@ww.cx remains the private identity. Twenty public MX/SPF/DMARC/DKIM presence checks passed. Update health reported no warnings. The Health interface now uses the commissioned and sending_enabled values supplied by the readiness report.

The isolated mail-data restore rehearsal passed: three SQLite databases, 107 file hashes including 68 archive files, and a Redis snapshot containing 63 keys. This establishes the documented mail data/configuration rehearsal scope only; it does not establish a full-server rebuild or an external DNS rollback. External DNS rollback rehearsal remains explicitly unverified. Twelve catch-all, feature, and local-route regression tests passed. No external messages were sent during this acceptance.
