# Project Agent State

This directory stores durable project-state information for autonomous engineering workflows.

Core cross-project records:

- `current-state.md` — concise verified state index and workstream pointers;
- `backlog.md` — completed and remaining gates;
- `validation.md` — accepted validation checkpoints and remaining validation gates;
- `handoff.md` — continuation order, safety boundaries and exact resume points.

Workstream-specific state files should be preferred when a project has its own durable record. Current Communications Relay records are:

- `comms-relay.md` — private relay, ingestion, News Reader and archive state;
- `comms-relay-upstream-nntp.md` — selective Eternal September reader sources and provenance state.

Other workstreams maintain their own state files where present, including DTMF/provider-response and outbound-mail records.

Update state records only with verified facts. Preserve dated acceptance/history documents rather than rewriting them to look current. Never store credentials, secret values, raw private databases, authentication transcripts, or unredacted restricted evidence in `.agent/`.
