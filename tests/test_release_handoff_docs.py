from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class ReleaseHandoffDocumentationTests(unittest.TestCase):
    REQUIRED_FILES = {
        "CHANGELOG.md": [
            "Brand Brain",
            "Media Library",
            "AI mock generation",
            "Draft approvals",
            "Calendar",
            "Publish Queue",
            "Manual Export",
            "Connector scaffolding",
            "Connected Accounts mock mode",
            "Analytics",
            "Engagement Inbox",
            "Reply suggestions",
            "AI learning loop",
            "Safety Center",
            "Backup and Diagnostics",
            "Desktop packaging prep",
        ],
        "RELEASE_NOTES.md": [
            "local test release",
            "Who it is for",
            "What works",
            "Mock/demo only",
            "Local-only",
            "Not implemented yet",
            "How to run it",
            "Safety notes",
            "Known risks",
        ],
        "TODO.md": [
            "Critical before real users",
            "Important before real publishing",
            "Nice to have",
            "Research needed",
            "Platform API verification",
            "Security hardening",
            "UX improvements",
            "Desktop packaging",
        ],
        "VERSION": ["0.1.0-local-test"],
    }

    REQUIRED_DOCS = {
        "handoff-summary.md": [
            "Project purpose",
            "Architecture summary",
            "Tech stack",
            "App modules",
            "Data storage",
            "Safety model",
            "AI model/provider model",
            "Social connector model",
            "Current limitations",
            "How to continue development",
            "Where important files live",
            "Commands to know",
        ],
        "next-build-plan.md": [
            "Track A",
            "Real Meta OAuth and account discovery",
            "Track B",
            "Real publishing for one platform",
            "Track C",
            "Better AI generation and image/video analysis",
            "Track D",
            "Cloud sync or multi-device/team mode",
            "Acceptance criteria",
        ],
        "known-limitations.md": [
            "Real publishing disabled",
            "Real analytics are not fetched by default",
            "Real comments are not fetched by default",
            "Real replies are not sent",
            "Platform limits require verification",
            "OAuth requires real developer app setup later",
            "Token storage",
            "Desktop packaging",
            "Local scheduling only works while app/backend is running",
        ],
        "future-real-publishing-plan.md": [
            "one platform at a time",
            "Required safety gates",
            "OAuth/token hardening",
            "platform API verification",
            "app review",
            "user approval",
            "preflight",
            "post-publish audit log",
            "rollback/error handling",
            "rate limit handling",
            "Autonomous publishing should wait",
        ],
    }

    def test_release_handoff_files_exist_and_cover_required_topics(self) -> None:
        for file_name, phrases in self.REQUIRED_FILES.items():
            with self.subTest(file=file_name):
                path = ROOT / file_name
                self.assertTrue(path.exists(), file_name)
                text = path.read_text(encoding="utf-8")
                for phrase in phrases:
                    self.assertIn(phrase, text)
                if file_name != "VERSION":
                    self.assertIn("real publishing", text.lower())

        for file_name, phrases in self.REQUIRED_DOCS.items():
            with self.subTest(file=file_name):
                path = DOCS / file_name
                self.assertTrue(path.exists(), file_name)
                text = path.read_text(encoding="utf-8")
                for phrase in phrases:
                    self.assertIn(phrase, text)
                self.assertIn("local-first", text.lower())

    def test_readme_points_to_final_handoff_package_and_launch_check(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "0.1.0-local-test",
            "Launch candidate status",
            "docs/handoff-summary.md",
            "docs/next-build-plan.md",
            "docs/known-limitations.md",
            "docs/future-real-publishing-plan.md",
            "docs/launch-candidate-checklist.md",
            "python -m scripts.launch_check",
            "Real publishing remains disabled",
        ):
            self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
