"""Send-route caller authentication (deploy/email/mail-room-send)."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "deploy/email/mail-room-send/gateway/server"))
sys.path.insert(0, str(ROOT / "deploy/email/mail-room-send/mailroom/server"))

import outbound_mail_preparation_auth as preparation_auth  # noqa: E402
import outbound_mail_send_auth as send_auth  # noqa: E402
from mail_room_send import MailRoomSendClient  # noqa: E402

SEND_SECRET = "s" * 48
PREP_SECRET = "p" * 48
ENV = {"WWCX_MAIL_SEND_TOKEN": SEND_SECRET, "WWCX_MAIL_GATEWAY_TOKEN": PREP_SECRET}


class SendAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.nonces = Path(self.tmp.name) / "send-nonces.sqlite3"
        self.body = json.dumps({"to": ["a@example.com"], "subject": "x", "confirm_send": True}).encode()
        self.client = MailRoomSendClient(secret=SEND_SECRET)

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, headers, body=None, path=send_auth.SEND_PATH, env=ENV):
        return send_auth.verify_send(headers, "POST", path, self.body if body is None else body, nonce_store=self.nonces, environment=env)

    def test_mail_room_client_signature_is_accepted(self):
        verified = self.verify(self.client.headers(self.body))
        self.assertEqual(verified.client_id, "wwcx-mail-room")

    def test_unsigned_request_is_rejected(self):
        with self.assertRaises(preparation_auth.InvalidPreparationAuthError):
            self.verify({"Content-Type": "application/json"})

    def test_preparation_token_cannot_sign_sends(self):
        # The shared preparation secret (held by the Private AI client) must not work here,
        # whether it claims its own client ID or the Mail Room's.
        for client_id in ("wwcx-private-ai", "wwcx-mail-room"):
            headers = preparation_auth.build_headers(PREP_SECRET, client_id, "POST", send_auth.SEND_PATH, self.body)
            with self.assertRaises(preparation_auth.InvalidPreparationAuthError):
                self.verify(headers)

    def test_body_changed_after_signing_is_rejected(self):
        headers = self.client.headers(self.body)
        with self.assertRaises(preparation_auth.InvalidPreparationAuthError):
            self.verify(headers, body=self.body.replace(b"a@example.com", b"b@example.com"))

    def test_replayed_nonce_is_rejected(self):
        headers = self.client.headers(self.body)
        self.verify(headers)
        with self.assertRaises(preparation_auth.PreparationReplayError):
            self.verify(headers)

    def test_stale_timestamp_is_rejected(self):
        headers = self.client.headers(self.body, timestamp=int(time.time()) - 600)
        with self.assertRaises(preparation_auth.InvalidPreparationAuthError):
            self.verify(headers)

    def test_missing_send_secret_fails_closed(self):
        with self.assertRaises(preparation_auth.PreparationAuthUnavailableError):
            self.verify(self.client.headers(self.body), env={"WWCX_MAIL_GATEWAY_TOKEN": PREP_SECRET})

    def test_only_the_send_route_is_accepted(self):
        with self.assertRaises(preparation_auth.InvalidPreparationAuthError):
            self.verify(self.client.headers(self.body), path="/outbound-mail/preview")

    def test_client_refuses_non_loopback_targets(self):
        for url in ("http://10.77.0.1:8104", "https://127.0.0.1:8104", "http://127.0.0.1:8117"):
            with self.assertRaises(ValueError):
                MailRoomSendClient(secret=SEND_SECRET, base_url=url)


if __name__ == "__main__":
    unittest.main()
