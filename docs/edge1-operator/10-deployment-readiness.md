# Edge1 Operator Deployment Readiness

## Purpose

Track the final transition from repository implementation to an installed Edge1 operational connector.

## Completed foundation

- Architecture defined.
- Authority boundaries defined.
- Tool contract defined.
- Runtime and protocol components scaffolded.
- Bootstrap and verification workflows documented.

## Deployment requirements

Before enabling live operation:

- [ ] Edge1 host identity verified.
- [ ] Dedicated operator service account created.
- [ ] Private transport configured.
- [ ] Runtime dependencies installed.
- [ ] systemd service enabled.
- [ ] Health endpoint validated.
- [ ] Audit storage verified.
- [ ] Secret material provisioned outside Git.
- [ ] Read-only validation completed.
- [ ] Mutation capabilities enabled only after validation.

## Final connection

The remaining external step is the approved workspace/tunnel association required to connect the ChatGPT environment to the Edge1 operator service.

## Definition of readiness

The operator is ready when it can authenticate, inspect Edge1 state, execute bounded operations, record evidence, validate results, and recover safely from failed operations.