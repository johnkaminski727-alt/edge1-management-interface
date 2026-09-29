# Private Library Search Service Runbook

Date: 2026-07-18
Classification: internal
Scope: managed systemd service for the localhost-only search wrapper

## Purpose

Runs `server/private_library_search_server.py` (via
`bin/run_private_library_search.sh`) as a managed systemd service named
`edge1-private-library-search.service`, so the Private Library Search UI/API
survives reboots and operator logouts.

This closes combined-register open item "Turn search wrapper into managed
systemd service". Per that register, a localhost-only service is safe and
needs no additional approval; exposing any route beyond localhost still
requires explicit approval.

## Boundary

- Binds `127.0.0.1:8091` only. The unit additionally enforces
  `IPAddressAllow=localhost` / `IPAddressDeny=any` as defense in depth.
- Read-only behavior is unchanged: only the `operations` collection, result
  limits clamped, no write endpoints.
- Production search fails closed if the live Library engine/backend is unavailable.
  Fixture results require the explicit development flag
  `EDGE1_LIBRARY_FIXTURE_FALLBACK_ENABLED=1` and must not be enabled for Ava
  production retrieval.
- The unit runs with a read-only view of the repo (`ReadOnlyPaths`) and
  `ProtectSystem=full`. It deliberately does not use `ProtectSystem=strict`
  so that SQLite WAL/shm access to `/var/lib/bigbird-ai-library/` cannot be
  silently blocked (which would downgrade `live_direct` to fixture mode).
  Tighten only after verifying live mode under the service.

## Install

```bash
cd /opt/edge1-management-interface
sudo deploy/install-private-library-search-service.sh
```

The installer refuses to run if the checkout is not at
`/opt/edge1-management-interface` (the unit file hardcodes that path — edit
the unit before installing from a different checkout).

If `config/private-library-search.env` exists, the run script loads it, same
as a manual launch.

## Verify

```bash
deploy/private-library-search-service-smoke-test.sh
```

Checks, in order: the service is active; port 8091 listens on loopback only;
`/api/private-library/search?q=VPN` returns valid JSON and reports its mode
(expect `live_direct` on Edge1); a disallowed collection returns HTTP 400.

The smoke test fails if the mode is fixture-backed. Development/off-box testing
may explicitly set `ALLOW_FIXTURE_SMOKE=1`, but Edge1 acceptance requires
`live_direct` or `live`. A fixture mode on Edge1 means the service process
cannot reach the real Library and must not be treated as valid evidence.

Repo-side asset validation (no root, no systemd needed):

```bash
python3 tests/validate_search_service_assets.py
```

## Operate

```bash
sudo systemctl status edge1-private-library-search.service
sudo systemctl restart edge1-private-library-search.service
sudo journalctl -u edge1-private-library-search.service -n 100 --no-pager
```

To change the port, override the unit rather than editing the installed file:

```bash
sudo systemctl edit edge1-private-library-search.service
```

```ini
[Service]
ExecStart=
ExecStart=/opt/edge1-management-interface/bin/run_private_library_search.sh 8092
```

## Rollback

```bash
sudo systemctl disable --now edge1-private-library-search.service
sudo rm /etc/systemd/system/edge1-private-library-search.service
sudo systemctl daemon-reload
```

Manual launch remains available and unchanged:

```bash
bin/run_private_library_search.sh 8091
```

## Out of Scope

- Any route or reverse proxy beyond localhost (requires approval).
- Human authentication at any route beyond loopback remains the responsibility
  of the Edge1 Private Access Gateway. The loopback wrapper itself is not a
  public authentication endpoint and must not be exposed directly.
- Running the wrapper as a dedicated service user. The unit currently runs as
  root with filesystem/network sandboxing; moving to a dedicated user needs a
  decision about read access to the library DB and should be validated
  against `mode=live_direct` on Edge1 first.
