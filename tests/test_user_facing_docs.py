import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class UserFacingDocumentationTests(unittest.TestCase):
    REQUIRED_DOCS = {
        "intro-setup-guide.md": [
            "Start the App",
            "Complete Onboarding",
            "Create Brand Brain",
            "Upload or Import Media",
            "Choose Social Platforms",
            "mock connect",
            "Generate Drafts",
            "Review and Approve Drafts",
            "Schedule and Export Manually",
            "Track Analytics and Engagement",
            "Protect the App",
            "Real publishing",
            "Manual Export",
        ],
        "user-guide.md": [
            "What the app does",
            "local-first",
            "Home screen",
            "Intro Setup Guide",
            "Brand Brain",
            "Media Library",
            "Generate",
            "Drafts",
            "Calendar",
            "Publish Queue",
            "Manual Export",
            "Analytics",
            "Engagement Inbox",
            "Settings",
            "Safety Center",
            "Backup and Data",
            "Diagnostics",
            "Real publishing is disabled",
        ],
        "non-coder-setup.md": [
            ".env.example",
            "copy",
            "seed demo data",
            "mock mode",
            "Do not commit",
            "What not to touch",
            "ask Claude Code or Codex",
            "python -m apps.api.local_server --database data/app.sqlite --port 8000",
        ],
        "operator-manual.md": [
            "Daily workflow",
            "Weekly workflow",
            "Monthly workflow",
            "review drafts",
            "schedule posts",
            "manually export",
            "enter analytics",
            "review engagement",
            "weekly reports",
            "back up",
            "emergency pause",
        ],
        "common-workflows.md": [
            "Create a Brand Brain",
            "Upload job photos",
            "Generate post drafts",
            "Approve a draft",
            "Schedule a post",
            "Export a manual posting package",
            "Mark a post manually exported",
            "Enter analytics manually",
            "Generate mock analytics",
            "Review content insights",
            "Generate mock engagement",
            "Generate and approve a reply suggestion",
            "Create a weekly report",
            "Back up app data",
            "Use emergency pause",
        ],
        "troubleshooting.md": [
            "App will not start",
            "Database error",
            "Missing local data directory",
            "Media upload fails",
            "AI generation fails",
            "Mock provider not working",
            "Draft will not schedule",
            "Queue item is blocked",
            "Manual export fails",
            "Analytics are empty",
            "Engagement inbox is empty",
            "Connected account setup is missing",
            "OAuth callback fails",
            "Emergency pause blocks actions",
            "Desktop build fails",
            "export diagnostics",
        ],
        "privacy-and-local-data.md": [
            "stored locally",
            "Where data is stored",
            "What can be backed up",
            "excluded from backups",
            "API keys",
            "tokens",
            "mock data",
            "AI providers in the future",
            "customer info",
        ],
        "safety-controls.md": [
            "Approval required",
            "Emergency pause",
            "Kill switch",
            "Automation levels",
            "Safety flags",
            "Reply approval",
            "Real publishing disabled",
            "Manual export fallback",
            "The AI should never",
        ],
        "glossary.md": [
            "Brand Brain",
            "Media Asset",
            "Generated Draft",
            "Approval Queue",
            "Scheduled Post",
            "Publish Queue",
            "Preflight",
            "Manual Export",
            "Mock Publish",
            "Engagement Item",
            "Reply Suggestion",
            "AI Memory",
            "Weekly Report",
            "Emergency Pause",
            "Connector",
            "OAuth",
            "Token",
            "Local-first",
        ],
    }

    def test_required_user_docs_exist_and_cover_plain_language_topics(self):
        for file_name, phrases in self.REQUIRED_DOCS.items():
            with self.subTest(file_name=file_name):
                path = DOCS / file_name
                self.assertTrue(path.exists(), file_name)
                text = path.read_text()
                self.assertLess(text.count("```"), 8, "docs should avoid heavy code blocks")
                for phrase in phrases:
                    self.assertIn(phrase, text)
                self.assertIn("real publishing", text.lower())
                self.assertNotRegex(text, r"sk-[A-Za-z0-9]{20,}")

    def test_readme_links_to_user_facing_docs(self):
        readme = (ROOT / "README.md").read_text()
        for file_name in self.REQUIRED_DOCS:
            self.assertIn(f"docs/{file_name}", readme)

    def test_docs_use_current_real_commands_not_nonexistent_package_scripts(self):
        command_docs = [
            "non-coder-setup.md",
            "operator-manual.md",
            "common-workflows.md",
            "troubleshooting.md",
        ]
        for file_name in command_docs:
            text = (DOCS / file_name).read_text()
            self.assertIn("python -m apps.api.local_server", text)
            self.assertNotIn("npm run dev", text)


if __name__ == "__main__":
    unittest.main()
