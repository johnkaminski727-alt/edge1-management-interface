import pathlib
import tempfile
import unittest
from server import mail_edge1_gateway_source as source
from server.mail_correspondence_store import MailCorrespondenceStore

class TestEdge1OpenPGPHold(unittest.TestCase):
    def test_encrypted_pgp_mime_is_held_before_correspondence_ingest(self):
        raw=(
            b'From: sender@example.net\r\n'
            b'To: postmaster@ww.cx\r\n'
            b'Date: Tue, 06 Oct 2026 09:00:00 +0000\r\n'
            b'Message-ID: <pgp-hold@example.net>\r\n'
            b'MIME-Version: 1.0\r\n'
            b'Content-Type: multipart/encrypted; protocol="application/pgp-encrypted"; boundary=x\r\n\r\n'
            b'--x\r\nContent-Type: application/pgp-encrypted\r\n\r\nVersion: 1\r\n'
            b'--x\r\nContent-Type: application/octet-stream\r\n\r\n-----BEGIN PGP MESSAGE-----\r\nsynthetic\r\n-----END PGP MESSAGE-----\r\n'
            b'--x--\r\n'
        )
        with tempfile.TemporaryDirectory() as td:
            store=source.open_edge1_store(pathlib.Path(td)/'mail.sqlite3')
            with self.assertRaisesRegex(source.Edge1MailGatewaySourceError,'held for isolated decryption'):
                source.normalize_edge1_rfc822(raw,store,envelope_recipient='postmaster@ww.cx',queue_id='ABC123')
            self.assertEqual(store.status()['record_count'],0)
if __name__=='__main__': unittest.main()
