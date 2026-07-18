# Tests

Initial test targets:

- fixture JSON validates
- mobile result cards do not require horizontal scroll
- desktop result layout can show source metadata and detail panel
- API wrapper clamps collection and limit
- error responses do not leak backend internals

Run the complete dependency-free validation suite:

```bash
for test_file in tests/validate_*.py; do
    python3 "$test_file"
done
```

GitHub Actions also imports the shared-host Time Authority collector inside a real Python 3.6 container so cPanel-runtime compatibility cannot silently regress.

`validate_time_authority_rollout_simulation.py` executes both real installers against isolated temporary directories, a fake systemd/crontab layer, a local NTP responder, and the real dashboard API. It does not require root and cannot address production systemd while simulation mode is active.
