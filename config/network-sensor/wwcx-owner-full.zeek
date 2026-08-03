# WW.CX owner-operated full-fidelity passive sensor policy.
@load policy/tuning/json-logs
@load policy/frameworks/files/extract-all-files
@load policy/frameworks/files/hash-all-files

# Protocol logs are JSON, discovered files are hashed and reconstructed to the
# restricted extraction tree, and full packet bytes are retained separately by
# the rotating PCAP service.
redef Log::default_rotation_interval = 1hr;
redef FileExtract::prefix = "/var/lib/wwcx-network-sensor/extracted/";
redef FileExtract::default_limit = 536870912;
