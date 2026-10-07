import unittest
from tools.automation.contact_enrichment_research_bot import allowed_host, clean_text, extract_page, choose, relevant_name

class ContactEnrichmentResearchTests(unittest.TestCase):
    def test_first_party_host_boundary(self):
        self.assertTrue(allowed_host('example.com','example.com'))
        self.assertTrue(allowed_host('www.example.com','example.com'))
        self.assertFalse(allowed_host('api.example.com','example.com'))
        self.assertFalse(allowed_host('example.net','example.com'))

    def test_html_extraction_is_contact_fact_only(self):
        raw='<html><title>Example Clinic</title><body>Example Clinic Contact us info@example.com or +1 (306) 555-1212. Box 3, Regina SK S4P 3Y2<script>evil@example.com</script></body></html>'
        page=extract_page(raw,'https://example.com/contact','example.com')
        self.assertIn('info@example.com',page['emails'])
        self.assertIn('+13065551212',page['phones'])
        self.assertIn('S4P3Y2',page['postals'])
        self.assertNotIn('evil@example.com',page['emails'])

    def test_unique_contact_page_candidate_can_be_staged(self):
        page={'name_relevant':True,'phones':{'+13065551212'},'emails':set(),'postals':{},'url':'https://example.com/contact','text':'Example Clinic'}
        result=choose('find_phone',[page],'example.com','Example Clinic')
        self.assertEqual(result['value'],'+13065551212')
        self.assertEqual(result['confidence'],'first_party_public')

    def test_ambiguous_contact_page_does_not_stage(self):
        page={'name_relevant':True,'phones':{'+13065551212','+13065551213'},'emails':set(),'postals':{},'url':'https://example.com/contact','text':'Example Clinic'}
        self.assertIsNone(choose('find_phone',[page],'example.com','Example Clinic'))

    def test_name_relevance_requires_entity_signal(self):
        self.assertTrue(relevant_name('Welcome to Example Clinic','Example Clinic'))
        self.assertFalse(relevant_name('Unrelated company','Example Clinic'))

if __name__=='__main__': unittest.main()
