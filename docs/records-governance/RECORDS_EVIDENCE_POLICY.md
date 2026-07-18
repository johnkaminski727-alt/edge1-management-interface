# Records and Evidence Policy

## Status and purpose

This is a project-defined control for the Edge1 Management Interface repository. It establishes how engineering claims are supported by durable, reviewable evidence. It does not claim certification or conformance with a statute, regulator, or external records-management standard.

The policy is designed to make the repository demonstrably well documented: assertions should be traceable to source, review, validation, operational, and correction records.

## Scope

This policy applies to public, non-sensitive engineering records maintained in this repository, including:

- source code and configuration templates;
- architecture decisions and design documentation;
- pull requests, reviews, commits, and releases;
- validation scripts and automated check results;
- sanitized project, handoff, deployment, and completion registers;
- security, contribution, citation, and roadmap documentation.

Private Library contents, credentials, personal information, production databases, search indexes, secrets, and unredacted operational diagnostics remain outside this public evidence set.

## Evidence principles

1. **Traceability:** a material claim should point to the source, decision, test, register, or review that supports it.
2. **Provenance:** records should identify their repository path and inherit author, timestamp, and revision history from Git.
3. **Reproducibility:** validation evidence should name an executable command or a clearly described manual inspection.
4. **Reviewability:** changes should be small enough to inspect and should state purpose, risk, validation, and rollback.
5. **Integrity:** corrections should use normal commits or explicit superseding records. Shared history must not be silently rewritten.
6. **Data minimization:** public evidence must prove the work without publishing sensitive operational content.
7. **Bounded claims:** documentation should distinguish implemented behavior, observed results, plans, and non-goals.

## Minimum record metadata

Material engineering records should contain or inherit the following information when applicable:

- title or stable identifier;
- creation or observation date;
- responsible author, operator, or automated actor;
- source or affected component;
- summary of the change, decision, or observation;
- validation method and result;
- security and privacy impact;
- deployment and rollback information;
- classification or publication boundary;
- links to related commits, pull requests, decisions, tests, or registers.

Git metadata may satisfy author, timestamp, and revision-history fields. Pull-request descriptions may satisfy change, review, risk, validation, and rollback fields.

## Record classes and authoritative locations

| Record class | Authoritative public location |
| --- | --- |
| Source and sanitized configuration | Version-controlled repository paths |
| Change and review history | Git commits and GitHub pull requests |
| Automated validation results | GitHub Actions runs for the associated commit |
| Architecture decisions | `docs/` decision and architecture records |
| Operational guidance | `docs/handoff/`, runbooks, and approved deployment assets |
| Project and completion registers | `registers/` and indexed completion documentation |
| Security and disclosure guidance | `SECURITY.md` |
| Contribution expectations | `CONTRIBUTING.md` |
| Citation metadata | `CITATION.cff` |
| Directional plans | `ROADMAP.md` |

The detailed crosswalk is maintained in [EVIDENCE_MAP.md](EVIDENCE_MAP.md).

## Lifecycle

### Create

Use a focused branch and create the smallest coherent evidence set that accurately describes the work. Use synthetic or sanitized examples.

### Review

Confirm internal consistency, referenced-path existence, privacy boundaries, validation commands, and rollback guidance. Material changes should be reviewed through a pull request.

### Validate

Run the repository baseline:

```bash
python3 tests/validate_static_ui.py
python3 tests/validate_search_service_assets.py
python3 tests/validate_time_authority.py
python3 tests/validate_records_evidence.py
```

GitHub Actions repeats these checks for pull requests and changes to `main`.

### Publish

Merge through normal Git history. Publication means inclusion in the public repository; it does not authorize publication of private operational records.

### Correct or supersede

Correct errors with a new commit. When a historical record must remain understandable, mark it as superseded and link to its replacement. Do not erase evidence merely because a conclusion changed.

### Retain and review

Retain repository evidence with project history. Review this policy and its evidence map when record classes, validation commands, public boundaries, or repository structure materially change.

## Integrity and security controls

- The CI workflow uses read-only repository permissions.
- Validation must not require production credentials or unrestricted network access.
- Generated evidence must not contain secrets or unredacted private data.
- Production service changes remain operator-controlled and outside CI.
- Force-pushes and silent history rewrites are not acceptable evidence-maintenance practices.
- Failed checks are evidence of an unresolved state and must not be represented as a successful validation.

## Evidence limitations

Repository evidence demonstrates what was committed, reviewed, and validated within its stated scope. It does not by itself prove production deployment, continued runtime health, legal compliance, or third-party certification. Those claims require separate, appropriately controlled operational or external evidence.
