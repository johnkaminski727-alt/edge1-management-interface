# Edge1 Git Identity

Use repo-level configuration first so unrelated repositories are not affected.

Please run this on Edge1:

```bash
cd /opt/edge1-management-interface
git config user.name "John K"
git config user.email "wwadmin@edge1.ww.cx"
git config --get user.name
git config --get user.email
```

If you prefer a different email address, replace `wwadmin@edge1.ww.cx` before
running the command.

The previous documentation commit used the automatically inferred identity:

```text
John K <wwadmin@edge1.ww.cx>
```

That is acceptable operationally, but setting it explicitly removes the warning
on future commits.
