# Edge1 network sensor validation regression — 2026-08-03

## Incident

The guarded live installer stopped before mutation because `tools/networking/validate-edge1-network-sensor.sh` scanned the entire repository for forbidden traffic-control command strings. It found the literal test string `iptables -F` inside `tests/validate_edge1_network_sensor.py` and incorrectly treated validator source as deployment code.

## Correction

The forbidden-command scan is limited to the network-sensor runtime and deployment assets that could execute or install behavior. Test, documentation, and validator source files are not treated as runtime control paths.

The repository validation entrypoint now executes the operator-facing shell validator, ensuring CI exercises the same validation path used by the live installer.

## Live impact

No sensor service, timer, configuration, capture directory, or traffic control was created or changed. The installer failed during pre-mutation repository validation.
