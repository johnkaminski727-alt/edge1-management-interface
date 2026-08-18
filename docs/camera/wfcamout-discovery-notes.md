# BAZZ WFCAMOUT discovery notes

Date: 2026-08-18

Status: public-source research plus private owner model verification. Local network behavior remains unverified until the owned physical camera is observed on the owner's network.

## Verified identity

Private owner evidence identifies the physical camera as **BAZZ WFCAMOUT**. No serial number or other unnecessary private identifier is reproduced here.

BAZZ's current product page independently identifies SKU `WFCAMOUT` as its Smart WiFi HD 1080p Motorized Outdoor Camera.

## Manufacturer-documented behavior

BAZZ documentation currently supports the following facts:

- 1080p video, two-way audio, infrared night vision, motorized pan/tilt, and motion detection;
- 2.4 GHz Wi-Fi only; 5 GHz Wi-Fi is not supported;
- live video, recordings, snapshots, notifications, and automation are available through the BAZZ Smart Home application;
- current WFCAMOUT product information describes 16 GB internal storage and continuous or event-triggered recording;
- the BAZZ application exposes device information including device ID, IP address, MAC address, and device time zone;
- the general BAZZ application supports default pairing and an alternate AP/SmartConfig-style pairing mode depending on device support.

These facts make the BAZZ application device-information screen the least-invasive first route to obtain a candidate LAN address for M2.

## Platform lineage

BAZZ publicly announced a partnership with Tuya Smart in November 2020 and stated that BAZZ smart-home products would use Tuya's IoT platform. That establishes a BAZZ/Tuya relationship, but it does **not** by itself prove that this specific WFCAMOUT hardware revision, its currently installed firmware, or its local video transport is Tuya-derived.

Treat exact WFCAMOUT Tuya/Smart Life compatibility as **unverified** until the owned device or an exact model-specific technical artifact confirms it.

## Local-protocol status

As of this research pass, no authoritative WFCAMOUT source located here documents any of the following as supported:

- ONVIF;
- RTSP;
- RTMP;
- MJPEG endpoint;
- HTTP/HTTPS snapshot endpoint;
- HLS;
- WebRTC;
- mDNS;
- SSDP/UPnP;
- a documented owner-accessible proprietary LAN video API.

Absence from manufacturer marketing/manual material is **not** evidence that these protocols are absent from the device. Local protocol support remains unknown and should be resolved from the owned camera's actual LAN behavior.

No exact FCC ID, OEM manufacturer, chipset, or firmware family has yet been recovered for WFCAMOUT from authoritative model-specific evidence. Do not substitute visually similar camera records.

## First-frame discovery order

Use the narrowest owner-authorized evidence first:

1. read the WFCAMOUT's IP address from BAZZ Smart Home Device Settings / Device Information if the camera is already paired;
2. confirm that address on the owner network using passive neighbor/DHCP evidence where available;
3. probe only that identified host for standard camera protocols, beginning with ONVIF/RTSP and then bounded HTTP/MJPEG/HLS candidates;
4. record discovered listeners and protocol responses without storing credentials;
5. configure only verified candidate endpoint(s) in `/etc/bigbird-camera/cameras.json`;
6. run the one-shot capture probe;
7. visually verify the resulting artifact as actual WFCAMOUT pixels before recording M3.

If the camera is not currently paired, use the documented BAZZ application pairing path before considering broader or more invasive techniques. Firmware modification is not part of the current first-frame path.

## Evidence classification

- Camera model WFCAMOUT: **VERIFIED** from private owner evidence and independently consistent with BAZZ product identification.
- 2.4 GHz Wi-Fi, app streaming/recording and BAZZ device-information IP/MAC visibility: **MANUFACTURER-DOCUMENTED**.
- BAZZ/Tuya corporate platform relationship: **MANUFACTURER-DOCUMENTED**.
- Exact WFCAMOUT Tuya firmware lineage: **UNVERIFIED**.
- Exact local streaming protocol(s), LAN listeners, OEM, chipset, FCC ID, and firmware family: **UNVERIFIED** pending device/network evidence.

Public research sources used for this note:

- BAZZ Smart Home WFCAMOUT product page;
- BAZZ Smart Home application documentation;
- BAZZ Smart Home announcement of its Tuya Smart partnership.
