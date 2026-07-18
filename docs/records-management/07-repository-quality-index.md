# Repository Evidence Quality Index

## Purpose

This internal rubric helps reviewers measure whether the repository produces clear, reproducible evidence. It is a project-management aid, not a certification score or legal-compliance determination.

## Scale

Score each dimension from 0 through 4:

| Score | Meaning |
| --- | --- |
| 0 | No evidence identified |
| 1 | Ad hoc evidence exists |
| 2 | Documented control exists |
| 3 | Control is automated or repeatedly demonstrated |
| 4 | Control is automated, negatively tested, traceable, and periodically reviewed |

## Dimensions

| Dimension | Evidence to inspect |
| --- | --- |
| Provenance | Git history, source revision, responsible role, record identifiers |
| Integrity and fixity | SHA-256 manifests, object validation, correction history |
| Metadata completeness | Schema, validator, required fields, sanitized example |
| Retention and legal hold | Schedule identifier, trigger, duration, disposition, hold guard |
| Preservation events | Acting agent and role, UTC time, outcome, details |
| Restoration readiness | Restore instructions, exercise evidence, unresolved findings |
| Automation | CI execution, positive tests, negative tests, explicit failures |
| Privacy boundary | Data minimization, classifications, absence of private content |
| Documentation traceability | Evidence map, stable links, accurate PR description |
| Correction and supersession | Normal commits, linked replacements, no silent history rewrite |

## Review method

1. Select the revision and evidence period.
2. Link evidence for every non-zero score.
3. Record gaps and owners instead of inflating a score.
4. Treat a green CI run as one evidence source, not proof of production state.
5. Compare against the prior review only when scope is equivalent.
6. Publish only sanitized findings.

## Interpretation

Totals may guide project priorities but must not be labeled as external conformance, accreditation, or certification. A high score means the repository demonstrates its own stated controls well; it does not establish organization-wide or legal compliance.
