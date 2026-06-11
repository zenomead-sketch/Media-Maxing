import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopPackagingReadinessTests(unittest.TestCase):
    def test_desktop_manifest_documents_safe_dependency_free_path(self):
        manifest_path = ROOT / "apps" / "desktop" / "desktop-readiness.json"
        self.assertTrue(manifest_path.exists())

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["appName"], "Local Social AI Manager")
        self.assertEqual(manifest["packagingDecision"], "tauri_preferred_not_installed")
        self.assertEqual(manifest["devCommand"], "python -m scripts.desktop.launcher --dev")
        self.assertEqual(manifest["buildCommand"], "python -m scripts.desktop.launcher --check")
        self.assertFalse(manifest["realPublishingEnabled"])
        self.assertFalse(manifest["realReplySendingEnabled"])
        self.assertEqual(manifest["networkBoundary"], "loopback_only")
        self.assertIn("context_isolation_required", manifest["futureSecurityRequirements"])
        self.assertIn("least_privilege_filesystem", manifest["futureSecurityRequirements"])

    def test_desktop_launcher_exposes_safe_check_without_starting_server(self):
        from scripts.desktop.launcher import desktop_readiness_check

        result = desktop_readiness_check()

        self.assertEqual(result["status"], "ready_for_native_wrapper")
        self.assertEqual(result["host"], "127.0.0.1")
        self.assertEqual(result["url"], "http://127.0.0.1:8000")
        self.assertFalse(result["realPublishingEnabled"])
        self.assertFalse(result["realReplySendingEnabled"])
        self.assertIn("python -m apps.api.local_server --host 127.0.0.1 --port 8000", result["localServerCommand"])
        self.assertIn("Tauri is preferred", result["packagingNotes"])

    def test_desktop_docs_explain_commands_and_limitations(self):
        docs = (ROOT / "docs" / "desktop-packaging.md").read_text()
        desktop_readme = (ROOT / "apps" / "desktop" / "README.md").read_text()

        required_phrases = [
            "Tauri is the preferred future wrapper",
            "No Tauri or Electron dependency is installed yet",
            "python -m scripts.desktop.launcher --dev",
            "python -m scripts.desktop.launcher --check",
            "Real publishing remains disabled",
            "local data directory",
            "least privilege",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, docs)

        self.assertIn("Desktop readiness scaffold", desktop_readme)
        self.assertIn("python -m scripts.desktop.launcher --dev", desktop_readme)


if __name__ == "__main__":
    unittest.main()
