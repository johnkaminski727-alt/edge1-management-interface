# Big Bird camera first-frame probe

Status: repository-ready; live BAZZ validation not yet performed.

`server/bigbird_camera_first_frame.py` is a one-shot, model-neutral capture utility for the Project Big Bird FIRST FRAME milestone. It adds no listener or daemon and is intended to remain dormant until a camera is explicitly configured on Edge1.

## Safety boundary

- Camera endpoint candidates must be explicitly configured; the tool does not scan arbitrary networks.
- Credentials must not be embedded in URIs.
- Optional credential files are restricted to `/etc/bigbird-camera/` and are never printed into evidence.
- Output evidence records only the redacted source URI, transport, byte size, UTC timestamp, and SHA-256 of the verified image payload.
- This repository increment does not claim that the owned BAZZ camera has been identified or that real camera pixels have been captured.

## Supported one-shot transports

The probe follows Project Big Bird first-frame priority for the transports it can safely exercise without a persistent media service: RTSP, MJPEG, HTTP snapshot, then HLS. ONVIF discovery, WebRTC, proprietary protocols, live relay, AI inference, event memory, and camera control remain separate milestones.

## Example local config shape

The production config belongs outside Git under `/etc/bigbird-camera/cameras.json` with restrictive permissions. Do not commit real addresses or credentials.

```json
{
  "cameras": [
    {
      "id": "bazz-primary",
      "enabled": true,
      "candidates": [
        {"transport": "rtsp", "uri": "rtsp://CAMERA_HOST/STREAM_PATH"},
        {"transport": "http_snapshot", "uri": "http://CAMERA_HOST/SNAPSHOT_PATH"}
      ]
    }
  ]
}
```

Run manually only after the physical BAZZ model and local endpoint are verified:

```sh
python3 server/bigbird_camera_first_frame.py --camera bazz-primary
```

A successful result is a milestone artifact, not full camera acceptance. Project completion still requires actual BAZZ live video through WW.CX, AI/event validation, persistence, and recovery.
