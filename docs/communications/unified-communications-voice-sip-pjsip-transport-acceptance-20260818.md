# Unified Communications — Voice/SIP PJSIP Transport Repair Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Scope: bounded local Asterisk/FreePBX transport repair and post-restart acceptance

## Result

PASS.

The previously confirmed Asterisk PJSIP transport defect is repaired in the live Edge1 runtime. FreePBX now owns the authoritative transport source and generates one UDP transport bound only to loopback:

- transport id: `127.0.0.1-udp`;
- protocol: UDP;
- bind: `127.0.0.1:5061`;
- `allow_reload=false`;
- live PJSIP registry objects: `1`.

Kamailio retains SIP ownership of TCP/UDP `5060`. Asterisk does not own `5060`.

## Authoritative live evidence

Operator evidence directory:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z`

Rollback retained at:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z/rollback.sh`

Pre-change backup retained at:

`/var/backups/wwcx-asterisk-pjsip-transport-20260818T172956Z`

Final acceptance artifact:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z/ACCEPTANCE.txt`

SHA-256:

`35d80adc1f0f734343dd5efe4a977aafcb3bf1b713b0cdb2aaeb59950be52852`

## Root cause and repair

The old configuration defined the same transport object twice:

- FreePBX-generated `pjsip.transports.conf` defined `[0.0.0.0-udp]` at `0.0.0.0:5060`;
- `pjsip.transports_custom.conf` defined the same object name at `127.0.0.1:5061`.

Asterisk rejected the duplicate transport object and the PJSIP transport registry was empty even though a loopback UDP listener remained present.

Phase 24 established that the authoritative FreePBX BMO source was `chan_pjsip` with the active bind stored in `kvstore_Sipsettings` as UDP `0.0.0.0:5060`.

Phase 25 changed the supported FreePBX BMO source to UDP `127.0.0.1:5061`, retired the duplicate custom transport object by leaving its custom file empty, regenerated configuration through `fwconsole`, and restarted through the installed FreePBX lifecycle controller.

No generated Asterisk file was edited directly.

## Generated and BMO state

Accepted generated transport:

```text
[127.0.0.1-udp]
type=transport
protocol=udp
bind=127.0.0.1:5061
allow_reload=no
```

Accepted FreePBX BMO state:

```text
binds={"udp":{"127.0.0.1":"on"}}
udpport-127.0.0.1='5061'
```

The historical inactive `udpport-0.0.0.0='5060'` value remains stored but is not active because `binds` selects only `127.0.0.1`.

Accepted file hashes after repair:

```text
25071e24453cf4304474d68bb8eab65749752bb637c388d88ff29dd0b38a20e0  /etc/asterisk/pjsip.transports.conf
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /etc/asterisk/pjsip.transports_custom.conf
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /etc/asterisk/pjsip.transports_custom_post.conf
```

## Reload/restart interpretation

The pre-restart `fwconsole reload` produced a transient `Address already in use` error for `127.0.0.1:5061` while the old Asterisk process still owned that socket. This was not the final repaired runtime.

After the controlled FreePBX/Asterisk restart, the new Asterisk process loaded the intended transport successfully. Post-restart evidence showed:

- UDP/IPv4 reported as an available SIP transport;
- one live PJSIP transport object at `127.0.0.1:5061`;
- no post-restart duplicate-object, bind, or address-in-use transport errors.

## Listener ownership

Accepted listener state:

- Kamailio retains public and loopback TCP/UDP `5060`;
- Asterisk PJSIP owns only loopback UDP `127.0.0.1:5061`;
- Asterisk does not own SIP `5060`.

Asterisk HTTP also reconciled to its generated FreePBX configuration after restart:

- HTTP `127.0.0.1:8088`;
- HTTPS `127.0.0.1:8089`.

This is a narrowing from the previously observed stale wildcard `8089` listener and matches `http_additional.conf` (`tlsbindaddr=127.0.0.1:8089`). No firewall change was required.

## Health and safety gates

Final acceptance confirmed:

- Asterisk `22.10.1` healthy;
- zero active channels;
- zero active calls;
- Kamailio active;
- telephony analytics active;
- telephony console active;
- Messaging Gateway active;
- PostgreSQL active;
- rollback present and executable;
- no production SIP probe generated;
- no call originated;
- no carrier, trunk, dialplan, emergency-routing, firewall, DNS, certificate, or credential change.

## Readiness interpretation

This closes the local Asterisk PJSIP duplicate-transport defect and establishes a healthy local PJSIP transport runtime.

It does **not** establish current end-to-end carrier/interconnect health. The existing readiness matrix should continue to treat `voice_sip.edge1_runtime` as `unknown` for operational peer/interconnect health until fresh non-stale evidence is available. The earlier `degraded` analytics classification was derived from a stored July 20 snapshot rather than a fresh peer probe.

`voice_sip.live_acceptance = runtime_ready` remains valid for the bounded read-only surface.

No production call origination or carrier traffic is authorized by this acceptance.