# Edge1 passive network sensor

## Objective

Observe the complete mirrored business-network link on Edge1 without making Edge1 the gateway. The active `owner-full` profile retains rotating full-packet PCAP and unrestricted recent Suricata/Zeek event samples in a root-only snapshot. A separate dashboard snapshot contains aggregate counts only.

## Capture and observability architecture

A managed-switch SPAN/mirror destination or hardware TAP connects to a dedicated Edge1 NIC with no IP address. The package runs:

- a separate Suricata process using the installed `/etc/suricata/suricata.yaml`, a dedicated PID, disabled command socket, and dedicated log directory;
- a rotating `tcpdump` full-PCAP recorder with snap length zero;
- optional Zeek live metadata in JSON;
- a one-minute exporter producing restricted and dashboard snapshots;
- an optional-source Security Correlation layer that imports minimized IDS, DNS, and network events when the restricted sensor snapshot exists;
- a final Network Defense layer that exposes the passive sensor as a first-class observed component;
- daily age and capacity retention enforcement.

The correlation and Network Defense extensions are absent-neutral. Before the sensor snapshot exists, existing source counts and component behavior remain unchanged. Raw packet payloads and raw Suricata/Zeek objects are not copied into Security Correlation or Network Defense.

The package does not enable IP forwarding, add routes, alter nftables, change DNS, or make Edge1 inline. TLS payloads remain encrypted in PCAP unless endpoint/session keys or a separately configured interception system are introduced.

## Default retention

- full PCAP: 7 days and a 250 GiB hard capacity ceiling;
- extracted files: 14 days;
- metadata policy target: 90 days;
- restricted latest snapshot: `/var/lib/wwcx-network-sensor/restricted/latest.json`;
- dashboard snapshot: `/var/www/edge1-status/network-sensor/data/network-sensor.json`.

Adjust `/etc/default/wwcx-network-sensor` after measuring traffic volume and disk capacity.

## Read-only discovery

```bash
cd /opt/edge1-management-interface
sudo bash tools/networking/discover-edge1-network-sensor.sh /var/lib/wwcx-deployment-evidence/network-sensor-discovery/$(date -u +%Y%m%dT%H%M%SZ)
```

## Installation

First configure the switch/router mirror destination to a dedicated Edge1 NIC. Verify that NIC has no assigned address, then:

```bash
cd /opt/edge1-management-interface
git switch main
git pull --ff-only origin main
sudo bash deploy/install-edge1-network-sensor.sh \
  --interface <mirror-interface> \
  --install-packages \
  --activate
```

To enable Zeek after installing it:

```bash
sudo bash deploy/install-edge1-network-sensor.sh \
  --interface <mirror-interface> \
  --enable-zeek \
  --activate
```

Without `--activate`, files and units are staged but no sensor service or timer is enabled or started.

## Acceptance

```bash
systemctl is-active wwcx-network-sensor-suricata.service
systemctl is-active wwcx-network-sensor-pcap.service
systemctl is-active wwcx-network-sensor-exporter.timer
systemctl show wwcx-security-correlation.service -p Result -p ExecMainStatus
systemctl show wwcx-network-defense.service -p Result -p ExecMainStatus
sudo tcpdump -ni <mirror-interface> -c 20
sudo ls -lh /var/lib/wwcx-network-sensor/pcap
sudo jq . /var/lib/wwcx-network-sensor/restricted/latest.json
curl -fsS http://127.0.0.1/edge1-status/network-sensor/data/network-sensor.json | jq .
curl -fsS http://127.0.0.1/edge1-status/security/correlation/data/security-correlation.json | jq '.summary,.network_sensor_context'
curl -fsS http://127.0.0.1/edge1-status/network-defense/data/network-defense.json | jq '.components.network_sensor,.correlation_context'
```

Expected integrated state after mirrored traffic is present:

- Security Correlation `source_status.network_sensor.available` is `true`;
- `summary.network_sensor_event_count` is greater than zero;
- `network_sensor_context.restricted_payloads_copied` is `false`;
- Network Defense `components.network_sensor.state` is `observed`;
- Network Defense continues to report `traffic_controls_changed: false`.

Traffic is network-wide only if the switch/TAP actually mirrors both ingress and egress for the desired WAN/LAN ports or VLANs. Edge1 cannot manufacture visibility for packets that never reach the sensor NIC.
