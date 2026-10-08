import unittest
from tools.automation.evidence_document_contact_extractor import sasktel_facts


class EvidenceDocumentContactExtractorTests(unittest.TestCase):
    def test_sasktel_role_sensitive_phone_extraction(self):
        pages=[(1, '''SaskTel Bill\nSales, service, support & billing inquiries 1 800 727-5835\nPhone numbers 306 593-0123\nSaskTel communication services\n''')]
        facts=sasktel_facts(pages)
        by_value={f['value']:f for f in facts}
        self.assertEqual(by_value['+18007275835']['kind'],'organization_phone')
        self.assertEqual(by_value['+18007275835']['organization'],'SaskTel')
        self.assertEqual(by_value['+13065930123']['kind'],'service_phone')
        self.assertNotIn('organization',by_value['+13065930123'])

    def test_independent_ccts_number_is_not_attributed_to_sasktel(self):
        pages=[(1, '''SaskTel Bill\nDo you have a complaint? Commission for Complaints for Telecom-television Services (CCTS) 1-888-221-1687.\n''')]
        values={f['value'] for f in sasktel_facts(pages)}
        self.assertNotIn('+18882211687',values)

    def test_duplicate_occurrences_are_collapsed(self):
        pages=[(1, '''Phone numbers 306 593-0123\n9-1-1 Call Taking Charge for 306 593-0123\n''')]
        facts=sasktel_facts(pages)
        self.assertEqual(sum(1 for f in facts if f['value']=='+13065930123'),1)


if __name__=='__main__': unittest.main()
