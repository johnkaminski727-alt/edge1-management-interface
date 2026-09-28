import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from server import phone_intelligence_gateway as gateway


class PhoneGatewayTests(unittest.TestCase):
    def test_dashboard_route(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/intelligence/dashboard"
            ),
            "/v1/intelligence/dashboard",
        )

    def test_phone_list_query(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/intelligence/phones"
                "?status=confirmed&limit=5"
            ),
            "/v1/intelligence/phones"
            "?limit=5&status=confirmed",
        )

    def test_phone_search_query(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/intelligence/phones"
                "?q=Canora&limit=10"
            ),
            "/v1/intelligence/phones"
            "?limit=10&q=Canora",
        )

    def test_detail_route(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/intelligence/phones/90"
            ),
            "/v1/intelligence/phones/90",
        )

    def test_sources_route(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/intelligence/sources?limit=5"
            ),
            "/v1/intelligence/sources?limit=5",
        )

    def test_unknown_route_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/intelligence/admin"
            )
        )

    def test_unknown_query_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/intelligence/phones"
                "?evil=true"
            )
        )

    def test_duplicate_query_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/intelligence/phones"
                "?limit=5&limit=10"
            )
        )

    def test_dashboard_query_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/intelligence/dashboard?x=1"
            )
        )

    def test_secret_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secret"
            path.write_bytes(b"x" * 64)

            self.assertEqual(
                gateway.read_secret(path),
                b"x" * 64,
            )

    def test_short_secret_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secret"
            path.write_bytes(b"short")

            with self.assertRaises(
                gateway.GatewayError
            ):
                gateway.read_secret(path)

    def test_symlink_secret_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            link = root / "link"

            target.write_bytes(b"x" * 64)
            link.symlink_to(target)

            with self.assertRaises(
                gateway.GatewayError
            ):
                gateway.read_secret(link)

    def test_signed_get_uses_exact_path(self):
        secret = b"s" * 64
        path = (
            "/v1/intelligence/phones"
            "?limit=5&status=confirmed"
        )

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return b'{"total":48,"phones":[]}'

        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        with (
            mock.patch.object(
                gateway.time,
                "time",
                return_value=1000,
            ),
            mock.patch.object(
                gateway.secrets,
                "token_hex",
                return_value="abc123",
            ),
            mock.patch.object(
                gateway.urllib.request,
                "urlopen",
                side_effect=fake_urlopen,
            ),
        ):
            status, body = gateway.signed_get(
                path,
                secret=secret,
            )

        self.assertEqual(status, 200)
        self.assertIn(b'"total":48', body)

        request = captured["request"]

        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:8097" + path,
        )

        body_hash = hashlib.sha256(
            b""
        ).hexdigest()

        canonical = "\n".join(
            (
                "GET",
                path,
                "1000",
                "abc123",
                gateway.DEFAULT_ACTOR,
                body_hash,
            )
        ).encode()

        expected = hmac.new(
            secret,
            canonical,
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(
            request.get_header(
                "X-wwcx-signature"
            ),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
