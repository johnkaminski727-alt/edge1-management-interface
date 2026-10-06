import unittest
from server import mail_openpgp_mime as module
class TestOpenPGPMIME(unittest.TestCase):
    def test_detect_encrypted(self):
        raw=(b'MIME-Version: 1.0\r\nContent-Type: multipart/encrypted; protocol="application/pgp-encrypted"; boundary=x\r\n\r\n--x\r\nContent-Type: application/pgp-encrypted\r\n\r\nVersion: 1\r\n--x--\r\n')
        self.assertTrue(module.detect(raw)['encrypted'])
    def test_invalid_adapter_fails_closed(self):
        with self.assertRaises(module.OpenPGPMIMEError):
            module.require_transform(b'From: a@b\r\n\r\nx', lambda *_: {}, {})
if __name__ == '__main__': unittest.main()
