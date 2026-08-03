# WW.CX owner-operated full-fidelity passive sensor policy.
@load policy/tuning/json-logs

# Zeek writes protocol metadata in JSON. Full packet bytes are retained by
# the separate rotating PCAP service. Add site-specific analyzers below as
# the live Zeek version and installed packages are confirmed on Edge1.
redef Log::default_rotation_interval = 1hr;
