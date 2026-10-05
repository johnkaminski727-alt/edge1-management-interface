#!/usr/bin/env python3
"""Live local-engine acceptance in disposable state; no delivery or AI calls."""
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from tools.messaging.mail_room_security_scan import inspect
from server.mail_room_security import SecurityStore
from mail_correspondence_store import MailCorrespondenceStore,CorrespondenceStoreError


def raw_message(label,body):
    m=EmailMessage();m['From']='Commissioning <commissioning@example.test>';m['To']='john@ww.cx';m['Subject']='Isolated security acceptance '+label;m['Message-ID']='<security-'+label+'@example.test>';m['Date']=datetime.now(timezone.utc);m.set_content(body);return m.as_bytes()


def main():
    gtube='XJS*C4JDBQADN1.NSBN3*2IDNEN*GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X'
    eicar='X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
    states={}
    with tempfile.TemporaryDirectory(prefix='mail-security-acceptance-') as temporary:
        root=Path(temporary);security=SecurityStore(root/'security'/'security.sqlite3')
        os.environ['WWCX_MAIL_SECURITY_REQUIRED']='true';os.environ['WWCX_MAIL_SECURITY_DATABASE']=str(security.path)
        writer=MailCorrespondenceStore(root/'mail'/'mail.sqlite3',source='isolated-security-acceptance',source_authoritative=True,source_scope='local_native')
        for label,body in [('clean','Harmless commissioning body for testing local release behavior.'),('spam',gtube),('eicar',eicar),('unavailable','Harmless body with a simulated scanner failure.')]:
            raw=raw_message(label,body)
            kwargs={'scan':lambda _: 'unscanned_blocked'} if label=='unavailable' else {}
            decision,_,_=inspect(raw,transport={'source':'postfix_pipe','client_ip':'127.0.0.1','envelope_sender':'commissioning@example.test'},policy_config={'junk_score':6,'quarantine_score':15},**kwargs)
            mid='<security-'+label+'@example.test>'
            security.write(mid,hashlib.sha256(raw).hexdigest(),decision)
            writer.ingest({'message_id':mid,'thread_id':'THREAD-SECURITY-ACCEPTANCE','direction':'inbound','sender':'commissioning@example.test','recipients':['john@ww.cx'],'subject':'Isolated acceptance','body_text':body,'references':[],'occurred_at':datetime.now(timezone.utc).isoformat()})
            states[label]=decision['state']
        assert states['clean']=='released',states
        assert states['spam'] in {'junk','quarantine'},states
        assert states['eicar']=='quarantine',states
        assert states['unavailable']=='pending',states
        reader=MailCorrespondenceStore(writer.path,source='acceptance-read',read_only=True)
        assert reader.search_authoritative()['count']==1
        assert reader.read_thread('THREAD-SECURITY-ACCEPTANCE')['count']==1
        security.action('<security-clean@example.test>','phishing',True)
        assert reader.search_authoritative()['count']==0
        try:reader.read_message('<security-clean@example.test>')
        except CorrespondenceStoreError:pass
        else:raise AssertionError('Reported phishing remained readable')
        for mid in ['<security-eicar@example.test>','<security-unavailable@example.test>']:
            try:security.action(mid,'release')
            except ValueError:pass
            else:raise AssertionError('Unsafe release succeeded')
        print(json.dumps({'acceptance':'passed','states':states,'reported_phishing_read_blocked':True,'malware_and_unscanned_release_blocked':True,'production_database_modified':False,'mail_sent':False,'ai_called':False}))

if __name__=='__main__':main()
