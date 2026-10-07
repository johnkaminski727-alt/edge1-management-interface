import importlib.util, sqlite3, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(name, rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
filing=load('document_filing_bot_test','tools/automation/document_filing_bot.py')
backup=load('backup_verification_bot_test','tools/automation/backup_verification_bot.py')
actions=load('outstanding_actions_bot_test','tools/automation/outstanding_actions_bot.py')

class Wave1Tests(unittest.TestCase):
    def test_document_classification_and_metadata(self):
        text='Invoice Number: INV-1047\nAmount Due: $1,234.50\nDue Date: October 30, 2026\n'
        self.assertEqual(filing.classify('vendor-invoice.pdf',text),'invoice')
        meta=filing.metadata('invoice',text)
        self.assertEqual(meta['invoice_number'],'INV-1047')
        self.assertEqual(meta['amount'],'1,234.50')
    def test_general_document_stays_general(self):
        self.assertEqual(filing.classify('notes.txt','ordinary notes without business markers'),'general')
    def test_calendar_attachment_precedes_invoice_keywords(self):
        self.assertEqual(filing.classify('invite.ics','BEGIN:VCALENDAR\nInvoice Number: INV-1'),'calendar')
    def test_database_integrity_check_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.sqlite'; db=sqlite3.connect(p); db.execute('create table t(x)'); db.execute('insert into t values (1)'); db.commit(); db.close()
            self.assertEqual(backup.dbcheck(p)['state'],'ok')
            self.assertEqual(sqlite3.connect(p).execute('select count(*) from t').fetchone()[0],1)
    def test_subject_normalization_collapses_reply_prefixes(self):
        self.assertEqual(actions.normalized_subject(' Re: FWD: Your library request is ready! '),'your library request is ready')
    def test_outbound_check_is_commissioning_language(self):
        source=(ROOT/'tools/automation/outstanding_actions_bot.py').read_text()
        self.assertIn("'outbound check'",source)
    def test_action_markdown_declares_advisory_boundary(self):
        data={'generated_at':'x','summary':{'total':0,'high':0,'medium':0,'low':0},'actions':[]}
        text=actions.markdown(data)
        self.assertIn('advisory',text)
        self.assertIn('does not send messages',text)

if __name__=='__main__': unittest.main()
