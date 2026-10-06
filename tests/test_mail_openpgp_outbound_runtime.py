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

    def test_encrypt_if_verified_key_resolves_only_when_explicitly_enabled(self):
        policy=json.loads(POLICY.read_text()); policy['outbound']['encrypt_enabled']=True
        senders=json.loads(SENDERS.read_text()); senders['senders']['john@ww.cx']['mode']='encrypt_if_verified_key'
        recipients={'contract':'wwcx.openpgp-recipient-keys.v1','private_key_material_included':False,'armored_public_key_material_included':False,'recipients':{'recipient@example.net':{'verification_status':'verified','primary_fingerprint':'E529012FC9B50FD2B8F2ADF0AAA57DEE473CF5AD','encryption_subkeys':[{'fingerprint':'8E5B8FAFE6B0F0027A26AE2E621A4633F624DE99','expires_unix':4102444800}]}}}
        with tempfile.TemporaryDirectory() as td:
            td=pathlib.Path(td); pp=td/'policy.json'; sp=td/'senders.json'; rp=td/'recipients.json'
            pp.write_text(json.dumps(policy)); sp.write_text(json.dumps(senders)); rp.write_text(json.dumps(recipients))
            r=runtime.RuntimeOpenPGPResolver(pp,sp,rp)
            out=r({'from_address':'john@ww.cx','recipients':['recipient@example.net']})
            self.assertEqual(out['operation'],'sign_encrypt')
            self.assertEqual(out['recipient_fingerprints'],['E529012FC9B50FD2B8F2ADF0AAA57DEE473CF5AD'])

if __name__=='__main__': unittest.main()
