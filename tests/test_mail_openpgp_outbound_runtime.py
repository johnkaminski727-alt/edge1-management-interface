import json, pathlib, tempfile, unittest
from server import mail_openpgp_outbound_runtime as runtime

ROOT=pathlib.Path(__file__).resolve().parents[1]
POLICY=ROOT/'config/messaging/openpgp-policy.json'
SENDERS=ROOT/'config/messaging/openpgp-outbound-senders.json'

class TestOutboundResolver(unittest.TestCase):
    def test_john_resolves_to_sign_only(self):
        r=runtime.RuntimeOpenPGPResolver(POLICY,SENDERS)
        out=r({'from_address':'john@ww.cx','recipients':['recipient@example.net']})
        self.assertEqual(out['operation'],'sign')
        self.assertEqual(out['signing_fingerprint'],'316F9A96BCC1912631E98D6382A0ACB1EC85FBDF')
    def test_other_sender_is_unchanged(self):
        r=runtime.RuntimeOpenPGPResolver(POLICY,SENDERS)
        self.assertIsNone(r({'from_address':'records@ww.cx','recipients':['recipient@example.net']}))
    def test_disabled_runtime_fails_closed_for_managed_sender(self):
        data=json.loads(SENDERS.read_text()); data['enabled']=False
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'senders.json'; p.write_text(json.dumps(data))
            r=runtime.RuntimeOpenPGPResolver(POLICY,p)
            with self.assertRaises(runtime.OpenPGPOutboundRuntimeError):
                r({'from_address':'john@ww.cx','recipients':['recipient@example.net']})
if __name__=='__main__': unittest.main()
