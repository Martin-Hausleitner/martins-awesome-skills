from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ai_research_browser.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ai_research_browser", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AiResearchBrowserTest(unittest.TestCase):
    def make_profile_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "Local State").write_text(
            json.dumps(
                {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "name": "Personal",
                                "user_name": "personal@example.test",
                            },
                            "Profile 2": {
                                "name": "work",
                                "user_name": "work@example.test",
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        for directory, account in {
            "Default": "personal@example.test",
            "Profile 2": "work@example.test",
        }.items():
            profile_dir = root / directory
            profile_dir.mkdir(parents=True)
            (profile_dir / "Preferences").write_text(
                json.dumps(
                    {
                        "profile": {"name": directory},
                        "account_info": [{"email": account}],
                    }
                ),
                encoding="utf-8",
            )
        return root

    def test_discovers_profiles_and_resolves_work_alias(self):
        module = load_module()
        root = self.make_profile_root()

        profiles = module.discover_profiles(root)
        resolved = module.resolve_profile(profiles, "work")

        self.assertEqual([p["directory"] for p in profiles], ["Default", "Profile 2"])
        self.assertEqual(resolved["directory"], "Profile 2")
        self.assertEqual(resolved["account"], "work@example.test")

    def test_provider_registry_contains_chatgpt_gemini_modes_and_models(self):
        module = load_module()

        providers = module.provider_registry()

        self.assertIn("deep-research", providers["chatgpt"]["modes"])
        self.assertIn("agent", providers["chatgpt"]["modes"])
        self.assertIn("chat", providers["chatgpt"]["modes"])
        self.assertIn("deep-research", providers["gemini"]["modes"])
        self.assertIn("agent", providers["gemini"]["modes"])
        self.assertIn("models", providers["chatgpt"])
        self.assertIn("models", providers["gemini"])

    def test_parse_account_and_quota_from_visible_text(self):
        module = load_module()

        status = module.parse_visible_status(
            "Signed in as work@example.test\n"
            "Deep research: 7 remaining\n"
            "Agent tasks: 3 left\n"
            "Model: GPT-5.2 Thinking"
        )

        self.assertEqual(status["account"], "work@example.test")
        self.assertEqual(status["quotas"]["deep_research_remaining"], 7)
        self.assertEqual(status["quotas"]["agent_remaining"], 3)
        self.assertEqual(status["model"], "GPT-5.2 Thinking")

    def test_launch_args_include_selected_profile_headless_and_provider_url(self):
        module = load_module()
        browser = {
            "app_path": "/Applications/Brave Browser.app",
            "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "user_data_dir": "/tmp/brave",
        }

        args = module.build_launch_args(
            browser,
            profile_directory="Profile 2",
            port=9444,
            provider="chatgpt",
            mode="deep-research",
            headless=True,
        )

        self.assertIn("--remote-debugging-port=9444", args)
        self.assertIn("--user-data-dir=/tmp/brave", args)
        self.assertIn("--profile-directory=Profile 2", args)
        self.assertIn("--headless=new", args)
        self.assertIn("https://chatgpt.com/", args)

    def test_detect_launch_blockers_reports_busy_port_and_non_cdp_process(self):
        module = load_module()

        blockers = module.detect_launch_blockers(
            browser_name="Comet",
            port=9223,
            port_owner="Code Helper",
            process_args="/Applications/Comet.app/Contents/MacOS/Comet",
        )

        self.assertIn("port 9223 is already used by Code Helper", blockers)
        self.assertIn("Comet is already running without --remote-debugging-port", blockers)

    def test_run_artifact_paths_are_stable_and_screenshot_friendly(self):
        module = load_module()

        paths = module.build_artifact_paths(
            Path("/tmp/e2e"),
            provider="chatgpt",
            mode="agent",
            browser="brave",
            profile="work",
        )

        self.assertEqual(paths["run_dir"], Path("/tmp/e2e/chatgpt-agent-brave-work"))
        self.assertEqual(paths["status_json"], Path("/tmp/e2e/chatgpt-agent-brave-work/status.json"))
        self.assertEqual(paths["screenshot_png"], Path("/tmp/e2e/chatgpt-agent-brave-work/screenshot.png"))

    def test_verify_visible_text_detects_provider_mode_markers(self):
        module = load_module()

        result = module.verify_visible_text(
            "ChatGPT\nDeep research\nGet a detailed report\nModel: GPT-5.2 Thinking",
            provider="chatgpt",
            mode="deep-research",
        )

        self.assertTrue(result["detected"])
        self.assertIn("Deep research", result["matched_markers"])
        self.assertEqual(result["visible_status"]["model"], "GPT-5.2 Thinking")

    def test_write_e2e_record_persists_verification_and_screenshot_path(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        screenshot = root / "screen.png"
        screenshot.write_bytes(b"not really a png")

        record = module.write_e2e_record(
            root,
            provider="chatgpt",
            mode="agent",
            browser="brave",
            profile="work",
            status="selected",
            screenshot=screenshot,
            visible_text="Agent\nDescribe a task\nAgent tasks: 3 left",
            notes=["Agent mode selected in the composer."],
        )

        saved = json.loads(record["status_json"].read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "selected")
        self.assertEqual(saved["screenshot"], str(screenshot))
        self.assertTrue(saved["verification"]["detected"])
        self.assertEqual(saved["verification"]["visible_status"]["quotas"]["agent_remaining"], 3)


if __name__ == "__main__":
    unittest.main()
