from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
README = REPO_ROOT / "README.md"


class Batch7CloseoutDocsTest(unittest.TestCase):
    def test_batch7_owner_guides_exist_and_keep_sources_clear(self):
        guides = {
            "manual-analytics-entry.md": (
                "source = manual",
                "duplicate",
                "Analytics",
            ),
            "mock-analytics.md": (
                "fake",
                "source = mock",
                "Generate mock analytics",
            ),
        }

        for filename, required_text in guides.items():
            with self.subTest(filename=filename):
                content = (DOCS / filename).read_text(encoding="utf-8")
                for phrase in required_text:
                    self.assertIn(phrase, content)

    def test_readme_links_every_batch7_owner_guide(self):
        readme = README.read_text(encoding="utf-8")

        for filename in (
            "analytics.md",
            "manual-analytics-entry.md",
            "mock-analytics.md",
            "engagement-inbox.md",
            "reply-suggestions.md",
            "reply-approval-workflow.md",
            "ai-learning-loop.md",
            "weekly-reports.md",
            "batch7-local-workflow.md",
        ):
            with self.subTest(filename=filename):
                self.assertIn(f"`docs/{filename}`", readme)

    def test_local_workflow_guide_covers_the_review_required_chain(self):
        workflow = (DOCS / "batch7-local-workflow.md").read_text(encoding="utf-8")

        for phrase in (
            "manual export",
            "manual analytics",
            "Generate mock engagement",
            "Approve Locally",
            "weekly report",
            "No external reply is sent",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, workflow)


if __name__ == "__main__":
    unittest.main()
