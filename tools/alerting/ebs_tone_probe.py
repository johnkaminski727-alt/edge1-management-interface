#!/usr/bin/env python3
"""Detect the legacy EBS 853/960 Hz two-tone attention signal in a PCM WAV file.

This is a receive-side laboratory probe. It does not generate, transmit, route,
or activate emergency alerts.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import sys
import wave
from pathlib import Path

MAX_DURATION_SECONDS = 120
WINDOW_SECONDS = 0.10
TARGETS = (853.0, 960.0)


def _goertzel_power(samples: list[float], sample_rate: int, target_hz: float) -> float:
    if not samples:
        return 0.0
    k = int(0.5 + (len(samples) * target_hz / sample_rate))
    omega = 2.0 * math.pi * k / len(samples)
    coeff = 2.0 * math.cos(omega)
    q0 = q1 = q2 = 0.0
    for sample in samples:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0
    return max(0.0, q1 * q1 + q2 * q2 - coeff * q1 * q2)


def _decode_pcm(raw: bytes, sample_width: int, channels: int) -> list[float]:
    if sample_width != 2:
        raise ValueError("only 16-bit PCM WAV files are supported")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if channels == 1:
        return [value / 32768.0 for value in values]
    if channels == 2:
        return [
            (values[index] + values[index + 1]) / 65536.0
            for index in range(0, len(values) - 1, 2)
        ]
    raise ValueError("only mono or stereo WAV files are supported")


def probe(path: Path, min_duration: float) -> dict[str, object]:
    with wave.open(str(path), "rb") as wav:
        if wav.getcomptype() != "NONE":
            raise ValueError("compressed WAV files are not supported")
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frame_count = wav.getnframes()
        duration = frame_count / sample_rate if sample_rate else 0.0
        if duration > MAX_DURATION_SECONDS:
            raise ValueError(f"WAV exceeds {MAX_DURATION_SECONDS}-second safety limit")
        raw = wav.readframes(frame_count)

    samples = _decode_pcm(raw, sample_width, channels)
    window_size = max(1, int(sample_rate * WINDOW_SECONDS))
    max_consecutive = current_consecutive = 0
    qualifying_windows = 0
    ratios: list[dict[str, float]] = []

    for offset in range(0, len(samples) - window_size + 1, window_size):
        window = samples[offset : offset + window_size]
        total_energy = sum(sample * sample for sample in window)
        if total_energy <= 1e-9:
            current_consecutive = 0
            continue

        powers = [_goertzel_power(window, sample_rate, hz) for hz in TARGETS]
        normalized = [power / (len(window) * len(window) * total_energy) for power in powers]
        balance = powers[0] / powers[1] if powers[1] > 0 else math.inf

        qualifies = (
            normalized[0] >= 0.0001
            and normalized[1] >= 0.0001
            and 0.25 <= balance <= 4.0
        )
        ratios.append(
            {
                "offset_seconds": round(offset / sample_rate, 3),
                "ratio_853": round(normalized[0], 6),
                "ratio_960": round(normalized[1], 6),
                "balance": round(balance, 4) if math.isfinite(balance) else -1.0,
            }
        )

        if qualifies:
            qualifying_windows += 1
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0

    detected_duration = max_consecutive * WINDOW_SECONDS
    return {
        "compatible": detected_duration >= min_duration,
        "profile": "legacy EBS 853/960 Hz receive-side compatibility probe",
        "operating_mode": "read-only test laboratory",
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "duration_seconds": round(duration, 3),
        "minimum_required_seconds": min_duration,
        "detected_contiguous_seconds": round(detected_duration, 3),
        "qualifying_windows": qualifying_windows,
        "window_seconds": WINDOW_SECONDS,
        "analysis": ratios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav_file", type=Path)
    parser.add_argument("--min-duration", type=float, default=0.5)
    args = parser.parse_args()

    if not 0.1 <= args.min_duration <= 30.0:
        parser.error("--min-duration must be between 0.1 and 30 seconds")

    try:
        result = probe(args.wav_file, args.min_duration)
    except (OSError, ValueError, wave.Error) as exc:
        print(json.dumps({"compatible": False, "errors": [str(exc)]}, indent=2))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["compatible"] else 1


if __name__ == "__main__":
    sys.exit(main())
