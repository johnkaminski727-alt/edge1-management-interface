import hashlib
import http.server
import json
import pathlib
import socketserver
import sys
import tempfile
import threading
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import bigbird_camera_first_frame as probe

JPEG = b"\xff\xd8\xff\xe0" + b"TESTFRAME" + b"\xff\xd9"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(JPEG)))
        self.end_headers()
        self.wfile.write(JPEG)
    def log_message(self, fmt, *args):
        return


class Tests(unittest.TestCase):
    def test_transport_priority(self):
        camera = {"candidates": [
            {"transport": "http_snapshot", "uri": "http://127.0.0.1/a"},
            {"transport": "rtsp", "uri": "rtsp://127.0.0.1/b"},
            {"transport": "mjpeg", "uri": "http://127.0.0.1/c"},
        ]}
        self.assertEqual([x.transport for x in probe.candidates_for(camera)], ["rtsp", "mjpeg", "http_snapshot"])

    def test_embedded_credentials_rejected(self):
        with self.assertRaises(probe.CameraProbeError):
            probe.candidates_for({"candidates": [{"transport": "rtsp", "uri": "rtsp://u:p@127.0.0.1/x"}]})

    def test_secret_path_confined(self):
        with self.assertRaises(probe.CameraProbeError):
            probe.candidates_for({"candidates": [{"transport": "rtsp", "uri": "rtsp://127.0.0.1/x", "password_file": "/tmp/p"}]})

    def test_redacts_uri_credentials(self):
        self.assertEqual(probe.redact_uri("rtsp://user:pass@example.test:554/live"), "rtsp://example.test:554/live")

    def test_http_first_frame_and_evidence(self):
        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with tempfile.TemporaryDirectory() as td:
                root = pathlib.Path(td)
                config = root / "cameras.json"
                config.write_text(json.dumps({"cameras": [{
                    "id": "bazz-test", "enabled": True,
                    "candidates": [{"transport": "http_snapshot", "uri": f"http://127.0.0.1:{server.server_address[1]}/snapshot.jpg"}]
                }]}))
                result = probe.run(config, "bazz-test", root / "frames", root / "evidence")
                self.assertEqual(result["status"], "first_frame_captured")
                frame = pathlib.Path(result["frame"])
                evidence = json.loads(pathlib.Path(result["evidence"]).read_text())
                self.assertEqual(frame.read_bytes(), JPEG)
                self.assertEqual(evidence["sha256"], hashlib.sha256(JPEG).hexdigest())
                self.assertTrue(evidence["verified_image_payload"])
                self.assertTrue(evidence["live_camera_pixels_verified"])
            server.shutdown()

    def test_disabled_camera_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "c.json"
            path.write_text(json.dumps({"cameras": [{"id": "x", "enabled": False, "candidates": []}]}))
            with self.assertRaises(probe.CameraProbeError):
                probe.load_camera(path, "x")


if __name__ == "__main__":
    unittest.main()
