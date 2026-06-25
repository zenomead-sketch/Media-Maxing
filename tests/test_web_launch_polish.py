import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "apps" / "web" / "index.html").read_text()
CSS = (ROOT / "apps" / "web" / "styles.css").read_text()
SETTINGS_JS = (ROOT / "apps" / "web" / "settings.js").read_text()


class WebLaunchPolishTests(unittest.TestCase):
    def test_navigation_uses_user_facing_terms_from_docs(self):
        expected_labels = [
            "Control Center",
            "Intro Setup Guide",
            "Onboarding",
            "Media Library",
            "Generate",
            "Drafts",
            "Calendar",
            "Publish Queue",
            "Connected Accounts",
            "Social Integration Setup",
            "Analytics",
            "Engagement Inbox",
            "Brand Brain",
            "Settings",
            "Safety Center",
            "Backup & Data",
            "Diagnostics",
        ]
        for label in expected_labels:
            self.assertRegex(
                HTML,
                rf'<a class="[^"]*nav-link[^"]*" href="#[^"]+"[^>]*>{re.escape(label)}</a>',
                label,
            )
        self.assertIn("<summary>Daily Workflow</summary>", HTML)
        self.assertIn("<summary>Setup</summary>", HTML)
        self.assertIn("<summary>Advanced Tools</summary>", HTML)
        self.assertNotIn('href="#engagement">Engagement</a>', HTML)
        self.assertIn('<h1>Diagnostics</h1>', HTML)

    def test_home_primary_actions_are_real_routes_with_clear_labels(self):
        self.assertIn('<h1>Control Center</h1>', HTML)
        self.assertIn('id="control-next-action" href="#generate"', HTML)
        self.assertIn('href="#drafts"', HTML)
        self.assertIn("What should I do next?", HTML)
        self.assertIn('href="#guide"', HTML)
        self.assertIn("<h1>Intro Setup Guide</h1>", HTML)
        self.assertIn('id="simple-mode-toggle"', HTML)
        self.assertIn('id="facebook-readiness-panel"', HTML)
        self.assertIn("Facebook posting setup", HTML)
        self.assertIn("Create media post", HTML)
        self.assertIn("Owner Mode", HTML)
        self.assertIn("Plug-and-play path", HTML)
        self.assertIn("getFacebookReadiness", SETTINGS_JS)
        self.assertIn("renderFacebookReadiness", SETTINGS_JS)
        self.assertIn("local-social-ai-manager.simpleMode", SETTINGS_JS)
        self.assertIn(".simple-mode", CSS)

    def test_accessibility_basics_are_present_for_launch(self):
        self.assertIn('class="skip-link" href="#app-main"', HTML)
        self.assertIn('<main class="main-content" id="app-main" tabindex="-1">', HTML)
        self.assertIn('aria-describedby="generate-error"', HTML)
        self.assertIn('aria-describedby="analytics-manual-error"', HTML)
        self.assertIn('aria-describedby="engagement-action-error"', HTML)
        self.assertIn(":focus-visible", CSS)

    def test_all_route_views_have_consistent_headers_and_safety_language(self):
        route_sections = re.findall(
            r'<section class="route-view[^"]*" id="([^"]+)" data-route="([^"]+)"',
            HTML,
        )
        self.assertGreaterEqual(len(route_sections), 16)
        for view_id, route in route_sections:
            with self.subTest(route=route):
                section_start = HTML.index(f'id="{view_id}"')
                section_end = HTML.find('<section class="route-view"', section_start + 1)
                section = HTML[section_start : section_end if section_end != -1 else len(HTML)]
                self.assertRegex(section, r'<header class="[^"]*\btopbar\b[^"]*">')
                self.assertIn("<h1>", section)
        self.assertIn("Real publishing disabled", HTML)
        self.assertIn("Replies are not sent automatically", HTML)
        self.assertIn("Local Only", HTML)
        self.assertIn("Mock Data", HTML)
        self.assertIn("Approval Required", HTML)
        self.assertIn("Weekly reports", HTML)
        self.assertIn("Active AI memory", HTML)

    def test_responsive_and_overflow_guards_exist(self):
        self.assertRegex(CSS, r"@media \(max-width: 900px\)[\s\S]*\.app-shell")
        self.assertRegex(CSS, r"@media \(max-width: 720px\)[\s\S]*\.topbar")
        self.assertIn("overflow-wrap: anywhere", CSS)
        self.assertIn("overflow-x: auto", CSS)
        self.assertIn(".platform-badge", CSS)
        self.assertIn(".status-badge", CSS)
        self.assertIn(".control-summary-grid", CSS)
        self.assertIn(".nav-group", CSS)
        self.assertIn("table-scroll-hint", HTML)
        self.assertIn('aria-label="Scrollable platform metrics table"', HTML)
        self.assertIn("-webkit-overflow-scrolling: touch", CSS)

    def test_dangerous_actions_keep_confirmation_messages(self):
        confirmations = [
            "Skip onboarding?",
            "Disconnect this mock account locally?",
            "Cancel this local queue item?",
            "Cancel this scheduled post locally?",
        ]
        for message in confirmations:
            self.assertIn(message, SETTINGS_JS)


if __name__ == "__main__":
    unittest.main()
