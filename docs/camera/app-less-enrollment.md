# Project Big Bird camera app-less enrollment

Date: 2026-08-18  
Status: repository-ready foundation; vendor provisioning protocol still gated by evidence

## Purpose

Provide a reusable Edge1-side enrollment contract for cameras without confusing Big Bird identity with a camera vendor's activation credentials.

The immediate target is the owned BAZZ WFCAMOUT. App-less provisioning is a design requirement. The BAZZ mobile application is not an operational dependency.

## Token boundary

Two credential domains remain strictly separate:

1. **Vendor / BAZZ / Tuya activation material** — whatever the stock firmware actually requires to join, activate, or bind. Its exact WFCAMOUT semantics are not yet verified.
2. **WW.CX / Big Bird enrollment token** — a cryptographically random, short-lived, one-time token used only to bind a WW.CX enrollment session to a Big Bird device identity.

`server/bigbird_camera_enrollment.py` implements only the second domain. It does not construct a vendor QR code, accept a Wi-Fi password, store a vendor activation token, or claim that an arbitrary Big Bird token can be placed into a vendor payload.

## Enrollment state model

The reusable state sequence is:

`CREATED -> WAITING_FOR_PROVISIONING -> WAITING_FOR_CAMERA -> CAMERA_OBSERVED -> DEVICE_BOUND -> FIRST_FRAME_PENDING -> FIRST_FRAME_CAPTURED`

`FAILED` and `EXPIRED` are terminal states. Invalid jumps fail closed.

The module stores only a SHA-256 digest of the one-time enrollment token. Token replay is rejected, expiry is enforced, and audit events reject secret-like fields.

## Current WFCAMOUT evidence classification

| Finding | Classification | Status |
| --- | --- | --- |
| Physical owned camera label identifies model WFCAMOUT | VERIFIED WFCAMOUT | Confirmed from owner-controlled photograph |
| BAZZ Android package is `com.bazz.wifi` | VERIFIED BAZZ PLATFORM | Public distribution metadata found; APK binary analysis still pending |
| Current BAZZ app distribution notes mention IPC pairing in QR-code mode | VERIFIED BAZZ PLATFORM | Confirms a BAZZ-platform IPC QR flow exists, not its exact WFCAMOUT payload |
| Exact WFCAMOUT QR schema, keys, escaping, vendor-token source and TTL | UNKNOWN | Do not implement from generic assumptions |
| WFCAMOUT support for AP mode / SmartConfig without vendor activation | UNKNOWN | Must be verified on authoritative implementation evidence or owner-controlled testing |
| Local RTSP/ONVIF/MJPEG/snapshot interfaces | UNKNOWN | Continue bounded discovery after the camera joins the owner-controlled LAN |

## Security properties

- no Wi-Fi password in this module, logs, audit rows, documentation, or Git;
- no raw Big Bird token stored after session creation;
- one-time token consumption and expiry;
- explicit token namespace `bigbird_enrollment`;
- no vendor token or QR payload generation until the stock-camera contract is verified;
- no network listener or public Edge1 exposure;
- no firmware changes;
- no cloud-authentication bypass.

## Integration direction

WW.CX remains the authenticated browser plane. Edge1 remains the private enrollment, discovery, camera-adapter, media, AI, and durable-device-identity plane. Existing authenticated/queued WW.CX-to-Edge1 patterns should carry enrollment work; a new public Edge1 listener is not required.

## First-frame handoff

Once the physical camera is actually identified on the LAN and bound to an enrollment session, transition to `FIRST_FRAME_PENDING` and pass explicitly configured media candidates to the existing bounded first-frame probe. Capturing an image-like payload remains pending visual verification until the owner-controlled WFCAMOUT pixels are visibly confirmed.
