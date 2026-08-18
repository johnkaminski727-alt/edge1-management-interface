# Big Bird camera first-frame probe

Status: repository-ready; the owned physical BAZZ camera model is verified as WFCAMOUT, but network discovery and a visually verified real frame remain pending.

`server/bigbird_camera_first_frame.py` is a one-shot, model-neutral capture utility for the Project Big Bird FIRST FRAME milestone. It adds no listener or daemon and is intended to remain dormant until a camera is explicitly configured on Edge1.

## Acceptance boundary

Receiving an image-like payload is not, by itself, FIRST FRAME acceptance. The probe records a candidate frame as `pending_visual_verification`; it does not mark `live_camera_pixels_verified` true. M3 is reached only after the captured artifact is visually inspected and confirmed to contain actual pixels from the owned physical WFCAMOUT.

Synthetic loopback media, arbitrary HTTP image responses, API success, endpoint reachability, and file-signature validation are never sufficient to satisfy M3.

## Safety boundary

- Camera endpoint candidates must be explicitly configured; the tool does not scan arbitrary networks.
- Credentials must not be embedded in URIs.
- Optional credential files are restricted to `/etc/bigbird-camera/` and are never printed into evidence.
- Output evidence records only the redacted source URI, transport, byte size, UTC timestamp, SHA-256, image-payload validation state, and pending visual-verification state.
- Private owner evidence establishes the camera model as BAZZ WFCAMOUT. Serial numbers and other unnecessary private identifiers are not reproduced in this public repository document.
- No real WFCAMOUT frame has yet been claimed by this repository increment.

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

Run manually only after the local endpoint is verified:

```sh
python3 server/bigbird_camera_first_frame.py --camera bazz-primary
```

A successful probe result means only that a candidate image payload was captured and hashed. The frame must then be visually verified before M3 is recorded. Project completion still requires actual BAZZ live video through WW.CX, AI/event validation, persistence, and recovery.
