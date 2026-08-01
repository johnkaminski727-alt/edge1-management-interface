#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tools" / "messaging" / "capture_cpanel_mail_inventory.sh"


class CpanelMailInventoryCaptureTests(unittest.TestCase):
    def make_fake_bin(self, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        fake_bin = root / "bin"
        fake_bin.mkdir()
        log_path = root / "uapi.log"

        (fake_bin / "id").write_text(
            "#!/bin/sh\n"
            "case \"${1:-}\" in\n"
            "  -u) printf '%s\\n' 955 ;;\n"
            "  -un) printf '%s\\n' wwcxjywl ;;\n"
            "  *) exit 64 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        (fake_bin / "uapi").write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$UAPI_LOG\"\n"
            "cat <<'JSON'\n"
            '{"apiversion":3,"func":"test","module":"Email",'
            '"result":{"data":[],"errors":null,"messages":null,'
            '"metadata":{},"status":1,"warnings":null}}\n'
            "JSON\n",
            encoding="utf-8",
        )
        for path in (fake_bin / "id", fake_bin / "uapi"):
            path.chmod(0o700)
        return fake_bin, log_path

    def test_normal_account_user_does_not_pass_root_only_user_option(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            fake_bin, log_path = self.make_fake_bin(root)
            output = root / "evidence"
            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
            env["UAPI_LOG"] = str(log_path)

            result = subprocess.run(
                [
                    "sh",
                    str(CAPTURE),
                    "--output",
                    str(output),
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
            calls = log_path.read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(len(calls), 7)
            self.assertTrue(all("--user=" not in call for call in calls))
            self.assertTrue(all("--output=jsonpretty" in call for call in calls))

            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["uapi_execution_mode"], "current-account-user")
            self.assertTrue(metadata["read_only"])
            self.assertTrue((output / "SHA256SUMS").is_file())

    def test_normal_account_user_cannot_select_another_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            fake_bin, log_path = self.make_fake_bin(root)
            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
            env["UAPI_LOG"] = str(log_path)

            result = subprocess.run(
                [
                    "sh",
                    str(CAPTURE),
                    "--output",
                    str(root / "evidence"),
                    "--user",
                    "anotheruser",
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
            self.assertEqual(result.returncode, 77)
            self.assertIn("may only inspect its own account", result.stderr)
            self.assertFalse(log_path.exists())


if __name__ == "__main__":
    unittest.main()
