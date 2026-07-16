# Tests

Initial test targets:

- fixture JSON validates
- mobile result cards do not require horizontal scroll
- desktop result layout can show source metadata and detail panel
- API wrapper clamps collection and limit
- error responses do not leak backend internals

Current validation command:

```bash
python3 tests/validate_static_ui.py
```
