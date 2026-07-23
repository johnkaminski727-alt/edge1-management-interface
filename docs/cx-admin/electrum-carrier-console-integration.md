# Electrum and carrier console integration

## Scope

The Unified Administration Control Centre includes Electrum and carrier operations as first-class modules while preserving their existing security boundaries.

## Electrum Watch Console

The Electrum module is an observation surface over the Edge1 localhost-only watch API.

It may display:

- service and API health;
- wallet loaded state and watch-only classification;
- confirmed, unconfirmed, and total balances;
- synchronization freshness and last successful collection;
- server connectivity and non-secret network status;
- evidence-backed warnings when data is stale or unavailable.

It must not expose:

- seed phrases, private keys, wallet passwords, RPC credentials, or unrestricted RPC;
- transaction signing, broadcast, address import, wallet creation, or wallet mutation;
- arbitrary Electrum commands or shell execution.

The initial permission is `finance.electrum.watch.read`. The operational boundary is `watch_only_read_only`.

## Carrier Operations

Carrier Operations presents carrier-scoped exported summaries from the authenticated portal API, including:

- carrier profile and relationship state;
- interconnect inventory and health;
- numbering summaries;
- operational metrics and monitoring results;
- freshness, provenance, and filtering scope.

The console must preserve carrier ownership filtering and must not expose private topology, credentials, or another carrier's records.

## Carrier Analysis

Carrier Analysis combines authorized summaries into scorecards and trends for:

- interconnect availability;
- quality and error rates;
- routing outcomes represented by exported data;
- capacity and utilization;
- support volume and aging;
- comparison to a defined baseline.

Findings are advisory and evidence-backed. They cannot change routing, numbering, emergency calling, certificates, firewall policy, STIR/SHAKEN, or production traffic.

## Carrier Requests

Carrier Requests uses the existing ticket and change-request workflows. It records a request with a signed body and scoped authorization.

A submitted request is not an approval and is never execution authority. The UI must display `request_only_no_execution` prominently and retain the generated ticket or change ID for audit correlation.

## Carrier Review Queue

The internal review module supports acknowledgement, review start, information requests, closure, and rejection where already supported. It remains explicitly non-executing and cannot grant approval, schedule work, or authorize a production change.

## Navigation placement

- Observe: Electrum Watch Console, Carrier Operations
- Analyze: Carrier Analysis
- Control: Carrier Requests, Carrier Review Queue

## Data contract requirements

Every response adapter must provide:

- source name and environment;
- generated and collected timestamps;
- freshness state;
- authorization scope used;
- sanitized payload version;
- correlation or audit identifier when available;
- explicit read-only or non-executing boundary.

The browser receives only the minimum sanitized response needed for the page. Credentials and backend signing material remain server-side.
