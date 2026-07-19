# WW.CX Carrier Risk Register

| ID | Risk | Impact | Likelihood | Initial treatment | Owner | Status |
|---|---|---|---|---|---|---|
| R-001 | Applicant does not satisfy Canadian ownership/control requirements | Critical | Unknown | Obtain counsel review before filing or investment | WW.CX | Open |
| R-002 | Incorrect CLEC classification creates rework or non-compliance | High | Medium | Confirm Type IV/III/I model against final architecture | WW.CX + counsel | Open |
| R-003 | Public service begins before required CRTC completion | Critical | Low | Enforce launch gates and documented authorization | WW.CX | Controlled |
| R-004 | No qualified underlying LEC supports chosen exchanges | High | Medium | Survey multiple partners before committing territory | WW.CX | Open |
| R-005 | Edge1 is a single point of failure | Critical | High | Build a second failure-isolated signalling and call-control path | WW.CX | Open |
| R-006 | 9-1-1 location is missing, stale, or mismatched | Critical | Medium | Validated address workflow, synchronization, exception monitoring, and testing | Shared | Open |
| R-007 | Porting failure causes loss of customer service | High | Medium | Formal LNP workflow, cutover testing, rollback, and escalation | Shared | Open |
| R-008 | Unauthorized caller ID receives high STIR/SHAKEN attestation | High | Medium | Verify identity and number authorization; audit signing policy | WW.CX | Open |
| R-009 | SIP exposure enables toll fraud or denial of service | Critical | High | SBC controls, allowlists, limits, monitoring, and destination policy | WW.CX | In progress |
| R-010 | TLS certificate expiry disrupts interconnection | High | Medium | Automated renewal, independent expiry alerts, replacement runbook | WW.CX | Planned |
| R-011 | Wholesale partner failure strands numbers or customers | Critical | Medium | Migration rights, data export, continuity clauses, alternate supplier plan | WW.CX | Open |
| R-012 | Billing records cannot be reconciled | High | Medium | Immutable CDRs, versioned rates, partner reconciliation, audit tests | WW.CX | Open |
| R-013 | International routing occurs without appropriate BITS authority | High | Medium | Complete applicability assessment before international carriage | WW.CX + counsel | Open |
| R-014 | Customer agreement understates VoIP and emergency limitations | High | Medium | Counsel review, explicit disclosure, retained acknowledgement | WW.CX | Open |
| R-015 | Major outage is not reported within applicable process | High | Medium | Prebuilt assessment matrix, contacts, templates, and exercises | WW.CX | Open |
| R-016 | Cross-border processing is undisclosed or uncontrolled | High | Medium | Data-flow mapping, vendor review, privacy disclosure, contractual controls | WW.CX | Open |
| R-017 | Experimental PBX changes disrupt existing service | High | Medium | Separate staging, change approval, backup, rollback, and protected production | WW.CX | In progress |
| R-018 | Regulatory sources or model tariffs become outdated | Medium | High | Scheduled primary-source review and dated references | Regulatory owner | Open |

## Review rules

- Review monthly until commercial launch and quarterly afterward.
- Critical risks require a named treatment owner and target date.
- Launch is prohibited while any critical public-safety or authorization risk is unmitigated.
- Link each closed risk to retained evidence rather than relying on a narrative assertion.