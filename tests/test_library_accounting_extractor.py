import unittest

from tools.automation import library_accounting_extractor as mod


class LibraryAccountingExtractorTests(unittest.TestCase):
    def test_sasktel_bill_extracts_document_sourced_accounting_facts(self):
        row = {
            'title': '2023-11-10 - SaskTel - Residential Telephone and Internet Services Bill.pdf',
            'item_type': 'telecom-bill',
        }
        text = '''
        SaskTel Bill
        Account number: 9576429-6
        Totalamount due as ofthebilldate $387.83
        Regina, SK
        '''
        facts = mod.extract_facts(row, text)
        self.assertEqual(facts['vendor_name'], 'SaskTel')
        self.assertEqual(facts['document_kind'], 'bill')
        self.assertEqual(facts['issue_date'], '2023-11-10')
        self.assertEqual(facts['account_reference'], '9576429-6')
        self.assertEqual(facts['currency'], 'CAD')
        self.assertEqual(facts['total_amount'], '387.83')
        self.assertEqual(facts['balance_due'], '387.83')
        self.assertEqual(facts['review_status'], 'staged')

    def test_register_text_is_not_accounting_document(self):
        row = {'title': 'Edge1 Contacts Source Registry', 'item_type': 'contact-register'}
        facts = mod.extract_facts(row, '{"contract":"edge1.contacts-source-registry.v1"}')
        self.assertIsNone(facts)

    def test_mobility_statement_classification(self):
        self.assertEqual(
            mod.infer_kind('2026-05-28 - SaskTel Mobility - Monthly Statement.pdf', 'telecom-statement', 'SaskTel Mobility'),
            'telecom_statement',
        )


if __name__ == '__main__':
    unittest.main()
