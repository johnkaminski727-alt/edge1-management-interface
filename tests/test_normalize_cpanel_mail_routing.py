from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

from tools.messaging import normalize_cpanel_mail_routing as normalizer


DOMAINS = ["creekco.ca", "scgardens.ca", "omegafx.com"]


def api2(domain: str, mode: str, *, success: int = 1):
    return {
        "cpanelresult": {
            "apiversion": 2,
            "data": [
                {
                    "alwaysaccept": 1 if mode in {"auto", "local", "secondary"} else 0,
                    "domain": domain,
                    "mxcheck": mode,
                    "result": 1,
                }
            ],
            "event": {"result": success},
            "func": "getmxcheck",
            "module": "Email",
        }
    }


class NormalizeCpanelMailRoutingTests(unittest.TestCase):
    def write_capture(
        self,
        root: pathlib.Path,
        *,
        modes: dict[str, str] | None = None,
        failed_domain: str | None = None,
        returned_domain: str | None = None,
    ) -> pathlib.Path:
        root.mkdir(parents=True)
        selected_modes = modes or {
            "creekco.ca": "local",
            "scgardens.ca": "remote",
            "omegafx.com": "auto",
        }

        payloads = {
            "metadata.json": {
                "contract": "wwcx.cpanel-mail-routing-evidence.v1",
                "captured_at": "2026-08-01T09:00:00Z",
                "read_only": True,
                "cpanel_host": "business159.web-hosting.com",
                "cpanel_user_sha256": "0" * 64,
                "domains": DOMAINS,
                "transport": "https-cpanel-api-token",
                "api_family": "cpanel-api-2",
                "function": "Email::getmxcheck",
                "sensitivity": "restricted-operational-metadata",
            }
        }

        for domain in DOMAINS:
            safe = domain.replace(".", "_")
            response_domain = returned_domain if domain == "creekco.ca" and returned_domain else domain
            payloads[f"getmxcheck-{safe}.json"] = api2(
                response_domain,
                selected_modes[domain],
                success=0 if domain == failed_domain else 1,
            )

        lines = []
        for filename, payload in sorted(payloads.items()):
            path = root / filename
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {filename}")

        (root / "SHA256SUMS").write_text(
            "\n".join(lines) + "\n",
            encoding="ascii",
        )
        return root

    def test_normalizes_known_routing_modes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "routing")
            inventory = normalizer.normalize_routing_capture(evidence)

        self.assertEqual(inventory["contract"], "wwcx.provider-mail-objects.v1")
        self.assertEqual(inventory["provider_family"], "namecheap_shared_hosting")
        self.assertEqual(inventory["source"]["method"], "provider_api")
        self.assertEqual(inventory["objects"], [])
        self.assertEqual(inventory["default_addresses"], [])

        by_domain = {
            item["domain"]: item["mode"] for item in inventory["domain_routing"]
        }
        self.assertEqual(by_domain["creekco.ca"], "local")
        self.assertEqual(by_domain["scgardens.ca"], "remote")
        self.assertEqual(by_domain["omegafx.com"], "automatic")

    def test_secondary_mode_is_conservatively_unknown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(
                pathlib.Path(temp_dir) / "routing",
                modes={
                    "creekco.ca": "secondary",
                    "scgardens.ca": "remote",
                    "omegafx.com": "auto",
                },
            )
            inventory = normalizer.normalize_routing_capture(evidence)

        by_domain = {
            item["domain"]: item["mode"] for item in inventory["domain_routing"]
        }
        self.assertEqual(by_domain["creekco.ca"], "unknown")

    def test_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "routing")
            (evidence / "getmxcheck-creekco_ca.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(normalizer.RoutingEvidenceError, "SHA-256 mismatch"):
                normalizer.normalize_routing_capture(evidence)

    def test_rejects_failed_api_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(
                pathlib.Path(temp_dir) / "routing",
                failed_domain="scgardens.ca",
            )
            with self.assertRaisesRegex(normalizer.RoutingEvidenceError, "API success"):
                normalizer.normalize_routing_capture(evidence)

    def test_rejects_domain_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(
                pathlib.Path(temp_dir) / "routing",
                returned_domain="example.com",
            )
            with self.assertRaisesRegex(normalizer.RoutingEvidenceError, "was expected"):
                normalizer.normalize_routing_capture(evidence)

    def test_rejects_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "routing")
            missing = evidence / "getmxcheck-omegafx_com.json"
            missing.unlink()
            lines = [
                line
                for line in (evidence / "SHA256SUMS").read_text(encoding="ascii").splitlines()
                if not line.endswith("getmxcheck-omegafx_com.json")
            ]
            (evidence / "SHA256SUMS").write_text(
                "\n".join(lines) + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(normalizer.RoutingEvidenceError, "incomplete"):
                normalizer.normalize_routing_capture(evidence)


if __name__ == "__main__":
    unittest.main()
