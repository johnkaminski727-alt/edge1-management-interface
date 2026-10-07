import importlib.util, json, sqlite3, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load():
    spec=importlib.util.spec_from_file_location('replybot',ROOT/'tools/automation/reply_suggestion_bot.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
class ReplySuggestionTests(unittest.TestCase):
    def test_private_state_schema_and_safety_contract(self):
        mod=load()
        with tempfile.TemporaryDirectory() as td:
            db=mod.open_state(Path(td)/'state.sqlite')
            cols={r[1] for r in db.execute('pragma table_info(suggestions)')}; db.close()
            self.assertIn('suggestion',cols); self.assertIn('content_sha',cols)
        text=(ROOT/'tools/automation/reply_suggestion_bot.py').read_text()
        self.assertIn("'send_authorized':False",text)
        self.assertIn("'draft_modified':False",text)
        self.assertNotIn('DraftStore',text)
    def test_library_copy_labels_review_only(self):
        mod=load(); row={'subject':'Question','sender':'person@example.test','evidence':'mail-room:message:abc','thread_evidence':'mail-room:thread:def','suggestion':'Suggested response','generated_at':'now'}
        text=mod.library_markdown([row])
        self.assertIn('review-only',text); self.assertIn('send_authorized=false',text); self.assertIn('Suggested response',text)
    def test_automated_sender_terms_are_excluded(self):
        mod=load(); self.assertIn('noreply',mod.AUTOMATED_LOCALPARTS); self.assertIn('mailer-daemon',mod.AUTOMATED_LOCALPARTS)
if __name__=='__main__': unittest.main()
