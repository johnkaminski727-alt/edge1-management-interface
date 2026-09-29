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


    def test_candidate_review_controls_preserve_browser_boundary(self):
        self.assertIn(
            'data-correlation-action="accept"',
            JS,
        )
        self.assertIn(
            'data-correlation-action="reject"',
            JS,
        )

        # Promotion remains deliberately unavailable as a
        # browser control until provenance selection is built.
        self.assertNotIn(
            'data-correlation-action="promote"',
            JS,
        )

        # Browser code uses the authenticated Edge1 session
        # and CSRF token. It must never contain Operations
        # HMAC material.
        for forbidden in (
            "X-WWCX-Signature",
            "X-WWCX-Nonce",
            "operations_api_secret",
            "EDGE1_OPS_SECRET",
        ):
            self.assertNotIn(forbidden, JS)


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
