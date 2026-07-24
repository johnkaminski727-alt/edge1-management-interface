# WW.CX Edge1 Operations Center Recovery

## Restore Source

Repository:

/opt/edge1-management-interface

## Restore Web Portal

Run:

deploy/operations-center/publish.sh

## Restore Systemd Units

Copy:

deploy/systemd/*.service
deploy/systemd/*.timer

Reload:

systemctl daemon-reload

Enable required timers.

## Validation

Confirm:

- JSON artifacts exist
- Apache route works
- timers active
- repository clean
