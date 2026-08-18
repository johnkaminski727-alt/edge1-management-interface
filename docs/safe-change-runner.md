# Safe change runner

`tools/safe_change_runner.py` provides the common operational sequence:

`PLAN -> BACKUP -> VALIDATE -> APPLY -> VERIFY -> ROLLBACK`

The runner does **not** accept shell commands or argv from callers. Operations must first be added to the repository-controlled `config/safe-change-operations.json`, where every phase has fixed argv and a timeout and therefore receives normal code review and CI before it can be selected by name.

The initial registry is intentionally empty. This establishes the execution/evidence framework without inventing a production mutation before a concrete reversible operation and rollback are reviewed.

By default, selecting a registered operation prints a plan only. `--execute` is required to run the forward phases. A failed PLAN/BACKUP/VALIDATE stops before APPLY. A failed APPLY stops before VERIFY. A failed VERIFY does not trigger rollback unless the committed operation explicitly opts into automatic rollback; otherwise the failure is evidence for attended review. `--rollback` runs only the committed rollback phase.

This runner is a mechanism for reviewed operations, not a generic remote shell.
