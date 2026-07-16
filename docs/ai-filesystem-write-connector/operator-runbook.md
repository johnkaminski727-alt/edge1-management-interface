# Operator Runbook: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Purpose

This runbook describes the intended operator workflow for AI-assisted
filesystem changes on Edge1.

## Golden Rule

The model may stage proposals. The operator approves. The root-owned apply
processor writes. No single AI tool call may stage, approve, and apply a live
filesystem change.

## Normal Workflow

1. Receive a proposed change from Codex, ChatGPT, or the private model.
2. Stage the proposed file content through the connector.
3. Inspect staging metadata.
4. Review the generated diff.
5. Confirm target path is expected and within the allowlist.
6. Confirm no secrets are introduced.
7. Approve the stage as root/operator.
8. Request or trigger apply.
9. Verify connector status and audit events.
10. Run any project-specific tests.
11. Commit repository changes when the target is a git-backed project.

## Example Future Commands

Please run this on Edge1:

```bash
sudo /usr/local/sbin/bigbird-fsctl inspect <stage_id>
sudo /usr/local/sbin/bigbird-fsctl diff <stage_id>
sudo /usr/local/sbin/bigbird-fsctl approve --by John <stage_id>
sudo /usr/local/sbin/bigbird-fsctl apply <stage_id>
sudo /usr/local/sbin/bigbird-fsctl status <stage_id>
```

## Repository Documentation Install

Please run this on Edge1 after copying this documentation package to `/tmp`:

```bash
cd /opt/edge1-management-interface
mkdir -p docs
cp -a /tmp/Edge1_AI_Filesystem_Write_Connector_Docs_2026-07-16/docs/ai-filesystem-write-connector docs/
git status --short
git add docs/ai-filesystem-write-connector
git commit -m "Document AI filesystem write connector"
```

## Private Library Import

The consolidated import document is:

```text
library-import/edge1-ai-filesystem-write-connector-library-import-20260716.md
```

After staging through the Edge1 import bridge, approval remains a root/operator
action. ChatGPT or Codex may request commit only after approval exists.

## Stop Conditions

Stop before approval if:

- The target path is surprising.
- The diff contains secrets, credentials, private keys, or unrelated changes.
- The stage attempts to write outside the allowlist.
- The proposed file type is not explicitly allowed.
- The connector reports a hash mismatch.
- Audit logging fails.
- Backup creation fails.
- Post-apply verification fails.

## Post-Apply Checks

For `/opt/edge1-management-interface` documentation changes:

```bash
cd /opt/edge1-management-interface
git status --short
find docs/ai-filesystem-write-connector -type f | sort
git diff --cached --stat
```
