import copy, hashlib, json, pathlib, sys, tempfile, subprocess, unittest
from unittest import mock
from email import policy
from email.parser import BytesParser
ROOT=pathlib.Path(__file__).resolve().parents[1]
SERVER=ROOT/'server'
if str(SERVER) not in sys.path: sys.path.insert(0,str(SERVER))
import identity_aware_outbound_gateway as gateway
import mail_openpgp_outbound_runtime as pgp_runtime
import mail_openpgp_socket_adapter
import mail_secure_submission
import outbound_mail_gateway
import outbound_mail_policy

class TestSigningIntegration(unittest.TestCase):
    def test_provider_bound_message_is_valid_pgp_mime_signed(self):
        cfg=json.loads((ROOT/'config/messaging/outbound-mail-gateway.json').read_text())
        cfg['enabled']=True; cfg['deployment_authorized']=True; cfg['external_delivery_authorized']=True
        cfg['admin']['send_endpoint_enabled']=True; cfg['provider']['selected']='smtp_submission'; cfg['provider']['profiles']['smtp_submission']['enabled']=True
        outbound_mail_gateway.validate_gateway_config(cfg)
        base=json.loads((ROOT/'config/messaging/outbound-mail-policy.json').read_text())
        pol=outbound_mail_policy.activated_copy(base,'151 2 Street South, Invermay, SK')
        ids=json.loads((ROOT/'config/messaging/mail-identities.json').read_text())
        ids['outbound_activation_authorized']=True; ids['sender_selection']['live_sender_allowlist']=['john@ww.cx']
        payload={'to':'recipient@example.net','subject':'OpenPGP integration acceptance','body':'Synthetic acceptance message; not transmitted.','message_class':'business_correspondence','signer_name':'John Kaminski','signer_title':'Authorized Representative','mailing_address':'151 2 Street South, Invermay, SK','original_recipient':'john@ww.cx'}
        def scanner(raw):
            return {'contract':'wwcx.mail-final-scan.v1','state':'clean','engine':'synthetic-acceptance','engine_version':'1','ruleset_version':'acceptance-1','message_sha256':hashlib.sha256(raw).hexdigest(),'reason_codes':[]}
        captured={}
        def submit(_config,_preview,message_bytes,message_id):
            captured['raw']=message_bytes
            return {'provider':'capture','provider_type':'smtp','message_id':message_id,'recipient_count':1,'submitted_at':'2026-10-06T00:00:00+00:00'}
        resolver=pgp_runtime.RuntimeOpenPGPResolver(ROOT/'config/messaging/openpgp-policy.json',ROOT/'config/messaging/openpgp-outbound-senders.json')
        with mock.patch.object(mail_secure_submission,'_submit_smtp_message',side_effect=submit):
            result=gateway.send_message(cfg,pol,ids,payload,confirmation=True,final_scanner=scanner,openpgp_adapter=mail_openpgp_socket_adapter.transform,openpgp_request_resolver=resolver)
        raw=captured['raw']; msg=BytesParser(policy=policy.SMTP).parsebytes(raw)
        self.assertEqual(msg.get_content_type(),'multipart/signed')
        self.assertEqual(msg.get_param('protocol'),'application/pgp-signature')
        self.assertEqual(result['openpgp']['operation'],'sign')
        self.assertEqual(result['openpgp']['signing_fingerprint'],'316F9A96BCC1912631E98D6382A0ACB1EC85FBDF')
        parts=msg.get_payload(); self.assertEqual(len(parts),2)
        signed=parts[0].as_bytes(policy=policy.SMTP)
        sig=parts[1].get_payload().encode('ascii')
        with tempfile.TemporaryDirectory() as td:
            home=pathlib.Path(td)/'g'; home.mkdir(mode=0o700)
            pub=pathlib.Path('/var/www/edge1-status/openpgp/john-wwcx.asc')
            subprocess.run(['gpg','--batch','--homedir',str(home),'--import',str(pub)],check=True,capture_output=True)
            sp=pathlib.Path(td)/'signed.bin'; sg=pathlib.Path(td)/'sig.asc'; sp.write_bytes(signed); sg.write_bytes(sig)
            v=subprocess.run(['gpg','--batch','--homedir',str(home),'--verify',str(sg),str(sp)],capture_output=True,text=True)
            self.assertEqual(v.returncode,0,v.stderr)
if __name__=='__main__': unittest.main()
