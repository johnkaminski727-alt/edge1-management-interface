# Validation Checklists

## Repository

- expected branch confirmed;
- working tree understood;
- changed files reviewed;
- targeted tests pass;
- broader tests pass where warranted;
- commit created;
- remote push confirmed;
- final working tree clean or intentionally documented.

## Shell and deployment

- `sh -n` or equivalent passes;
- installer is idempotent;
- service user and directories are provisioned;
- source and runtime ownership are separated;
- systemd unit installs and reloads;
- service is enabled and active;
- fresh logs contain no traceback or repeated restart loop;
- listener and health endpoint match the documented design.

## Python

- all changed modules compile;
- imports work through the production module path;
- targeted tests pass;
- entrypoint startup is exercised without hanging CI indefinitely.

## Documentation

- commands match actual paths and service names;
- current state reflects verified evidence;
- rollback and ownership notes are included when operationally relevant;
- no secrets or private data are recorded.
