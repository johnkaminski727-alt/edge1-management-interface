# Edge1 Communications Relay Runbook

Version: 1.0.0  
Last reconciled: 2026-08-17

## Current production baseline

Accepted private listeners:

- IRC: `127.0.0.1:16667`;
- NNTP: `127.0.0.1:1119`;
- control/API/News Reader: `127.0.0.1:8100`.

Telephony analytics remains separate on `127.0.0.1:8099`.

Accepted outbound Eternal September mappings:

- `eternal.comp.lang.python`: `comp.lang.python` -> `usenet.comp.lang.python`;
- `eternal.news.admin.peering`: `news.admin.peering` -> `usenet.news.admin.peering`.

Accepted News Reader deployment:

- branch `deploy/private-nntp-news-reader-v2-20260817`;
- head `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result `NEWS_READER_V2_DEPLOYMENT=PASS`.

Do not assume current remote `main` is the production checkout. Unrelated time-authority work is present on remote `main`; deploy it only through its own acceptance process.

## Standard health verification

```sh
systemctl is-enabled edge1-comms-relay.service
systemctl is-active edge1-comms-relay.service
python3 deploy/comms-relay/smoke-test.py --config /etc/wwcx/comms-relay.json
ss -ltnp | grep -E ':(16667|1119|8100)'
bin/commsctl --config /etc/wwcx/comms-relay.json status
journalctl -u edge1-comms-relay.service --since '-10 minutes' --no-pager
```

Expected posture is loopback-only on the three relay ports.

## Readiness after restart

The service unit uses systemd `Type=simple`. `systemctl is-active` can report active before the Python control listener has bound.

After restart, use bounded readiness instead of a one-shot curl:

```sh
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8100/healthz >/dev/null; then
    echo "relay_ready attempt=$attempt"
    break
  fi
  sleep 0.5
done
curl -fsS http://127.0.0.1:8100/healthz | jq .
ss -ltnp | grep -E ':(16667|1119|8100)'
```

If bounded readiness fails, inspect the journal and use the applicable rollback path. Do not treat immediate active process state as sufficient readiness evidence.

## Initial install / reinstall gate

For an installation change, first freeze the intended clean checkout and run:

```sh
cd /opt/edge1-management-interface
git status --short --branch
deploy/comms-relay/install.sh --dry-run --expected-commit=<COMMIT>
python3 tests/validate_comms_relay.py
```

The installer permits dry-run inspection on a frozen feature/deployment checkout, but its live `--apply` path explicitly requires a clean `main` checkout. Therefore do **not** run the live installer from the accepted News Reader deployment branch. Before any future installer-based production change, first reconcile the exact intended implementation into a separately reviewed `main` commit, freeze that commit, and use it as `<COMMIT>`.

This installer rule does not require moving the currently accepted production checkout merely to complete documentation or archive work.

Do not alter DNS, firewall rules, certificates or listener addresses as part of the private loopback deployment.

Install without activation from the reviewed clean `main` commit:

```sh
sudo deploy/comms-relay/install.sh --apply --expected-commit=<COMMIT>
```

Activate only when the intended deployment change has been separately reviewed:

```sh
sudo deploy/comms-relay/install.sh --apply --start --expected-commit=<COMMIT>
```

The installer preserves prior unit/config/service state, records protected evidence and rolls back on activation failure.

## Founder account

Use an interactive terminal rather than command-line password arguments:

```sh
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json account add john --role founder
```

Never put password values in command history, documentation or evidence.

## Routine operations

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json account list
bin/commsctl --config /etc/wwcx/comms-relay.json group list
bin/commsctl --config /etc/wwcx/comms-relay.json article list wwcx.projects.edge1
bin/commsctl --config /etc/wwcx/comms-relay.json ingest status
bin/commsctl --config /etc/wwcx/comms-relay.json audit --limit 100
bin/commsctl --config /etc/wwcx/comms-relay.json maintenance prune
```

Private News Reader:

`http://127.0.0.1:8100/news.html`

## Configuration changes

Always preserve candidate/running configuration control:

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json config validate candidate.json
bin/commsctl --config /etc/wwcx/comms-relay.json config diff /etc/wwcx/comms-relay.json candidate.json
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json config stage candidate.json
sudo bin/commsctl --config /etc/wwcx/comms-relay.json config apply
sudo systemctl restart edge1-comms-relay.service
```

Then use bounded `/healthz` readiness and the smoke test.

Rollback:

```sh
sudo bin/commsctl --config /etc/wwcx/comms-relay.json config rollback
sudo systemctl restart edge1-comms-relay.service
```

Again use bounded readiness after restart.

## Adding one outbound NNTP source

Do one mapping at a time.

1. Freeze and record the clean local checkout.
2. Verify relay health and existing source state.
3. Record config and credential-file metadata without reading credential contents.
4. Capture a fresh config backup and SQLite `.backup`.
5. Create exactly one candidate mapping.
6. Validate and diff the candidate.
7. Run an attended real-TLS dry run.
8. Prove dry-run non-mutation of group/article/cursor/ingest state.
9. Stage/apply, restart only the relay and wait for bounded readiness.
10. Verify the exact new source and loopback-only listeners.
11. Run attended ingestion. If the result is `already_running`, wait for the scheduled worker and retry; do not bypass the lock.
12. Run/observe a later pass as needed for the `wwcx-bootstrap` `<group>:v1` introduction.
13. Validate source-specific ledger count, unique source IDs, target group, stored provenance, cursor, bootstrap count, orphan/wrong-group/unexpected-provenance counts and ingestion errors.
14. Preserve evidence and create/update the dated acceptance record.

Do not compare total group articles directly with only the external-source ledger count.

## Credential handling

Accepted Eternal September credential file:

`/etc/wwcx/credentials/eternal-september.json`

Accepted metadata:

`root:wwcx-comms 0640`

Never `cat`, copy, commit, paste or archive the credential values. Archive work may record metadata-only exclusion evidence.

## Incident containment

To stop communications without deleting state:

```sh
sudo systemctl stop edge1-comms-relay.service
```

Do not delete the SQLite database during incident handling. Preserve `/var/lib/wwcx-comms`, configuration, relevant journal logs and deployment evidence for diagnosis.

## Archive preparation

Current closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Archive state is **prepared, not sealed**.

The next archive action is read-only:

1. locate the exact News Reader v2 protected evidence directory;
2. inventory every retained file in the closeout source ledger;
3. record SHA-256, path, size, mode, owner/group and mtime;
4. hash live config and SQLite without copying them into Git;
5. prove credential contents are excluded;
6. reconcile retained/unavailable/duplicate/error totals;
7. rerun for idempotence;
8. update the closeout with the final manifest path/hash.

Do not move, delete or prune evidence merely to make an archive package tidy.

## External exposure gate

Internet-facing IRC/NNTP is not part of this runbook. Before any exposure, separately approve and validate TLS identity/certificate handling, DNS, firewall policy, public ports, client compatibility, abuse policy and monitoring.

Formal NNTP peering, inbound feeds, streaming federation, upstream posting and private `wwcx.*` forwarding remain disabled unless separately designed and authorized.
