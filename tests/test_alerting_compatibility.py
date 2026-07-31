from __future__ import annotations

import importlib.util
import math
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capcp_probe = load_module("capcp_probe", ROOT / "tools/alerting/capcp_probe.py")
ebs_probe = load_module("ebs_tone_probe", ROOT / "tools/alerting/ebs_tone_probe.py")
FIXTURE = ROOT / "tests/fixtures/alerting/capcp-test-alert.xml"


class CapCpProbeTests(unittest.TestCase):
    def test_synthetic_restricted_test_message_passes(self):
        report = capcp_probe.validate_capcp(FIXTURE)
        self.assertTrue(report.compatible, report.errors)
        self.assertEqual(report.fields["status"], "Test")
        self.assertEqual(report.fields["languages"], ["en-CA", "fr-CA"])

    def test_actual_message_is_blocked_by_default(self):
        xml = FIXTURE.read_text(encoding="utf-8").replace("<status>Test</status>", "<status>Actual</status>")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "actual.xml"
            path.write_text(xml, encoding="utf-8")
            report = capcp_probe.validate_capcp(path)
        self.assertFalse(report.compatible)
        self.assertIn("Actual alerts are blocked", " ".join(report.errors))

    def test_multiple_event_types_are_rejected(self):
        xml = FIXTURE.read_text(encoding="utf-8").replace("<value>testMessage</value>", "<value>otherEvent</value>", 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "multi-event.xml"
            path.write_text(xml, encoding="utf-8")
            report = capcp_probe.validate_capcp(path)
        self.assertFalse(report.compatible)
        self.assertIn("one subject event type", " ".join(report.errors))


class EbsToneProbeTests(unittest.TestCase):
    @staticmethod
    def _write_wave(path: Path, frequencies: tuple[float, ...], duration: float = 1.2):
        sample_rate = 8000
        amplitude = 9000 / max(1, len(frequencies))
        frames = bytearray()
        for index in range(int(sample_rate * duration)):
            value = sum(amplitude * math.sin(2.0 * math.pi * frequency * index / sample_rate) for frequency in frequencies)
            sample = max(-32768, min(32767, int(value)))
            frames.extend(sample.to_bytes(2, "little", signed=True))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(bytes(frames))

    def test_dual_tone_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dual.wav"
            self._write_wave(path, (853.0, 960.0))
            result = ebs_probe.probe(path, 0.5)
        self.assertTrue(result["compatible"], result)

    def test_single_tone_is_not_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "single.wav"
            self._write_wave(path, (853.0,))
            result = ebs_probe.probe(path, 0.5)
        self.assertFalse(result["compatible"], result)


if __name__ == "__main__":
    unittest.main()
