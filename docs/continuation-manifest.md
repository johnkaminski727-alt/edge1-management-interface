# Machine-readable continuation manifest

The repository stores `config/continuation-manifest.json` as the sanitized continuation declaration for WW.CX / Edge1 / Project Big Bird.

The Edge1 repository head uses the sentinel `SELF`. This avoids the impossible self-reference of embedding the SHA of the commit that contains the manifest. Run:

```bash
python3 tools/continuation_manifest.py --output /tmp/edge1-continuation.json
```

The generator resolves `SELF` to the checkout's exact Git `HEAD` and adds a UTC generation timestamp. Unknown live values remain null/unverified; the generator never promotes historical evidence into live state.

When a sanitized live discovery snapshot is available, compare it without mutation:

```bash
python3 tools/continuation_drift.py /tmp/edge1-continuation.json /path/to/live-snapshot.json --repo /opt/edge1-management-interface
```

The report uses only these classifications: `MATCH`, `DRIFT`, `UNKNOWN`, `NOT DEPLOYED`, and `LIVE NEWER THAN REPOSITORY`. It never overwrites drift.

A future live collector should provide at minimum `edge1_checkout_head`, `bigbird_version`, `operator_service`, and `operations_api_service`. Missing values intentionally classify as `UNKNOWN`.
