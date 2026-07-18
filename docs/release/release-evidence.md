# Release Evidence Package

Status: Controlled document
Applies to: Edge1 Management Interface source releases

## Requirement

Every adopted release keeps a durable evidence record, named
`edge1-management-interface-<version>-release-record`, stored outside the
source tree or in an approved records repository (see the records
retention schedule in `docs/records-management/`).

## Required contents

| Item | Evidence |
| --- | --- |
| Source identity | Tag name, commit SHA, branch |
| Validation | CI run URL or captured output of the validation suite |
| Artifact identity | Archive filename(s) and SHA-256 checksums |
| Reproducibility | Second-build comparison result or explained differences |
| Approvals | Who approved the release and when |
| Checklist | Completed copy of `release-checklist.md` |
| Communications | Release notes as published |
| Exceptions | Any waived control, with rationale and approver |

## Record template

```text
release: edge1-management-interface-<version>
date: YYYY-MM-DD
commit: <sha>
tag: <tag>
validation: <CI run URL or local log reference>
artifacts:
  - name: <archive>
    sha256: <checksum>
reproducibility: <verified | differences explained: ...>
approved_by: <name>
exceptions: <none | list>
notes: <free text>
```

A release without this record is not an adopted release, regardless of
whether an archive exists.
