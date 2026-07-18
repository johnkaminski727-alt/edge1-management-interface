# Release Engineering

## Purpose

The release workflow creates a reviewable, reproducible source bundle without deploying to production or publishing a GitHub Release automatically.

It runs in either of two ways:

- manually through **Actions → Build release artifacts → Run workflow**;
- automatically when a tag beginning with `v` is pushed.

## Output

Each run produces one retained GitHub Actions artifact containing:

- a source archive generated from the exact commit under test;
- `SHA256SUMS` for integrity verification;
- `release-manifest.json` recording the project, release label, commit SHA, repository, workflow run, archive name, and checksum file.

The source archive uses `git archive`, excludes untracked material and repository history, and is compressed with deterministic gzip metadata. Its timestamp is normalized to the source commit time.

## Release procedure

1. Confirm the repository validation workflow passes on `main`.
2. Choose a semantic version such as `v0.4.0`.
3. Review changes since the previous tag and update the changelog or release notes.
4. Create and push an annotated tag from the intended commit.
5. Confirm the release workflow completes successfully.
6. Download the artifact and verify it with `sha256sum -c SHA256SUMS`.
7. Review `release-manifest.json` and retain it with the release evidence.
8. Publish or deploy only through a separately approved procedure.

## Manual candidate builds

A manual workflow run may use a label such as `rc-2026-07-18`. Candidate builds are useful for testing packaging before a permanent version tag is created. A manual run does not create a tag, GitHub Release, or deployment.

## Security and control boundaries

- Workflow permissions are read-only for repository contents.
- The workflow does not use deployment credentials.
- The workflow does not modify branches, tags, releases, environments, or servers.
- Publishing and deployment remain explicit operator decisions.
- Release evidence should be preserved with the records-management package when a release is adopted.

## Verification example

```sh
tar -xzf edge1-management-interface-v0.4.0.tar.gz
sha256sum -c SHA256SUMS
python3 -m json.tool release-manifest.json
```

Run checksum verification from the directory containing both the archive and `SHA256SUMS`.
