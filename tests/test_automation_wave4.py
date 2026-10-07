import importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n,p):
 spec=importlib.util.spec_from_file_location(n,ROOT/p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
common=load('public_web_common_test','tools/automation/public_web_common.py')
class Wave4Tests(unittest.TestCase):
 def test_html_metadata_parser(self):
  x=common.parse_html('<html><head><title> Hello </title><meta name="description" content="Desc"><meta property="og:title" content="OG"><link rel="canonical" href="https://example.test/x"><link rel="icon" href="/favicon.ico"><script type="application/ld+json">{}</script></head></html>')
  self.assertEqual(x['title'],'Hello');self.assertEqual(x['description'],'Desc');self.assertEqual(x['og_title'],'OG');self.assertEqual(x['jsonld_blocks'],1)
 def test_sitemap_parser(self):
  locs,kind=common._locs(b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/a</loc></url></urlset>')
  self.assertEqual(kind,'urlset');self.assertEqual(locs,['https://example.test/a'])
 def test_config_is_https_only(self):
  sites=common.load_sites(ROOT/'config/automation/public-websites.json');self.assertEqual(len(sites),5);self.assertTrue(all(x['base_url'].startswith('https://') for x in sites))
if __name__=='__main__':unittest.main()
