# Edge1 Management Interface Handoff

Date: 2026-07-17
Classification: internal
System: Edge1 management interface

## Current State

The Edge1 management interface repository is installed at:

```text
/opt/edge1-management-interface
```

The project now includes:

- Static Private Library Search UI.
- Local read-only API wrapper at `/api/private-library/search`.
- Live direct bridge to Big Bird's SQLite FTS5 private library engine.
- Fixture fallback for offline validation.
- Localhost-only preview runner.
- Validation scripts for static UI and search wrapper behavior.

## Confirmed Milestones

| Area | Status | Evidence |
| --- | --- | --- |
| Repo bootstrap | Complete | Repo initialized and pushed to GitHub plus local bare remote |
| Static UI | Complete | `python3 tests/validate_static_ui.py` |
| API wrapper | Complete | `python3 tests/validate_private_library_server.py` |
| Live direct search | Complete | `mode: live_direct` result from `operations` collection |
| Library DB access | Complete | ACL grants `wwadmin` read/traverse access to the library DB path |
| Handoff docs | Complete | `docs/handoff/` and `registers/handoff-register-20260717.md` |

## Runbook

Start the local preview:

```bash
cd /opt/edge1-management-interface
bin/run_private_library_search.sh 8091
```

Verify from another Edge1 shell:

```bash
curl -sS "http://127.0.0.1:8091/api/private-library/search?q=VPN&collection=operations&limit=5"
```

Expected live mode:

```text
"mode": "live_direct"
```

## Handoff Notes

- The preview server binds to `127.0.0.1`.
- Browser access from Windows should use SSH port forwarding.
- The wrapper is read-only.
- The UI only exposes the `operations` collection.
- Fixture fallback remains available by setting `EDGE1_LIBRARY_DIRECT_ENABLED=0`.

## Next Recommended Work

1. Add a systemd user or root-managed service for the localhost wrapper.
2. Put the service behind the approved private/VPN route.
3. Add operator authentication at the route boundary.
4. Add a periodic backup policy for the private library database.
5. Add handoff acceptance sign-off after a browser walkthrough.

