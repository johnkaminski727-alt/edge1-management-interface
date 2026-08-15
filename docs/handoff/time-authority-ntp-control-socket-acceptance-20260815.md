# WW.CX NTP chronyc control-socket acceptance — 2026-08-15

## Live observation

After the successful chronyd cutover and UDP/123 listener-check repair, Edge1 showed:

- `chrony.service` active and enabled;
- chronyd bound to `0.0.0.0:123` and `[::]:123`;
- `systemd-timesyncd.service` absent after the package transition;
- an unprivileged `wwadmin` invocation of `chronyc tracking` returned `506 Cannot talk to daemon`.

The unprivileged chronyc result does not contradict NTP service health. The reviewed chrony configuration sets `cmdport 0`, so remote UDP command/control is disabled. Operational control remains local through chronyd's Unix-domain socket and is intentionally treated as privileged administration on Edge1.

## Accepted operator practice

Use:

```sh
sudo chronyc tracking
sudo chronyc sources -v
sudo chronyc clients
```

Do not relax command-socket permissions merely to allow unprivileged chronyc inspection. The public NTP data plane on UDP/123 and the local chronyc control plane are separate surfaces and must be validated separately.

## Remaining acceptance boundary

The public NTP endpoint is not fully accepted until the persistent `inet wwcxfw input` UDP/123 rule is installed and outside-in NTP queries to the published hostname succeed.
