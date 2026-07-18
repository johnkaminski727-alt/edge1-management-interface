# Private Library Search Service Register - 2026-07-18

| Item | Status | Evidence |
| --- | --- | --- |
| Service unit | Prepared | `deploy/systemd/edge1-private-library-search.service` |
| Installer | Prepared | `deploy/install-private-library-search-service.sh` |
| Smoke test | Prepared | `deploy/private-library-search-service-smoke-test.sh` |
| Operator runbook | Prepared | `docs/handoff/private-library-search-service-runbook.md` |
| Repo-side asset validation | Passing | `python3 tests/validate_search_service_assets.py` |
| Install on Edge1 | Pending operator | Requires root on Edge1 |
| Live smoke on Edge1 | Pending operator | Expect `mode=live_direct` on port 8091 |
| Dedicated service user decision | Deferred | See runbook "Out of Scope" |

## Boundary Notes

- Localhost-only by construction (bind 127.0.0.1) and by unit guardrails
  (`IPAddressAllow=localhost`, `IPAddressDeny=any`).
- No route exposure, no authentication change, no write endpoints. Route
  exposure beyond localhost still requires explicit operator approval.

## Operator Next Actions

1. `cd /opt/edge1-management-interface && git pull` (or apply patches).
2. `python3 tests/validate_search_service_assets.py`
3. `sudo deploy/install-private-library-search-service.sh`
4. `deploy/private-library-search-service-smoke-test.sh`
5. Record the observed search mode here; expect `live_direct`.
6. If fixture mode is reported, check service-process read access to
   `/var/lib/bigbird-ai-library/library.sqlite3` and
   `/opt/bigbird-ai-gateway`.
