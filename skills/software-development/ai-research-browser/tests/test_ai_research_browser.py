from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
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
        self.assertIn("grok", providers)
        self.assertIn("research", providers["grok"]["modes"])
        self.assertEqual(module.normalize_provider_name("grog"), "grok")
        self.assertIn("claude", providers)
        self.assertIn("chat", providers["claude"]["modes"])
        self.assertIn("research", providers["claude"]["modes"])
        self.assertIn("artifacts", providers["claude"]["modes"])
        self.assertEqual(module.provider_url("claude"), "https://claude.ai/new")
        self.assertIn("claude", module.provider_cli_choices())

    def test_browser_candidates_include_common_chromium_browsers(self):
        module = load_module()

        candidates = module.BROWSER_CANDIDATES

        self.assertIn("opera", candidates)
        self.assertIn("atlas", candidates)
        self.assertEqual(candidates["opera"]["display_name"], "Opera")
        self.assertEqual(candidates["atlas"]["display_name"], "ChatGPT Atlas")

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

    def test_parse_plan_and_usage_from_provider_visible_text(self):
        module = load_module()

        status = module.parse_visible_status(
            "Martin\nMax plan\n"
            "Opus 4.7 Adaptive\n"
            "You've used 75% of your weekly limit\n"
            "Guest pass: 3/3 left\n"
            "Usage resets tomorrow"
        )

        self.assertEqual(status["plan"], "Max")
        self.assertEqual(status["model"], "Opus 4.7 Adaptive")
        self.assertEqual(status["usage"]["used_percent"], 75)
        self.assertEqual(status["usage"]["remaining_count"], 3)
        self.assertEqual(status["usage"]["remaining_total"], 3)
        self.assertEqual(status["usage"]["reset"], "tomorrow")

    def test_parse_common_provider_plan_labels(self):
        module = load_module()

        examples = {
            "ChatGPT Pro\nDeep research: 12 remaining": "Pro",
            "Gemini Advanced\nModel: Pro": "Advanced",
            "Perplexity Pro\nResearch: 4 left": "Pro",
            "SuperGrok\nDeepSearch": "SuperGrok",
        }

        for text, plan in examples.items():
            with self.subTest(text=text):
                self.assertEqual(module.parse_visible_status(text)["plan"], plan)

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

    def test_build_test_matrix_expands_browsers_profiles_providers_and_features(self):
        module = load_module()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "profiles": [
                    {"directory": "Default", "name": "Work", "account": "work@example.test"},
                    {"directory": "Profile 2", "name": "Personal", "account": ""},
                ],
            }
        ]
        providers = {
            "chatgpt": {"modes": ["chat", "deep-research"]},
            "grok": {"modes": ["chat"]},
            "claude": {"modes": ["chat", "research", "artifacts"]},
        }

        matrix = module.build_test_matrix(browsers, providers)

        self.assertEqual(len(matrix), 12)
        self.assertEqual(matrix[0]["browser"], "brave")
        self.assertEqual(matrix[0]["profile_directory"], "Default")
        self.assertEqual(matrix[0]["profile_account"], "work@example.test")
        self.assertEqual(matrix[0]["provider"], "chatgpt")
        self.assertEqual(matrix[0]["feature"], "chat")
        self.assertIn(
            {
                "browser": "brave",
                "browser_name": "Brave Browser",
                "profile_directory": "Default",
                "profile_name": "Work",
                "profile_account": "work@example.test",
                "provider": "claude",
                "feature": "artifacts",
                "provider_url": "",
                "backend": "manual",
                "account_status": {},
                "status": "untested",
            },
            matrix,
        )

    def test_build_test_matrix_can_attach_account_status_by_provider(self):
        module = load_module()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "profiles": [{"directory": "Default", "name": "Work", "account": "work@example.test"}],
            }
        ]

        matrix = module.build_test_matrix(
            browsers,
            {"chatgpt": {"url": "https://chatgpt.com/", "modes": ["deep-research"]}},
            account_status={
                ("brave", "Default", "chatgpt"): {
                    "provider_account": "ui@example.test",
                    "plan": "Pro",
                    "usage": {"used_percent": 20},
                }
            },
            backend="playwright-cdp",
        )

        self.assertEqual(matrix[0]["backend"], "playwright-cdp")
        self.assertEqual(matrix[0]["account_status"]["plan"], "Pro")
        self.assertEqual(matrix[0]["account_status"]["usage"]["used_percent"], 20)

    def test_backend_registry_marks_local_and_managed_options(self):
        module = load_module()

        backends = module.backend_registry()

        self.assertIn("playwright-cdp", backends)
        self.assertIn("computer-use", backends)
        self.assertIn("openai-cua", backends)
        self.assertIn("hyperbrowser", backends)
        self.assertEqual(backends["playwright-cdp"]["scope"], "local")
        self.assertIn("Operator", " ".join(backends["openai-cua"]["aliases"]))

    def test_render_choice_table_is_human_readable(self):
        module = load_module()

        table = module.render_choice_table(
            "Browser",
            [
                {"id": "brave", "label": "Brave Browser", "detail": "1 profile"},
                {"id": "comet", "label": "Comet", "detail": "Default"},
            ],
        )

        self.assertIn("Browser", table)
        self.assertIn("[1] Brave Browser", table)
        self.assertIn("1 profile", table)

    def test_select_index_defaults_and_rejects_out_of_range(self):
        module = load_module()

        self.assertEqual(module.select_index("", 3), 0)
        self.assertEqual(module.select_index("2", 3), 1)
        with self.assertRaises(ValueError):
            module.select_index("4", 3)

    def test_account_status_record_combines_profile_and_visible_provider_state(self):
        module = load_module()

        status = module.account_status_record(
            browser="brave",
            profile={"directory": "Default", "name": "Work", "account": "profile@example.test"},
            provider="chatgpt",
            visible_text="Signed in as ui@example.test\nChatGPT Pro\nDeep research: 4 remaining\nAgent tasks: 2 left\n30% used",
        )

        self.assertEqual(status["browser"], "brave")
        self.assertEqual(status["profile_account"], "profile@example.test")
        self.assertEqual(status["provider_account"], "ui@example.test")
        self.assertEqual(status["plan"], "Pro")
        self.assertEqual(status["quotas"]["deep_research_remaining"], 4)
        self.assertEqual(status["usage"]["used_percent"], 30)

    def test_chat_cache_key_is_stable_and_provider_normalized(self):
        module = load_module()

        first = module.chat_cache_key(
            browser="brave",
            profile="Default",
            provider="grog",
            chat_url="https://grok.com/c/123",
        )
        second = module.chat_cache_key(
            browser="Brave",
            profile="Default",
            provider="grok",
            chat_url="https://grok.com/c/123",
        )

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("brave-default-grok-"))

    def test_save_chat_record_writes_metadata_text_and_index(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        text_file = root / "visible.txt"
        text_file.write_text("User: hi\nAssistant: hello", encoding="utf-8")

        record = module.save_chat_record(
            cache_root=root / "cache",
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="Greeting",
            text=text_file.read_text(encoding="utf-8"),
            source="manual",
            refresh=False,
        )

        metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
        index = json.loads((root / "cache" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["title"], "Greeting")
        self.assertEqual(metadata["text_path"], str(record["text_path"]))
        self.assertEqual(record["text_path"].read_text(encoding="utf-8"), "User: hi\nAssistant: hello")
        self.assertEqual(len(index["chats"]), 1)

    def test_save_chat_record_uses_cache_without_refresh(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())

        first = module.save_chat_record(
            cache_root=root,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="First",
            text="old text",
            source="manual",
            refresh=False,
        )
        second = module.save_chat_record(
            cache_root=root,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="Second",
            text="new text",
            source="manual",
            refresh=False,
        )

        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["text_path"].read_text(encoding="utf-8"), "old text")

    def test_save_chat_record_refresh_rescrapes_text(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())

        module.save_chat_record(
            cache_root=root,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="First",
            text="old text",
            source="manual",
            refresh=False,
        )
        refreshed = module.save_chat_record(
            cache_root=root,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="Second",
            text="new text",
            source="manual",
            refresh=True,
        )

        self.assertFalse(refreshed["cache_hit"])
        self.assertEqual(refreshed["text_path"].read_text(encoding="utf-8"), "new text")

    def test_parse_chat_listing_from_visible_text(self):
        module = load_module()

        chats = module.parse_chat_listing(
            "Recents\nPreisvergleich Original vs Angebote\nMotherboard Rahmen und Kosten\nProjects\n",
            provider="chatgpt",
        )

        self.assertEqual(chats[0]["title"], "Preisvergleich Original vs Angebote")
        self.assertEqual(chats[0]["provider"], "chatgpt")

    def test_cmd_list_chats_outputs_cached_records(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        module.save_chat_record(
            cache_root=root,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            chat_url="https://chatgpt.com/c/abc",
            title="Greeting",
            text="hello",
            source="manual",
            refresh=False,
        )

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["list-chats", "--cache-root", str(root)])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["chats"][0]["title"], "Greeting")

    def test_cmd_backends_outputs_backend_registry(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["backends"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("playwright-cdp", payload["backends"])
        self.assertIn("openai-cua", payload["backends"])

    def test_cmd_preflight_reports_missing_profiles_without_traceback(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_port_owner = module.port_owner
        original_process_args = module.process_args_for_browser
        module.discover_browsers = lambda: [
            {
                "id": "edge",
                "display_name": "Microsoft Edge",
                "default_port": 9225,
                "profiles": [],
            }
        ]
        module.port_owner = lambda port: ""
        module.process_args_for_browser = lambda display_name: ""
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["preflight", "--browser", "edge", "--profile", "Default"])
        finally:
            module.discover_browsers = original_discover
            module.port_owner = original_port_owner
            module.process_args_for_browser = original_process_args

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertIn("no profiles discovered for Microsoft Edge", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
