import importlib.util
import unittest
from email.message import EmailMessage
from pathlib import Path

MODULE = Path(__file__).parents[1] / 'tools/messaging/outlook_graph_mail_import.py'
spec = importlib.util.spec_from_file_location('outlook_graph_mail_import', MODULE)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def raw(mid='<x@example.test>', html=False):
    m=EmailMessage();m['From']='sender@example.test';m['To']='spiritcreekgardens@outlook.com';m['Subject']='hello';m['Date']='Thu, 08 Oct 2026 07:00:00 +0000';m['Message-ID']=mid
    if html: m.set_content('<p>Hello <b>there</b></p>',subtype='html')
    else: m.set_content('hello there')
    return m.as_bytes()


class OutlookGraphMailImportTests(unittest.TestCase):
    def test_projection_preserves_identity_and_direction_fields(self):
        projected=mod.build_projection(raw(), {'subject':'hello'}, 'inbound', '<x@example.test>')
        text=projected.decode('utf-8','replace')
        self.assertIn('Message-ID: <x@example.test>',text)
        self.assertIn('spiritcreekgardens@outlook.com',text)
        self.assertIn('hello there',text)

    def test_synthetic_security_copy_keeps_original_bytes_embedded(self):
        original=raw(mid='<x@example.test>')
        synthetic='<outlook-'+'a'*64+'@archive.ww.cx>'
        secured=mod.security_bytes(original,synthetic)
        self.assertNotEqual(secured,original)
        self.assertTrue(secured.startswith(('Message-ID: '+synthetic).encode()))
        self.assertIn(original,secured)

    def test_target_folders_exclude_deleted_items_and_preserve_direction(self):
        self.assertEqual(set(mod.FOLDERS),{'inbox','sent','archive','junk'})
        self.assertNotIn('deleteditems',{v['well_known'] for v in mod.FOLDERS.values()})
        self.assertEqual(mod.FOLDERS['sent']['direction'],'outbound')
        self.assertEqual(mod.FOLDERS['junk']['class'],'junk')

    def test_scopes_are_read_only(self):
        self.assertIn('Mail.Read',mod.SCOPES)
        self.assertNotIn('Mail.ReadWrite',mod.SCOPES)
        self.assertNotIn('Mail.Send',mod.SCOPES)

    def test_canonical_message_id_validation(self):
        self.assertTrue(mod.canonical_mid('<one@example.test>'))
        self.assertFalse(mod.canonical_mid('one@example.test'))
        self.assertFalse(mod.canonical_mid('<bad value@example.test>'))


if __name__=='__main__': unittest.main()
