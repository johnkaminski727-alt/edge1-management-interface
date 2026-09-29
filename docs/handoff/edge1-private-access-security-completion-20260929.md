# Edge1 Private Access and Security Validation Completion Handoff

Date: 2026-09-29
Status: COMPLETE for the private authentication and security-validation phase

## Completed and accepted

- Private HTTPS access for `edge1.ww.cx` is available over WireGuard split DNS.
- Business159 assertion exchange creates an independent opaque Edge1 session.
- The authenticated Control Center is live.
- The synchronized registry-driven navigation shell is live.
- The read-only `security.validate_config` action now validates the deployed Edge1 security stack rather than depending on Suricata.
- The systemd credential-mode incompatibility that caused HTTP 503 responses is fixed and regression-covered.
- Live browser acceptance produced a successful security configuration validation result.
- Suricata is intentionally not required on the current Edge1 CPU profile because SSE4.2 is not exposed.
- Current package state was repaired after the unsuccessful Suricata installation attempt.

## Safety boundaries retained

- Browser clients never receive the Operations API HMAC secret.
- Mutation actions remain disabled.
- Navigation never grants authorization.
- The private Control Center remains separated from public ingress.
- PASS observes and correlates; ASE decides and enforces.

## Approved follow-on security work

The following are recorded as follow-on work and do not block AVA or Contacts & Relationship Management:

1. Public `edge1.ww.cx:443` decoy/redirect listener:
   - expose no Edge1 application or authentication routes;
   - record sanitized access observations privately;
   - redirect ordinary browser traffic to the public WW.CX/store destination;
   - feed suspicious patterns into PASS for correlation and possible ASE sanctions.

2. Authenticated specialist-page routing:
   - move currently accepted read-only subpages behind the Edge1 authenticated namespace before declaring their browser links live;
   - do not expose the full `/edge1-status/` static tree without an Edge1 session boundary.

3. Persistent browser marker for repeated malicious activity:
   - future-proof correlation signal only, never a sole enforcement identity;
   - set only after sustained malicious activity across a multi-day rolling window;
   - threshold and rolling-window values remain intentionally TBD until the PASS/ASE scoring policy is finalized;
   - use an opaque, integrity-protected token with no sensitive data;
   - Secure, HttpOnly and appropriate SameSite attributes;
   - clearing or blocking the cookie must not defeat IP/network/fingerprint/event correlation;
   - cookie observations feed PASS; enforcement remains an ASE decision.

4. Automatic ASE queue consumption remains a separate activation item. Manual enforcement capability is not equivalent to fully automatic sanctions.

## Resume point

Security/private-access work may now be treated as a completed prerequisite. Primary project focus can return to:

- AVA;
- Contacts & Relationship Management;
- unified Control Center integration for those modules.
