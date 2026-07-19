# Edge1 Operator End-to-End Wiring Checklist

## Purpose

Track final integration between the Edge1 Operator components.

## Request Path

```text
Transport
  -> Adapter
  -> Tool Registry
  -> Dispatcher
  -> Runtime Bridge
  -> Runtime Handlers
  -> Audit/Evidence
```

## Verification

- [ ] Entry point initializes transport
- [ ] Transport validates requests
- [ ] Adapter resolves operations
- [ ] Registry exposes approved tools
- [ ] Dispatcher routes handlers
- [ ] Runtime handlers return structured results
- [ ] Audit records are generated
- [ ] Service health endpoint validates startup

## Deployment

- [ ] systemd unit installed
- [ ] environment configuration loaded
- [ ] service starts on boot
- [ ] smoke test passes
