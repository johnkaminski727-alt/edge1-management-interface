import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'tools/messaging/gmail_mail_import.py'
spec=importlib.util.spec_from_file_location('gmail_mail_import',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class GmailMailImportTests(unittest.TestCase):
    def test_scope_is_read_only(self):
        self.assertEqual(m.SCOPE,'https://www.googleapis.com/auth/gmail.readonly')
        self.assertNotIn('modify',m.SCOPE);self.assertNotIn('send',m.SCOPE)
    def test_source_is_per_account(self):
        self.assertEqual(m.source_id('Example.User@gmail.com'),'gmail-google-api-example-user-gmail-com')
    def test_folder_classification(self):
        self.assertEqual(m.classify(['INBOX']),('inbox','inbound'))
        self.assertEqual(m.classify(['SENT']),('sent','outbound'))
        self.assertEqual(m.classify(['SPAM']),('junk','inbound'))
        self.assertEqual(m.classify(['IMPORTANT']),('archive','inbound'))
        self.assertEqual(m.classify(['TRASH']),('excluded','inbound'))
        self.assertEqual(m.classify(['DRAFT']),('excluded','inbound'))
    def test_history_ids_deduplicate(self):
        p={'history':[{'messagesAdded':[{'message':{'id':'a'}}],'labelsAdded':[{'message':{'id':'a'}},{'message':{'id':'b'}}]}]}
        self.assertEqual(m.history_ids(p),['a','b'])
    def test_synthetic_id_is_canonical(self):
        self.assertTrue(m.canonical_mid('<gmail-'+'a'*64+'@archive.ww.cx>'))
if __name__=='__main__':unittest.main()
