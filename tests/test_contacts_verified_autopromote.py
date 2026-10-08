import sqlite3
import unittest

from tools.automation.contacts_verified_autopromote import (
    _existing_org_candidate,
    _proposed_org_candidate,
)


class VerifiedAutopromoteOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE mail_contact_extractions(
              id INTEGER PRIMARY KEY,
              message_id TEXT,
              security_state TEXT
            );
            CREATE TABLE mail_contact_candidates(
              id INTEGER PRIMARY KEY,
              extraction_id INTEGER,
              context TEXT
            );
        ''')

    def tearDown(self):
        self.db.close()

    def test_existing_verified_org_can_receive_domain_mailbox(self):
        row = {'id': 31, 'sender_domain': 'telus.com', 'message_count': 2}
        evidence = ('cartbilr@telus.com', {'message_ids': ['m1', 'm2']}, 'abc')
        orgs = [
            {'id': 67, 'canonical_name': 'TELUS Corporation', 'verification_status': 'document_sourced'},
        ]
        result = _existing_org_candidate(row, evidence, orgs)
        self.assertIsNotNone(result)
        self.assertEqual(result['existing_entity_id'], 67)
        self.assertEqual(result['canonical_name'], 'TELUS Corporation')

    def test_repeated_released_body_context_can_verify_org_name(self):
        for idx in (1, 2):
            self.db.execute(
                "INSERT INTO mail_contact_extractions VALUES(?,?, 'released')",
                (idx, f'm{idx}'),
            )
            self.db.execute(
                "INSERT INTO mail_contact_candidates VALUES(?,?,?)",
                (idx, idx, 'This email was sent by: Wild Birds Unlimited of Chilliwack, BC'),
            )
        row = {
            'id': 6,
            'proposed_entity_name': 'Wild Birds Unlimited',
            'message_count': 20,
        }
        evidence = (
            'chilliwackbc430@email.wbu.com',
            {'message_ids': ['m1', 'm2'], 'subjects': []},
            'def',
        )
        result = _proposed_org_candidate(row, evidence, self.db)
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_name'], 'Wild Birds Unlimited')

    def test_bad_subject_phrase_is_not_promoted_as_org(self):
        row = {
            'id': 41,
            'proposed_entity_name': 'Bandwidth is on the way',
            'message_count': 4,
        }
        evidence = (
            'team@bandwidth.com',
            {'message_ids': ['m1', 'm2'], 'subjects': ['Help from Bandwidth is on the way!']},
            'ghi',
        )
        self.assertIsNone(_proposed_org_candidate(row, evidence, self.db))


if __name__ == '__main__':
    unittest.main()
