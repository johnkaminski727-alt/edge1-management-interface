# Edge1 Private Access & Security Completion Register — 2026-09-29

| Item | State | Evidence / boundary |
| --- | --- | --- |
| WireGuard private HTTPS access | COMPLETE | Split-DNS private access accepted on Windows and iPhone |
| Business159 authentication handoff | COMPLETE | Assertion exchange and independent Edge1 session accepted |
| Edge1 session/CSRF boundary | COMPLETE | Authenticated session, logout and validation path operational |
| Read-only security validation | COMPLETE | Comprehensive Edge1 stack check succeeds; no Suricata dependency |
| Operations API credential bridge | COMPLETE | Systemd credential mode fixed; browser HMAC secret remains server-side |
| Control Center shell | COMPLETE | Authenticated synchronized shell live |
| Specialist module authenticated ingress | IMPLEMENTATION READY | PR #624 routes accepted pages through /edge1-ops/status/; live acceptance still required |
| Unified Contacts-style theme | IMPLEMENTATION READY | Shared shell/theme plus Control Center/specialist source updates in PR #624 |
| Contacts & Relationships | ACTIVE | Continue current relationship/correlation and authenticated browser integration |
| AVA | ACTIVE | Continue Ava Office / operator integration; external execution gates remain unchanged |
| Public edge1.ww.cx redirect/logger | APPROVED FOLLOW-ON | Minimal public listener only; no private app/auth routes; ordinary browser redirect to WW.CX/store; PASS observation |
| Multi-day malicious-activity browser marker | APPROVED DESIGN FOLLOW-ON | Opaque integrity-protected cookie after sustained malicious activity; correlation signal only, not sole identity/enforcement |
| ASE automatic queue consumption | OPEN | Manual enforcement capability exists; automatic live consumption remains separate activation |

## Persistent marker requirements

The future browser marker must:

- be set only after a defined malicious-activity threshold across a rolling multi-day window;
- carry no sensitive information;
- use an opaque integrity-protected value;
- use Secure and HttpOnly and an appropriate SameSite policy;
- be one PASS correlation feature among multiple observations;
- never substitute for authentication, identity proof, or an ASE decision;
- remain useful if IP addresses change, while cookie absence/clearing must not erase server-side history;
- have explicit retention, expiry, rotation and false-positive review policy before activation.

Threshold values and retention duration remain intentionally uncommitted until the PASS/ASE scoring policy is finalized.

## Project transition

The private-access/security prerequisite is complete. Primary implementation focus returns to AVA and Contacts & Relationship Management, including their unified authenticated Control Center navigation and visual integration.
