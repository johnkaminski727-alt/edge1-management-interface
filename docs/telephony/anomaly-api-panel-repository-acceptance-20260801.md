# Telephony Anomaly API and Panel Repository Acceptance — 2026-08-01

## Accepted repository assets

```text
server/telephony_anomaly_indicators.py
server/telephony_analytics_api.py
src/web/telephony/index.html
src/web/telephony/telephony-anomalies.js
src/web/telephony/telephony-anomalies.css
tests/validate_telephony_anomaly_indicators.py
tests/validate_telephony_anomaly_api_panel.py
schemas/telephony/anomaly-indicators.schema.json
docs/telephony/anomaly-indicators.md
docs/telephony/anomaly-api-console-panel.md
```

## Accepted behavior

- the deterministic evaluator consumes only the established aggregate health, call, and interconnect summaries;
- the loopback analytics API exposes `/api/telephony/platform/anomalies` as a read-only GET route;
- the established health response includes the same bounded contract under `anomalies`;
- the console continues to use the existing fixed same-origin health proxy route;
- the original three-route console proxy map remains unchanged;
- the anomaly panel accepts exactly six known indicators and fixed local investigation anchors;
- malformed, unknown, action-capable, or unavailable payloads fail closed;
- every automatic-action and top-level safety flag must be false;
- displayed values are escaped before insertion into HTML;
- no direct browser request to port `8099` exists.

## Explicitly absent

This repository acceptance does not include:

- service installation, enablement, restart, reload, or runtime replacement;
- notification dispatch or alert delivery;
- automated enforcement, traffic blocking, route changes, or remediation;
- call or message origination or DTMF transmission;
- database, AMI/ARI, SIP-trace, packet, log, carrier-portal, or credential access;
- configurable thresholds or user-supplied investigation URLs;
- firewall, DNS, certificate, listener, authentication, or public-exposure changes;
- claims of carrier interoperability, SLA compliance, route readiness, emergency-calling readiness, or regulatory acceptance.

## Validation gate

Repository acceptance requires all of the following to pass on the final merge result:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_anomaly_api_panel.py
node --check src/web/telephony/telephony.js
node --check src/web/telephony/telephony-anomalies.js
```

The general repository workflow must also pass Python compilation, JSON parsing, shell and JavaScript syntax checks, and legacy compatibility validation.

## Edge1 repository validation

Authenticated synchronization and repository validation completed on `edge1.ww.cx` as `wwadmin` at repository head:

```text
92cdccd4c7bda627bd7c5e8986bd0ed301c0ccb7
```

The operator confirmed all required assets, all four focused telephony validations, a clean repository, and `.git/index` owned by `wwadmin:wwadmin` with mode `0600`.

The detailed record is:

```text
docs/telephony/anomaly-api-panel-edge1-repository-validation-20260801.md
```

This validates repository presence and behavior only. It does not establish that the running analytics or console service has loaded these files.

## Runtime state

Runtime deployment remains **not executed**. The running analytics and console services may continue to load older accepted worktrees and must not be described as exposing the anomaly route or panel until a separate bounded deployment and live evidence pass.
