# Private Library Search Live Direct Bridge

Date: 2026-07-17
Classification: internal

## Purpose

The Private Library Search module provides an operator-friendly read-only search
surface for approved private library records in the `operations` collection.

## Architecture

```text
Browser UI
  -> /api/private-library/search
  -> server/private_library_search_server.py
  -> /opt/bigbird-ai-gateway/app/library_engine.py
  -> /var/lib/bigbird-ai-library/library.sqlite3
```

## Backend Order

The wrapper attempts search in this order:

1. Direct local Big Bird library engine search.
2. Optional HTTP backend configured by `EDGE1_LIBRARY_SEARCH_URL`.
3. Local fixture fallback.

## Live Direct Requirements

The wrapper process needs:

- Traverse access to `/var/lib/bigbird-ai-library`.
- Read access to `/var/lib/bigbird-ai-library/library.sqlite3`.
- Import access to `/opt/bigbird-ai-gateway/app/library_engine.py`.

Current ACL pattern:

```text
user:wwadmin:r-x /var/lib/bigbird-ai-library
user:wwadmin:r-- /var/lib/bigbird-ai-library/library.sqlite3
```

## Validation

```bash
cd /opt/edge1-management-interface
python3 tests/validate_private_library_server.py
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("s", "server/private_library_search_server.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.search_payload("VPN", "operations", 5)[1]["mode"])
PY
```

Expected:

```text
live_direct
```

