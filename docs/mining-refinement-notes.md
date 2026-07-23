# Mining refinement notes

This document records the managed CPU-mining refinements introduced after the initial live deployment.

- Use `ConditionFileIsExecutable=` for compatibility with Edge1 systemd.
- Persist one sanitized telemetry sample per collector run in JSON Lines format.
- Retain a bounded seven-day history at one-minute cadence.
- Keep private keys, seed material, pool credentials, and payout addresses out of telemetry.
