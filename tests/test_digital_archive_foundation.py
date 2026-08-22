import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).parents[1]


class DigitalArchiveFoundationTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def test_paperless_is_pinned_loopback_and_secret_file_based(self):
        text = self.read('deploy/digital-archive/paperless/compose.yaml')
        self.assertIn('paperless-ngx:3.0.5', text)
        self.assertIn('127.0.0.1:8113:8000', text)
        self.assertNotIn(':latest', text)
        self.assertIn('PAPERLESS_DBPASS_FILE', text)
        self.assertIn('PAPERLESS_SECRET_KEY_FILE', text)
        self.assertNotRegex(text, r'(?m)^\s*(PAPERLESS_DBPASS|PAPERLESS_SECRET_KEY):\s*\S+')

    def test_archivebox_is_stable_private_and_no_ia_submit(self):
        text = self.read('deploy/digital-archive/archivebox/compose.yaml')
        self.assertIn('archivebox/archivebox:0.7.4', text)
        self.assertIn('127.0.0.1:8114:8000', text)
        self.assertNotIn(':latest', text)
        for flag in ('PUBLIC_INDEX', 'PUBLIC_SNAPSHOTS', 'PUBLIC_ADD_VIEW', 'SAVE_ARCHIVE_DOT_ORG'):
            self.assertRegex(text, rf'{flag}:\s*["\']False["\']')

    def test_no_wildcard_web_bind(self):
        for path in (
            'deploy/digital-archive/paperless/compose.yaml',
            'deploy/digital-archive/archivebox/compose.yaml',
        ):
            text = self.read(path)
            self.assertNotRegex(text, r'(?m)^\s*-\s*["\']?(?:0\.0\.0\.0:|811[34]:)')

    def test_architecture_preserves_authority_split(self):
        text = self.read('docs/archive/wwcx-digital-archive-architecture.md')
        self.assertIn('one authoritative durable home', text.lower())
        self.assertIn('Big Bird', text)
        self.assertIn('Cookie Monster', text)
        self.assertIn('Fengus', text)

    def test_external_integrations_forbid_credentials(self):
        text = self.read('docs/archive/external-integrations.md').lower()
        self.assertIn('no external account credential', text)

    def test_retirement_requires_live_acceptance(self):
        text = self.read('docs/cookie-monster/bigbird-split-steady-state.md').lower()
        self.assertIn('live acceptance', text)
        self.assertIn('archived/disabled', text)


if __name__ == '__main__':
    unittest.main()
