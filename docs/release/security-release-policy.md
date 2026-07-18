# Security Release Policy

Status: Controlled document
Applies to: Edge1 Management Interface source releases

## Security gates

A release candidate is blocked until all of the following hold:

1. No credentials, tokens, private keys, WireGuard material, session data,
   recovery codes, or production records in the archive (repository
   boundary check; see `SECURITY.md` and the README boundary statement).
2. Repository validation (CI `validate.yml`) is green on the release SHA.
3. Any security-sensitive change since the previous release (auth, route
   exposure, filesystem-connector boundaries, network filtering) has a
   named reviewer recorded in the release record.
4. Secret-scanning results for the repository have been reviewed and any
   findings dispositioned.

## Dependencies and SBOM

This project is deliberately dependency-free at runtime (system Python,
no third-party packages). Therefore:

- If a release remains dependency-free, record "no third-party runtime
  dependencies" in the release record; no SBOM is required.
- If a release ever introduces deployable third-party dependencies, attach
  an SBOM (SPDX or CycloneDX) and review licenses and known-vulnerability
  status before adoption.

## Vulnerability response in releases

Vulnerabilities reported per `SECURITY.md` that affect a published release
are assessed against `rollback-procedure.md`: exposure of private data or
an exploitable artifact defect triggers withdrawal; lesser issues are fixed
in a superseding release and noted in its release notes.
