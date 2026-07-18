# Release Acceptance Checklist

Use this checklist for every tagged or manually approved release candidate.

## Preparation

- [ ] Release scope and target version are documented.
- [ ] The selected commit SHA is recorded.
- [ ] The working branch is protected from unreviewed changes.
- [ ] Required tests, linters, and repository validation complete successfully.
- [ ] Known limitations and deferred issues are documented.

## Security and compliance

- [ ] No credentials, tokens, private keys, production data, or personal information are included.
- [ ] Dependency and secret-scanning results have been reviewed.
- [ ] Security-sensitive changes have an identified reviewer.
- [ ] Third-party license obligations are understood.
- [ ] An SBOM is attached when the release contains deployable dependencies.

## Artifact verification

- [ ] The source archive was generated from the recorded commit.
- [ ] SHA-256 checksums were generated and independently verified.
- [ ] The release manifest names every distributed artifact.
- [ ] A second build reproduces the expected archive contents or differences are explained.
- [ ] Provenance records identify