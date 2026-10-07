import unittest
from tools.automation.catalog_consistency_bot import compare
class Wave7Tests(unittest.TestCase):
    def test_active_projection_matches(self):
        fallback={'currency':'CAD','store_mode':'live','version':'1','products':[{'id':'a','active':True,'name':'A','price':1},{'id':'b','active':False,'name':'B','price':2}]}
        live={'currency':'CAD','store_mode':'live','version':'1','products':[{'id':'a','name':'A','price':1}]}
        d=compare(live,fallback); self.assertEqual(d['state'],'healthy'); self.assertFalse(d['catalog_mutation_performed'])
    def test_inactive_product_leak_is_attention(self):
        fallback={'products':[{'id':'b','active':False}]}; live={'products':[{'id':'b'}]}
        d=compare(live,fallback); self.assertEqual(d['state'],'attention'); self.assertTrue(any(x['kind'] in {'inactive_product_leaked_live','unexpected_live_product'} for x in d['findings']))
    def test_no_store_mutation_paths(self):
        import pathlib
        text=(pathlib.Path(__file__).resolve().parents[1]/'tools/automation/catalog_consistency_bot.py').read_text()
        self.assertNotIn('stripe POST',text.lower()); self.assertNotIn('write_text(FALLBACK',text)
if __name__=='__main__':unittest.main()
