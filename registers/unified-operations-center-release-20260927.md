# Unified Operations Center release register — 2026-09-27

**State:** Implemented; browser-accepted; source merged; local `main` and accepted runtime frontend verified identical. Documentation closeout is maintained in `docs/operations/unified-operations-center-runbook-20260927.md`.

| Gate | Evidence and disposition |
| --- | --- |
| Navigation | Four deployed modules `accepted_live`; undeployed routes hidden from active menu; shared shell across four pages |
| Browser acceptance | Operator confirmed all six checks, including CrowdSec cards, Security Correlation event feed and Network Defense rendering |
| Data and services | Core snapshot showed 11/11 monitored services active at the observed check; private web and all four observation timers active in final parity audit |
| Frontend parity | 10/10 source assets matched deployed files byte-for-byte; all four routes returned HTTP 200 |
| Source provenance | PR #592 squash-merged into `main` as `9109606740f5e225ebba6301158ddc7658be391e`; local `main` synchronized and working tree clean |
| Release staging | 22 reviewed source files; collector AST and nine systemd definition validations passed; targeted credential-pattern scan had no matches (not exhaustive) |
| Rollback | Ten-asset publisher creates timestamped prepublication copies, manifest and rollback script; earlier runtime backup directories separately retained |
| Security boundary | Localhost-only port 8098; no production traffic changes, public listener expansion, IDS installation or DNS policy enforcement from this release |

**Important limits:** HTTP 200 and active timers do not prove browser rendering or snapshot freshness; browser acceptance was independently confirmed. Existing legacy Suricata/other historical feeds are not accepted as live. Correlation was not proven across separate sources. Network Defense was limited (five of eleven observed components during acceptance), and Bitcoin/Mining remain disabled in the live navigation. A deploy or rollback rehearsal of the new ten-file publisher has **not** been documented as executed; its source preflight and unit validation passed.

**Repository:** `johnkaminski727-alt/edge1-management-interface` · **PR:** https://github.com/johnkaminski727-alt/edge1-management-interface/pull/592

**Prior recovery:** `/var/backups/edge1-git-sync-191-20260927T050643Z` preserves the 13 exact-match files moved before local `main` synchronization. Earlier original dashboard backups are distinct. Do not publish backup paths or runtime evidence with sensitive content.

**Follow-up:** CI fixture testing for the publisher and its rollback, explicit freshness/availability UX, and independent staged-module acceptance. None is required to keep the existing read-only frontend running; they are readiness gates for future deployment phases.
