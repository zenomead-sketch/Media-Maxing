from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX = REPO_ROOT / "apps" / "web" / "index.html"
WEB_SCRIPT = REPO_ROOT / "apps" / "web" / "settings.js"
WEB_STYLES = REPO_ROOT / "apps" / "web" / "styles.css"


THEME_COLOR_SCHEMES = [
    "classic_blue",
    "forest_green",
    "sunrise_coral",
    "slate_violet",
    "teal_mint",
    "graphite_gold",
    "rose_plum",
    "sky_indigo",
    "olive_sage",
    "espresso_sand",
]


class WebSettingsScreenTest(unittest.TestCase):
    def test_settings_screen_contains_required_fields_and_adapter(self):
        html = WEB_INDEX.read_text(encoding="utf-8")
        script = WEB_SCRIPT.read_text(encoding="utf-8")

        required_ids = [
            "settings-view",
            "settings-form",
            "appName",
            "localDataDirectory",
            "defaultTimezone",
            "defaultPlatformTargets",
            "automationLevel",
            "requireApprovalBeforePublishing",
            "requireApprovalBeforeReplying",
            "emergencyPauseEnabled",
            "aiProviderPreference",
            "themeColorScheme",
            "themeColorSchemePreview",
            "settings-error",
            "settings-success",
        ]

        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', html)

        self.assertIn("Emergency pause", html)
        self.assertIn("Local settings adapter", html)
        self.assertIn("Local AI runtime, Ollama", html)
        self.assertIn("ENABLE_LOCAL_AI_CALLS=true", html)
        self.assertIn("OpenAI cloud API, later", html)
        self.assertIn("activeApiBridge", script)
        self.assertIn("persistThroughApi", script)
        self.assertIn("themeColorSchemes", script)
        self.assertIn("applyThemeColorScheme", script)
        self.assertIn("await persistThroughApi(\"/api/settings\"", script)
        self.assertIn("Settings saved to local SQLite.", script)
        self.assertIn("localStorage", script)
        self.assertIn("autonomous_content_engine", script)
        self.assertIn("approval before publishing", script)
        self.assertLess(
            script.index("function routeFromHash"),
            script.index("function setupRouting"),
        )

    def test_settings_screen_exposes_ten_color_schemes(self):
        html = WEB_INDEX.read_text(encoding="utf-8")
        script = WEB_SCRIPT.read_text(encoding="utf-8")
        styles = WEB_STYLES.read_text(encoding="utf-8")

        for theme_id in THEME_COLOR_SCHEMES:
            self.assertIn(f'value="{theme_id}"', html)
            self.assertIn(f'id: "{theme_id}"', script)
            self.assertIn(f'body[data-theme="{theme_id}"]', styles)

        theme_select = html.split('id="themeColorScheme"', 1)[1].split("</select>", 1)[0]
        self.assertEqual(theme_select.count("<option value="), 10)
        self.assertIn("Local Only: changes this app's appearance", html)
        self.assertIn("Unsupported color scheme", script)


if __name__ == "__main__":
    unittest.main()
