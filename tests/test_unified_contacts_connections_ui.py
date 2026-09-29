import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (
    ROOT / "src/web/contacts/index.html"
).read_text()
JS = (
    ROOT / "src/web/contacts/app.js"
).read_text()
CSS = (
    ROOT / "src/web/contacts/styles.css"
).read_text()


class ConnectionsUiTests(unittest.TestCase):

    def test_connections_view_exists(self):
        self.assertIn(
            'data-view="connections"',
            HTML,
        )
        self.assertIn(
            'connections: "Connections"',
            JS,
        )

    def test_read_routes_are_used(self):
        self.assertIn(
            "/api/contacts/relationships?",
            JS,
        )
        self.assertIn(
            "/api/contacts/relationship-evidence?",
            JS,
        )
        self.assertIn(
            "/api/contacts/correlations?",
            JS,
        )

    def test_no_mutation_routes_or_controls(self):
        forbidden = (
            "/correlations/accept",
            "/correlations/reject",
            "/correlations/promote",
            "Accept candidate",
            "Reject candidate",
            "Promote candidate",
        )

        for value in forbidden:
            self.assertNotIn(value, HTML)
            self.assertNotIn(value, JS)

    def test_semantic_separation_is_visible(self):
        self.assertIn(
            "Established relationship",
            JS,
        )
        self.assertIn(
            "Candidate correlation",
            JS,
        )
        self.assertIn(
            "This is a review candidate, not an established ",
            JS,
        )
        self.assertIn(
            "relationship or identity assertion.",
            JS,
        )

    def test_connections_styles_exist(self):
        self.assertIn(
            ".relationship-result",
            CSS,
        )
        self.assertIn(
            ".correlation-result",
            CSS,
        )


if __name__ == "__main__":
    unittest.main()
