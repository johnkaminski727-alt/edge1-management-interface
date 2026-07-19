# Edge1 Post-Merge Validation — 2026-07-19

## Purpose

Validate the merged telephony console, numbering node, SIP interconnect staging assets, and BigBird messaging adapter on Edge1 without enabling public routing, carrier traffic, emergency calling, messaging delivery, DNS, firewall, certificate, or credential changes.

## Safety boundary

This runbook permits repository synchronization and read-only or loopback-only validation. Stop before any command would:

- expose a listener beyond `127.0.0.1`;
- alter Asterisk, FreePBX, Kamailio, carrier routing, emergency calling, STIR/SHAKEN, DNS, firewall, or certificates;
- create, reveal, rotate, or transmit credentials;
- send calls or messages;
- activate a carrier account, DID, port, or interconnect.

## 1. Repository preflight

```bash
cd /opt/edge1-management-interface

git status --short
git branch --show-current
git rev-parse HEAD
git fetch origin main
git log --oneline --decorate -5 --all
```

If `git status --short` shows local changes, inspect and preserve them before pulling. Do not discard unknown work.

When the tree is clean and the current branch is `main`:

```bash
git pull --ff-only origin main
git rev-parse HEAD
git status --short
```

Expected repository state: current `main`, clean working tree, and a commit at or after merge commit `4dc0ef3401505d78b398986c1dfb7509e782960c`.

## 2. Repository validation

```bash
python3 tests/validate_telephony_console.py
bash deploy/interconnect/validate-staging-assets.sh
python3 -m unittest -v tests/test_wwcx_numbering_node.py
python3 -m unittest -v integrations/bigbird-messaging/tests/test_client.py
python3 -m unittest -v integrations/bigbird_messaging/test_tools.py
```

Record exact pass, fail, skipped, and unavailable results. Do not describe an unavailable dependency as passing.

## 3. Listener and service inspection

Read-only inspection:

```bash
systemctl is-active wwcx-numbering-node.service || true
systemctl is-active wwcx-telephony-console.service || true
systemctl is-active bigbird-ai-gateway.service || true
systemctl is-active wwcx-messaging-gateway.service || true

sudo ss -lntup | grep -E ':(8093|8094|8096)\b' || true
```

Expected safety posture:

- numbering node, when active, listens only on `127.0.0.1:8093`;
- telephony console, when active, listens only on `127.0.0.1:8096`;
- no new public SIP, HTTP, or messaging listener is created by validation.

Stop immediately if either `8093` or `8096` is bound to a non-loopback address.

## 4. Numbering-node health

When the service is already installed and active:

```bash
curl -fsS http://127.0.0.1:8093/healthz | python3 -m json.tool
curl -fsS http://127.0.0.1:8093/api/sources | python3 -m json.tool
```

Record source names, accepted and rejected row counts, and available checksum/provenance fields. Do not import an official production dataset until its format, provenance, and redistribution terms have been verified.

## 5. Telephony-console acceptance

Run repository validation before installation. Installation requires `sudo` and creates or updates a localhost-only service, so review the installer before execution:

```bash
sed -n '1,240p' deploy/telephony/install-telephony-console.sh
sed -n '1,240p' deploy/telephony/telephony-console-smoke-test.sh
```

When the scripts still match the reviewed loopback-only design:

```bash
sudo sh deploy/telephony/install-telephony-console.sh
sh deploy/telephony/telephony-console-smoke-test.sh
curl -fsS http://127.0.0.1:8096/healthz | python3 -m json.tool
curl -fsS http://127.0.0.1:8096/api/telephony/status | python3 -m json.tool
sudo ss -lntp 'sport = :8096'
```

Complete `docs/telephony/operator-acceptance-checklist.md`. Confirm that existing calls, registrations, routes, and messaging delivery remain unchanged.

## 6. BigBird messaging adapter validation

The merged adapter is disabled by default. Validate files and tests only; do not add credentials or enable control tools:

```bash
sed -n '1,240p' integrations/bigbird-messaging/README.md
python3 -m json.tool integrations/bigbird-messaging/tool-manifest.json >/dev/null
python3 -m json.tool integrations/bigbird-messaging/contract/management-api-v1.json >/dev/null
```

Do not activate pause/resume controls, provider delivery, public webhooks, or live messaging without a separate approved deployment gate.

## 7. Evidence capture

Create a timestamped directory and capture only sanitized operational output:

```bash
EVIDENCE="/tmp/edge1-post-merge-validation-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$EVIDENCE"

{
  date -u
  hostname -f
  id
  git rev-parse HEAD
  git status --short
} >"$EVIDENCE/preflight.txt"

systemctl is-active wwcx-numbering-node.service >"$EVIDENCE/numbering-service.txt" 2>&1 || true
systemctl is-active wwcx-telephony-console.service >"$EVIDENCE/telephony-console-service.txt" 2>&1 || true
sudo ss -lntup >"$EVIDENCE/listeners.txt" 2>&1 || true
curl -fsS http://127.0.0.1:8093/healthz >"$EVIDENCE/numbering-health.json" 2>&1 || true
curl -fsS http://127.0.0.1:8096/api/telephony/status >"$EVIDENCE/telephony-status.json" 2>&1 || true

printf '%s\n' "$EVIDENCE"
```

Before attaching evidence to an issue or repository record, inspect it for secrets, customer data, message bodies, recordings, private activation links, and internal addresses that should remain private.

## Completion record

Record:

- deployed repository commit;
- operator and UTC timestamp;
- validation results;
- service states;
- listener addresses;
- health responses;
- dataset checksum/provenance state;
- acceptance-checklist result;
- any stopped or unavailable checks;
- confirmation that public routing and production service configuration were unchanged.
