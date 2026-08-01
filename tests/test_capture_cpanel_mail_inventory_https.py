#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tools" / "messaging" / "capture_cpanel_mail_inventory_https.sh"


class CpanelHttpsMailInventoryCaptureTests(unittest.TestCase):
    def make_fake_curl(self, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        fake_bin = root / "bin"
        fake_bin.mkdir()
        args_log = root / "curl-args.log"
        (fake_bin / "curl").write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$CURL_ARGS_LOG\"\n"
            "config=$(cat)\n"
            "case \"$config\" in\n"
            "  *'Authorization: cpanel wwcxjywl:TESTTOKEN'*) ;;\n"
            "  *) echo 'missing expected authorization config' >&2; exit 91 ;;\n"
            "esac\n"
            "cat <<'JSON'\n"
            '{\"apiversion\":3,\"func\":\"test\",\"module\":\"Email\",'
            '\"result\":{\"data\":[],\"errors\":null,\"messages\":null,'
            '\"metadata\":{},\"status\":1,\"warnings\":null}}\n'
            "JSON\n",
            encoding="utf-8",
        )
        (fake_bin / "curl").chmod(0o700)
        return fake_bin, args_log

    def test_token_is_not_passed_in_curl_command_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            fake_bin, args_log = self.make_fake_curl(root)
            output = root / "evidence"
            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
            env["CURL_ARGS_LOG"] = str(args_log)
            env["CPANEL_API_TOKEN"] = "TESTTOKEN"

            result = subprocess.run(
                [
                    "sh",
                    str(CAPTURE),
                    "--output",
                    str(output),
                    "--host",
                    "business159.web-hosting.com",
                    "--user",
                    "wwcxjywl",
                    "--domain",
                    "creekco.ca",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("TESTTOKEN", args_log.read_text(encoding="utf-8"))
            self.assertEqual(len(list(output.glob("*.json"))), 8)

            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["uapi_execution_mode"], "https-api-token")
            self.assertEqual(metadata["token_input_mode"], "environment")
            self.assertFalse(metadata["token_retained"])
            self.assertEqual(metadata["domains"], ["creekco.ca"])

            check = subprocess.run(
                ["sha256sum", "-c", "SHA256SUMS"],
                cwd=output,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_invalid_token_is_rejected_before_curl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            fake_bin, args_log = self.make_fake_curl(root)
            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
            env["CURL_ARGS_LOG"] = str(args_log)
            env["CPANEL_API_TOKEN"] = "bad token"

            result = subprocess.run(
                [
                    "sh",
                    str(CAPTURE),
                    "--output",
                    str(root / "evidence"),
                    "--host",
                    "business159.web-hosting.com",
                    "--user",
                    "wwcxjywl",
                    "--domain",
                    "creekco.ca",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 64)
            self.assertIn("Invalid cPanel API-token format", result.stderr)
            self.assertFalse(args_log.exists())


if __name__ == "__main__":
    unittest.main()
