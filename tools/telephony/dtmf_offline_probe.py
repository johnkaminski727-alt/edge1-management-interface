#!/usr/bin/env python3
"""Generate and detect the complete 16-key DTMF matrix without telephony I/O."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, Iterable, List, Sequence, Tuple

SAMPLE_RATE_DEFAULT = 8000
DURATION_MS_DEFAULT = 120
ROW_FREQUENCIES: Tuple[int, ...] = (697, 770, 852, 941)
COLUMN_FREQUENCIES: Tuple[int, ...] = (1209, 1336, 1477, 1633)
KEYPAD: Tuple[Tuple[str, ...], ...] = (
    ("1", "2", "3", "A"),
    ("4", "5", "6", "B"),
    ("7", "8", "9", "C"),
    ("*", "0", "#", "D"),
)

DTMF_FREQUENCIES: Dict[str, Tuple[int, int]] = {
    KEYPAD[row_index][column_index]: (row_frequency, column_frequency)
    for row_index, row_frequency in enumerate(ROW_FREQUENCIES)
    for column_index, column_frequency in enumerate(COLUMN_FREQUENCIES)
}


def generate_tone(
    digit: str,
    *,
    sample_rate: int,
    duration_ms: int,
    amplitude: float = 0.42,
) -> List[float]:
    """Return a normalized dual-tone waveform for one DTMF digit."""

    row_frequency, column_frequency = DTMF_FREQUENCIES[digit]
    sample_count = max(1, int(sample_rate * duration_ms / 1000))
    fade_samples = max(1, min(sample_count // 8, int(sample_rate * 0.005)))
    samples: List[float] = []

    for index in range(sample_count):
        time_value = index / sample_rate
        envelope = 1.0
        if index < fade_samples:
            envelope = index / fade_samples
        elif index >= sample_count - fade_samples:
            envelope = (sample_count - index - 1) / fade_samples
        value = amplitude * envelope * (
            math.sin(2.0 * math.pi * row_frequency * time_value)
            + math.sin(2.0 * math.pi * column_frequency * time_value)
        )
        samples.append(value)

    return samples


def goertzel_power(
    samples: Sequence[float], frequency: int, sample_rate: int
) -> float:
    """Return Goertzel power for one target frequency."""

    omega = 2.0 * math.pi * frequency / sample_rate
    coefficient = 2.0 * math.cos(omega)
    previous = 0.0
    previous_two = 0.0

    for sample in samples:
        current = sample + coefficient * previous - previous_two
        previous_two = previous
        previous = current

    return (
        previous_two * previous_two
        + previous * previous
        - coefficient * previous * previous_two
    )


def strongest(
    powers: Dict[int, float], candidates: Iterable[int]
) -> Tuple[int, float, float]:
    ordered = sorted(
        ((frequency, powers[frequency]) for frequency in candidates),
        key=lambda item: item[1],
        reverse=True,
    )
    winner_frequency, winner_power = ordered[0]
    runner_up_power = ordered[1][1]
    return winner_frequency, winner_power, runner_up_power


def inspect_digit(digit: str, sample_rate: int, duration_ms: int) -> Dict[str, object]:
    samples = generate_tone(
        digit,
        sample_rate=sample_rate,
        duration_ms=duration_ms,
    )
    all_frequencies = ROW_FREQUENCIES + COLUMN_FREQUENCIES
    powers = {
        frequency: goertzel_power(samples, frequency, sample_rate)
        for frequency in all_frequencies
    }
    detected_row, row_power, row_runner_up = strongest(powers, ROW_FREQUENCIES)
    detected_column, column_power, column_runner_up = strongest(
        powers, COLUMN_FREQUENCIES
    )
    expected_row, expected_column = DTMF_FREQUENCIES[digit]
    row_separation = row_power / max(row_runner_up, 1e-12)
    column_separation = column_power / max(column_runner_up, 1e-12)
    passed = (
        detected_row == expected_row
        and detected_column == expected_column
        and row_separation >= 8.0
        and column_separation >= 8.0
    )

    return {
        "digit": digit,
        "expected_row_hz": expected_row,
        "expected_column_hz": expected_column,
        "detected_row_hz": detected_row,
        "detected_column_hz": detected_column,
        "row_separation_ratio": round(row_separation, 3),
        "column_separation_ratio": round(column_separation, 3),
        "passed": passed,
    }


def run_probe(sample_rate: int, duration_ms: int) -> Dict[str, object]:
    results = [
        inspect_digit(digit, sample_rate, duration_ms)
        for row in KEYPAD
        for digit in row
    ]
    passed = all(bool(result["passed"]) for result in results)
    return {
        "audit_state": "PASS" if passed else "FAIL",
        "mode": "offline synthetic generation and detection only",
        "sample_rate_hz": sample_rate,
        "duration_ms": duration_ms,
        "digits_expected": "123A456B789C*0#D",
        "digits_tested": len(results),
        "rfc4733_event_range": "0-15",
        "network_access": False,
        "channel_created": False,
        "call_originated": False,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline 16-key DTMF generator and detector probe."
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=SAMPLE_RATE_DEFAULT,
        help="sample rate in Hz (default: 8000)",
    )
    parser.add_argument(
        "--duration-ms",
        type=int,
        default=DURATION_MS_DEFAULT,
        help="tone duration in milliseconds (default: 120)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the complete result as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_rate < 4000:
        raise SystemExit("sample rate must be at least 4000 Hz")
    if not 40 <= args.duration_ms <= 2000:
        raise SystemExit("duration must be between 40 and 2000 milliseconds")

    report = run_probe(args.sample_rate, args.duration_ms)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("WW.CX OFFLINE DTMF PROBE")
        print(f"Audit state: {report['audit_state']}")
        print(f"Digits tested: {report['digits_tested']}")
        print(f"RFC 4733 event range: {report['rfc4733_event_range']}")
        for result in report["results"]:
            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"{status} digit={result['digit']} "
                f"row={result['detected_row_hz']}Hz "
                f"column={result['detected_column_hz']}Hz"
            )
        print("No network access, channel creation, or call origination occurred.")

    return 0 if report["audit_state"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
