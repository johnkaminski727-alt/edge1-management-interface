import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'src/web/contacts/index.html').read_text()
APP = (ROOT / 'src/web/contacts/app.js').read_text()
CSS = (ROOT / 'src/web/contacts/styles.css').read_text()


class UnifiedContactsMaintenanceUiTests(unittest.TestCase):
    def test_maintenance_tab_and_metrics_exist(self):
        self.assertIn('data-view="maintenance"', HTML)
        self.assertIn('metric-maintenance-review', HTML)
        self.assertIn('metric-identity-jobs', HTML)
        self.assertIn('metric-duplicate-risks', HTML)
        self.assertIn('metric-missing-sources', HTML)
        self.assertIn('metric-validation-issues', HTML)
        self.assertIn('metric-enrichment-backlog', HTML)
        self.assertIn('metric-last-maintenance', HTML)
        self.assertIn('id="maintenance-kind"', HTML)
        self.assertIn('Identity resolution', HTML)
        self.assertIn('Contact discoveries', HTML)
        self.assertIn('Candidate changes', HTML)

    def test_read_only_maintenance_api_is_used(self):
        self.assertIn('/api/contacts/maintenance-summary', APP)
        self.assertIn('/api/contacts/maintenance?', APP)

    def test_operator_actions_are_safe_workflow_actions(self):
        self.assertIn('data-maintenance-action="find-match"', APP)
        self.assertIn('data-maintenance-action="open-contact"', APP)
        self.assertIn('data-maintenance-action="create-contact"', APP)
        self.assertIn('Search and reconcile against existing canonical contacts before creating', APP)

    def test_create_from_identity_job_prefills_phone(self):
        self.assertIn('initial_point_type', APP)
        self.assertIn('button.dataset.maintenanceValue', APP)
        self.assertIn('button.dataset.maintenancePointType', APP)
        self.assertIn('Created from Contacts maintenance identity-resolution review', APP)

    def test_contact_editor_uses_current_render_path(self):
        self.assertNotIn('renderContactManager', APP)
        self.assertIn('await renderDetail(selected);', APP)

    def test_maintenance_styles_exist(self):
        self.assertIn('.maintenance-review-card', CSS)
        self.assertIn('.maintenance-actions', CSS)


if __name__ == '__main__':
    unittest.main()
