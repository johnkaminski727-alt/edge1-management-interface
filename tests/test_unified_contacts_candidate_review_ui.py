import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (
    ROOT / "src/web/contacts/app.js"
).read_text()
CSS = (
    ROOT / "src/web/contacts/styles.css"
).read_text()


class CandidateReviewUiTests(unittest.TestCase):
    def test_uses_existing_edge1_csrf_cookie(self):
        self.assertIn(
            "__Secure-wwcx_edge1_ops_csrf",
            APP,
        )
        self.assertIn("X-WWCX-CSRF", APP)

    def test_browser_contains_no_operations_hmac(self):
        for forbidden in (
            "X-WWCX-Signature",
            "X-WWCX-Nonce",
            "operations_api_secret",
            "EDGE1_OPS_SECRET",
        ):
            self.assertNotIn(forbidden, APP)

    def test_candidate_actions_are_accept_reject_only(self):
        self.assertIn(
            'data-correlation-action="accept"',
            APP,
        )
        self.assertIn(
            'data-correlation-action="reject"',
            APP,
        )

    def test_candidate_copy_preserves_identity_boundary(self):
        self.assertIn(
            "does not merge identities",
            APP,
        )

    def test_promote_is_not_browser_button_yet(self):
        self.assertNotIn(
            'data-correlation-action="promote"',
            APP,
        )

    def test_review_style_exists(self):
        self.assertIn(
            ".correlation-review",
            CSS,
        )


if __name__ == "__main__":
    unittest.main()
