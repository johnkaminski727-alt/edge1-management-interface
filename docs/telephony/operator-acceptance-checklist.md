# Telephony Console Operator Acceptance Checklist

Use this checklist before treating the Big Bird Telephony Operations console as accepted for read-only operational use. It does not authorize production routing, PBX configuration, carrier administration, public exposure, or service changes.

## 1. Repository preflight

- [ ] Confirm the checkout is on the intended reviewed commit.
- [ ] Confirm the working tree contains no unrelated or unreviewed changes.
- [ ] Run `python3 tests/validate_telephony_console.py` and retain the result.
- [ ] Review the base-to-head diff for secrets, private records, production addresses, and unintended executable changes.

## 2. Safe installation boundary

- [ ] Confirm the service binds only to `127.0.0.1`.
- [ ] Confirm access is through the host itself or an approved private tunnel.
- [ ] Confirm no firewall, DNS, certificate, Asterisk, FreePBX, Kamailio, carrier, or emergency-calling configuration is changed.
- [ ] Confirm the installer target paths and service account match the approved host design.

## 3. Read-only behavior

- [ ] Confirm `/healthz` responds without requiring production credentials.
- [ ] Confirm `/api/telephony/status` returns a normalized snapshot.
- [ ] Confirm unavailable integrations degrade to `unknown`, `degraded`, or sanitized fallback data rather than triggering a mutation.
- [ ] Confirm no endpoint permits reload, restart, route change, block, registration change, message submission, or credential management.
- [ ] Confirm logs and responses contain no SIP passwords, tokens, message bodies, recordings, or unredacted customer records.

## 4. Integration observations

Record each integration as **verified**, **unavailable**, or **not configured**. Do not represent an unavailable observation as a passing result.

| Integration | Expected observation | Result | Evidence |
| --- | --- | --- | --- |
| Asterisk service | service state and bounded read-only metrics |  |  |
| SIP listener | local listener posture only |  |  |
| Numbering node | loopback health response |  |  |
| Messaging gateway | configured health response or explicit unknown state |  |  |
| Big Bird gateway | service posture without administrative access |  |  |
| Browser console | live read-only mode or sanitized fixture fallback |  |  |

## 5. Smoke test

Run only after the repository validation succeeds:

```bash
sudo sh deploy/telephony/install-telephony-console.sh
sh deploy/telephony/telephony-console-smoke-test.sh
curl -fsS http://127.0.0.1:8096/api/telephony/status | python3 -m json.tool
```

- [ ] Confirm the smoke test passes.
- [ ] Confirm the returned `mode` accurately identifies live read-only or fallback operation.
- [ ] Confirm the service remains loopback-only after restart.
- [ ] Confirm existing telephony traffic and registrations are unchanged.

## 6. Stop conditions

Stop acceptance and preserve evidence when any of the following occurs:

- the service binds to a non-loopback address;
- a test requires credentials not already provisioned through approved secret management;
- output exposes customer data, message content, recordings, authentication material, or private network details;
- the installer changes PBX, carrier, routing, emergency-calling, DNS, firewall, or certificate state;
- required validation fails or the reviewed commit changes;
- live traffic, registrations, or message delivery changes during verification.

## 7. Acceptance record

Record the following in the pull request, project register, or approved evidence system:

- repository and commit SHA;
- operator and UTC date;
- validation and smoke-test commands;
- exact pass, fail, unavailable, and skipped results;
- listener address and port;
- observed integrations and redactions;
- unresolved risks or follow-up work;
- rollback or service-removal command.

Acceptance applies only to the reviewed read-only console version and host. Any future write control or public exposure requires a separate staged proposal, approval, verification, audit, and rollback workflow.
