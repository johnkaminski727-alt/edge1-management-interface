# Repository Evidence Map

This map connects common engineering claims to the public evidence that can support them. It is a navigation aid, not a claim that every possible control or standard has been satisfied.

| Claim or question | Primary evidence | Corroborating evidence | Boundary |
| --- | --- | --- | --- |
| What is the project and who maintains it? | `README.md` | `CITATION.cff`, Git history | Public identity and project purpose only |
| What is implemented? | Source under `src/`, `server/`, `tools/`, and `modules/` | Tests, pull requests, project registers | Source is not proof of production deployment |
| How is a change reviewed? | GitHub pull request and commit history | `CONTRIBUTING.md` | Sensitive review material must remain private |
| What validation ran? | GitHub Actions run for the commit | `tests/`, workflow source, PR validation notes | Checks are repository-side and credential-free |
| How is Private Library Search bounded? | Search wrapper source and contracts | Static UI and service-asset validators, runbooks | No private documents, indexes, or production DBs |
| How are filesystem changes controlled? | `docs/ai-filesystem-write-connector/` | Acceptance checklists, audit schema, handoff records | Production apply and rollback remain operator-controlled |
| How are time observations produced? | `modules/time-authority/` and collector source | Baseline fixtures and `tests/validate_time_authority.py` | Measurements do not change server clocks |
| How are services deployed and reversed? | `deploy/` and `docs/handoff/` | Smoke tests and project registers | Installation and restart require operator action |
| What security boundary applies? | `SECURITY.md` | `CONTRIBUTING.md`, service validators | Never publish credentials or private operational data |
| What work was completed? | `registers/` and completion indexes | Commits, pull requests, validation results | Registers must remain sanitized and accurately scoped |
| What is planned rather than implemented? | `ROADMAP.md` | Open pull requests and issues | Roadmap items are directional, not delivery promises |
| How should the project be cited? | `CITATION.cff` | Repository URL and ORCID link | Citation metadata is not a compliance certification |

## Evidence quality checklist

For a material claim, verify:

- the cited path exists at the referenced revision;
- the evidence directly supports the wording of the claim;
- validation is reproducible or clearly identified as manual;
- observed, implemented, planned, and deployed states are not conflated;
- sensitive information is excluded or sanitized;
- corrections and superseding records remain traceable;
- the pull request states risk and rollback where applicable.

## Current automated baseline

The workflow at `.github/workflows/repository-validation.yml` validates:

- Private Library Search static UI structure and fixture shape;
- managed search-service assets and localhost guardrails;
- WW.CX Time Authority collectors, fixtures, dashboard, and local fake-server probe;
- records-governance files, cross-references, and CI command coverage;
- JSON syntax for published API contracts and fixtures.

The workflow intentionally does not contact production services, use secrets, deploy software, restart services, or inspect private Library contents.

## Maintenance

Update this map whenever an authoritative evidence location moves, a validation category is added, or a public claim gains a materially different evidence source.
