# Edge1 Final Acceptance Checklist

Date: 2026-07-17
Classification: internal

Run from:

```bash
cd /opt/edge1-management-interface
```

## Repository

```bash
git status --short --branch
git log --oneline --max-count=8
git remote -v
```

Expected:

- Worktree clean.
- Latest autonomous/handoff commits present.
- `origin` and `edge1-local` configured.

## Validation

```bash
python3 tests/validate_static_ui.py
python3 tests/validate_private_library_server.py
python3 tools/handoff/verify_handoff_state.py
```

Expected:

- Static UI validation passes.
- Server validation passes.
- Handoff verifier reports no failed required checks.

## Live Search

Start:

```bash
bin/run_private_library_search.sh 8091
```

Verify from another shell:

```bash
curl -sS "http://127.0.0.1:8091/api/private-library/search?q=VPN&collection=operations&limit=5"
```

Expected:

```text
"mode": "live_direct"
```

## Backup

```bash
sudo sha256sum -c /var/backups/bigbird-ai-library/*.sha256
```

Expected:

- Every current manifest reports `OK`.

## Push

```bash
git push origin main
git push edge1-local main
```

Expected:

- Both remotes up to date.

