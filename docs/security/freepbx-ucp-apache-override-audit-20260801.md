# FreePBX UCP Apache Override Audit - 2026-08-01

## Purpose

A FreePBX-generated security notice reported that `.htaccess` processing is disabled for the User Control Panel. This package prepares a bounded read-only audit that can establish the relevant Apache directory contexts, observed `AllowOverride` directives, FreePBX/UCP `.htaccess` file metadata, and the effective runtime configuration evidence needed for a remediation decision.

This work addresses GitHub issue #242. It does not conclude that overrides should be enabled globally or that the alert's suggested change is safe for the current deployment.

## Repository package

- Policy: `config/security/freepbx-ucp-apache-override-audit-policy.json`
- Auditor: `tools/security/audit_freepbx_ucp_apache_overrides.py`
- Tests: `tests/test_freepbx_ucp_apache_override_audit.py`
- Default evidence root: `/var/lib/wwcx-deployment-evidence/freepbx-ucp-apache-override-audit`

## Evidence captured

The auditor requires `main`, a clean working tree, the canonical Edge1 host identity, root execution, the existing security-completion read-only authorization, and the repository evidence redactor.

It captures:

1. host, principal, repository revision, branch, and clean status;
2. `apache2ctl -t` or the available equivalent;
3. the virtual-host map from `-S`;
4. the loaded-module list from `-M`;
5. the effective runtime configuration dump from `-t -D DUMP_RUN_CFG`;
6. hashes and secret-minimized parsing of Apache configuration files;
7. observed `<Directory>` and `<DirectoryMatch>` contexts;
8. observed `AllowOverride` values and their source locations;
9. candidate FreePBX/UCP document roots;
10. `.htaccess` path, mode, size, SHA-256 hash, and directive names only;
11. a result contract and SHA-256 evidence manifest.

The auditor does not record `.htaccess` directive values, authentication material, cookies, environment variables, private keys, passwords, tokens, raw unredacted command output, or secret-directive values.

## Safety boundary

The package does not:

- edit Apache, FreePBX, UCP, PHP, or systemd configuration;
- enable or disable modules, sites, or configuration fragments;
- reload, restart, start, stop, enable, disable, mask, or unmask a service;
- alter authentication, routes, listeners, firewall rules, DNS, certificates, databases, calls, messages, or production traffic;
- follow symlinks while scanning files;
- determine automatically that a particular `AllowOverride` change is safe.

Evidence-directory creation is the only host write.

## Repository validation

Run from the repository root:

```bash
python3 -m unittest tests.test_freepbx_ucp_apache_override_audit
python3 -m py_compile tools/security/audit_freepbx_ucp_apache_overrides.py tests/test_freepbx_ucp_apache_override_audit.py
```

The normal repository and Edge1 Operator Validation workflows must also pass at the final branch head.

## Authorized operator command

This command is prepared but was not executed by the connector-only repository session:

```bash
cd /opt/edge1-management-interface
sudo python3 tools/security/audit_freepbx_ucp_apache_overrides.py
```

Do not run from a feature branch or dirty working tree. The auditor intentionally refuses both states.

## Review procedure after capture

1. Verify `sha256-manifest.txt` from inside the evidence directory.
2. Confirm `result.json` reports no mutation and a successful Apache configuration test.
3. Review `apache-vhosts.txt` and `apache-runtime-config.txt` to identify the active FreePBX virtual host and document root.
4. Review `apache-override-observations.json` for the most specific matching directory contexts. Apache section merging, regex contexts, included files, and nested directories mean source-order inspection remains necessary.
5. Review `freepbx-htaccess-inventory.json` to identify which UCP paths actually contain `.htaccess` files and which directive classes they require.
6. Classify the alert as one of:
   - unintended override regression;
   - intentional hardening with an incompatible FreePBX expectation;
   - path-specific mismatch;
   - insufficient evidence.
7. If a change is warranted, prepare a separate change package containing the narrowest directory scope, configuration syntax validation, GUI/UCP access checks, authentication non-regression checks, service-reload plan, rollback, and evidence capture.

## Decision gate

No live Apache change is authorized by this package. Enabling `AllowOverride All` broadly is specifically not an accepted default. Any proposed remediation must be path-scoped and justified by captured evidence before separate approval and execution.
