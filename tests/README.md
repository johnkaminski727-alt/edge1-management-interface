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
