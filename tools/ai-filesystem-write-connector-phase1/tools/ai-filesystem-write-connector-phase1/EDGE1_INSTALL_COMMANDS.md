# Edge1 Phase 1 Install Commands

Package: `Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip`

## Please Run This On Windows PowerShell

From the folder containing the zip:

```powershell
Get-FileHash .\Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip -Algorithm SHA256
scp .\Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip edge1:/tmp/Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip
```

## Please Run This On Edge1

```bash
cd /tmp
sha256sum /tmp/Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip
rm -rf Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16
unzip Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16.zip

cd /tmp/Edge1_AI_Filesystem_Write_Connector_Phase1_2026-07-16
sudo ./install.sh

bigbird-fsctl --help
```

## Please Run This On Edge1 To Set Git Identity

```bash
cd /opt/edge1-management-interface
git config user.name "John K"
git config user.email "wwadmin@edge1.ww.cx"
git config --get user.name
git config --get user.email
```

## Smoke Test On Edge1

```bash
cat >/tmp/bigbird-fsctl-phase1-smoke.md <<'EOF'
# Phase 1 Smoke Test

This file was staged, approved, applied, and audited through bigbird-fsctl.
EOF

sudo bigbird-fsctl stage \
  --source /tmp/bigbird-fsctl-phase1-smoke.md \
  --target /opt/edge1-management-interface/docs/phase1-smoke-test.md \
  --actor John \
  --reason "Phase 1 documentation-only smoke test"
```

Copy the returned `stage_id`, then:

```bash
sudo bigbird-fsctl inspect STAGE_ID
sudo bigbird-fsctl diff STAGE_ID
sudo bigbird-fsctl approve --by John STAGE_ID
sudo bigbird-fsctl apply STAGE_ID
sudo bigbird-fsctl status STAGE_ID
sudo bigbird-fsctl audit --limit 10

cd /opt/edge1-management-interface
git status --short
git add docs/phase1-smoke-test.md
git commit -m "Add Phase 1 filesystem connector smoke test"
git log -1 --oneline
```
