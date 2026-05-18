from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from unittest import mock
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
        self.assertIn("openrouter", providers)
        self.assertEqual(module.normalize_provider_name("open-router"), "openrouter")
        self.assertIn("claude", providers)
        self.assertIn("chat", providers["claude"]["modes"])
        self.assertIn("research", providers["claude"]["modes"])
        self.assertIn("artifacts", providers["claude"]["modes"])
        self.assertEqual(module.provider_url("claude"), "https://claude.ai/new")
        self.assertIn("claude", module.provider_cli_choices())
        self.assertEqual(module.normalize_provider_name("anthropic"), "claude")
        self.assertEqual(module.normalize_provider_name("entropic"), "claude")
        self.assertEqual(module.normalize_provider_name("google"), "gemini")

    def test_browser_candidates_include_common_chromium_browsers(self):
        module = load_module()

        candidates = module.BROWSER_CANDIDATES

        self.assertIn("opera", candidates)
        self.assertIn("atlas", candidates)
        self.assertEqual(candidates["opera"]["display_name"], "Opera")
        self.assertEqual(candidates["atlas"]["display_name"], "ChatGPT Atlas")

    def test_browser_install_state_distinguishes_app_binary_and_profile_data(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        app_path = root / "Example.app"
        binary_rel = "Contents/MacOS/Example"
        (app_path / "Contents" / "MacOS").mkdir(parents=True)
        (app_path / binary_rel).write_text("#!/bin/sh\n", encoding="utf-8")
        user_data_dir = root / "ProfileData"
        user_data_dir.mkdir()

        state = module.browser_install_state(
            {
                "app_path": str(app_path),
                "binary_rel": binary_rel,
                "user_data_dir": str(user_data_dir),
            }
        )

        self.assertEqual(
            state,
            {
                "app_exists": True,
                "binary_exists": True,
                "user_data_exists": True,
            },
        )

    def test_model_catalog_lists_selectable_models_and_feature_modes(self):
        module = load_module()

        catalog = module.model_catalog()

        self.assertIn("GPT-5.5", catalog["chatgpt"]["models"])
        self.assertIn("GPT-5.5 Pro", catalog["chatgpt"]["models"])
        self.assertIn("Pro", catalog["gemini"]["models"])
        self.assertIn("Complex", catalog["gemini"]["models"])
        self.assertIn("Thinking with 3 Pro", catalog["gemini"]["models"])
        self.assertIn("Deep Think", catalog["gemini"]["tools"])
        self.assertIn("Opus 4.7", catalog["claude"]["models"])
        self.assertIn("Sonnet 4.6", catalog["claude"]["models"])
        self.assertIn("Research", catalog["perplexity"]["tools"])
        self.assertIn("Sonar Deep Research", catalog["perplexity"]["models"])
        self.assertIn("DeepSearch", catalog["grok"]["tools"])
        self.assertIn("Grok 4.1 Fast Reasoning", catalog["grok"]["models"])

    def test_cmd_models_outputs_provider_catalog(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["models", "--provider", "anthropic"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["provider"], "claude")
        self.assertIn("Opus 4.7", payload["models"])

    def test_cmd_launch_args_accepts_provider_alias_and_model(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9222,
                "profiles": [{"directory": "Default", "name": "Work", "account": ""}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "launch-args",
                        "--browser",
                        "brave",
                        "--profile",
                        "Default",
                        "--provider",
                        "google",
                        "--mode",
                        "deep-research",
                        "--model",
                        "Pro",
                    ]
                )
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["provider"], "gemini")
        self.assertEqual(payload["model"], "Pro")
        self.assertEqual(payload["model_selection"], "select-in-provider-ui")

    def test_discovers_hidden_signed_in_opera_profile_state(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        (root / "Local State").write_text(
            json.dumps(
                {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "name": "",
                                "user_name": "",
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        profile_dir = root / "Default"
        profile_dir.mkdir()
        (profile_dir / "Preferences").write_text(
            json.dumps(
                {
                    "sync": {"gaia_id": "12345"},
                    "opera": {"anonymous_hidden_account_user_id": "encrypted"},
                }
            ),
            encoding="utf-8",
        )

        profiles = module.discover_profiles(root, browser_id="opera")

        self.assertEqual(profiles[0]["name"], "Opera Default")
        self.assertEqual(profiles[0]["account_state"], "signed-in-hidden")

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

    def test_parse_quota_ignores_accessibility_ref_ids(self):
        module = load_module()

        status = module.parse_visible_status('- link "KI Modelle für Voice-Agent" [ref=e14]\n- button "Advanced research" [ref=e53]')

        self.assertIsNone(status["quotas"]["agent_remaining"])
        self.assertIsNone(status["quotas"]["deep_research_remaining"])

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
            "Google AI Ultra plan\nDeep Research": "Ultra",
            "Perplexity Pro\nResearch: 4 left": "Pro",
            "X Premium+ subscription\nGrok": "Premium+",
            "SuperGrok\nDeepSearch": "SuperGrok",
        }

        for text, plan in examples.items():
            with self.subTest(text=text):
                self.assertEqual(module.parse_visible_status(text)["plan"], plan)

    def test_parse_plan_ignores_upgrade_upsells(self):
        module = load_module()

        status = module.parse_visible_status(
            "kleinstein.fragen@gmail.com\n"
            "Unlock extended capabilities\n"
            "Try for $0.00\n"
            "Upgrade to SuperGrok\n"
            "DeepSearch\n"
            "Ask anything"
        )

        self.assertEqual(status["account"], "kleinstein.fragen@gmail.com")
        self.assertEqual(status["plan"], "")

    def test_parse_plan_ignores_escaped_upgrade_upsell_text(self):
        module = load_module()

        status = module.parse_visible_status(
            '"Unlock extended capabilities\\n\\nTry for $0.00\\nUpgrade to SuperGrok\\nAsk anything"'
        )

        self.assertEqual(status["plan"], "")

    def test_parse_plan_ignores_comparison_history_titles(self):
        module = load_module()

        status = module.parse_visible_status("Claude Pro vs Max: Token-Limits & API-Kostenvergleich\nAsk anything")

        self.assertEqual(status["plan"], "")

    def test_parse_model_ignores_history_ref_titles(self):
        module = load_module()

        status = module.parse_visible_status('- link "Anti-Gravity Opus mit OpenClaw verbinden" [ref=e18]\nAsk Grok')

        self.assertEqual(status["model"], "")

    def test_parse_model_respects_provider_family_when_available(self):
        module = load_module()

        status = module.parse_visible_status("Anti-Gravity Opus mit OpenClaw verbinden\nAsk Grok", provider="grok")

        self.assertEqual(status["model"], "")

    def test_parse_chatgpt_profile_name_followed_by_plan(self):
        module = load_module()

        status = module.parse_visible_status("Isagi yoichi\nPro\nWhere should we begin?\nInstant")

        self.assertEqual(status["account"], "Isagi yoichi")
        self.assertEqual(status["plan"], "Pro")

    def test_extract_provider_inventory_decodes_agent_browser_eval_strings(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "chatgpt",
            '"Skip to content\\nChatGPT\\nIsagi yoichi\\nPro\\nWhat’s on your mind today?\\n\\nInstant"',
        )

        self.assertEqual(inventory["visible_status"]["account"], "Isagi yoichi")
        self.assertEqual(inventory["visible_status"]["plan"], "Pro")
        self.assertEqual(inventory["login_state"], "signed-in-or-ready")

    def test_login_words_inside_history_urls_do_not_force_signed_out(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "perplexity",
            "https://developer.nvidia.com/login [a@servas.ai](mailto:a@servas.ai)\n"
            "Create team\nam5150\nDiscover\nSearch\nComputer\nModel",
        )

        self.assertEqual(inventory["login_state"], "signed-in-or-ready")
        self.assertEqual(inventory["visible_status"]["account"], "am5150")

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

    def test_launch_plan_includes_model_without_pretending_url_selects_it(self):
        module = load_module()
        browser = {
            "id": "brave",
            "display_name": "Brave Browser",
            "app_path": "/Applications/Brave Browser.app",
            "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "user_data_dir": "/tmp/brave",
        }

        plan = module.build_launch_plan(
            browser,
            profile_directory="Default",
            port=9444,
            provider="google",
            mode="deep-research",
            model="Pro",
            headless=True,
        )

        self.assertEqual(plan["provider"], "gemini")
        self.assertEqual(plan["model"], "Pro")
        self.assertEqual(plan["model_selection"], "select-in-provider-ui")
        self.assertIn("--profile-directory=Default", plan["launch_args"])

    def test_background_launch_plan_uses_hidden_macos_open_without_focus(self):
        module = load_module()
        browser = {
            "id": "opera",
            "display_name": "Opera",
            "app_path": "/Applications/Opera.app",
            "binary_path": "/Applications/Opera.app/Contents/MacOS/Opera",
            "user_data_dir": "/tmp/opera",
        }

        plan = module.build_background_launch_plan(
            browser,
            profile_directory="Default",
            port=9555,
            provider="google",
            mode="deep-research",
            model="Thinking with 3 Pro",
            headless=False,
        )

        self.assertEqual(plan["strategy"], "macos-open-hidden")
        self.assertEqual(plan["launch_command"][:5], ["/usr/bin/open", "-g", "-j", "-n", "-a"])
        self.assertIn("/Applications/Opera.app", plan["launch_command"])
        self.assertIn("--args", plan["launch_command"])
        self.assertIn("--remote-debugging-port=9555", plan["launch_command"])
        self.assertIn("--profile-directory=Default", plan["launch_command"])
        self.assertIn("https://gemini.google.com/app?hl=de", plan["launch_command"])
        self.assertEqual(plan["post_launch_hide_command"], ["osascript", "-e", 'tell application "Opera" to set visible to false'])

    def test_background_launch_plan_can_be_headless_for_zero_window_runs(self):
        module = load_module()
        browser = {
            "id": "brave",
            "display_name": "Brave Browser",
            "app_path": "/Applications/Brave Browser.app",
            "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "user_data_dir": "/tmp/brave",
        }

        plan = module.build_background_launch_plan(
            browser,
            profile_directory="Default",
            port=9556,
            provider="chatgpt",
            mode="agent",
            model="GPT-5.5 Pro",
            headless=True,
        )

        self.assertIn("--headless=new", plan["launch_command"])
        self.assertEqual(plan["visibility"], "headless")

    def test_background_all_plan_filters_launchable_browsers_and_reports_blockers(self):
        module = load_module()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9222,
                "app_exists": True,
                "binary_exists": True,
                "profiles": [{"directory": "Default", "name": "Work", "account": ""}],
            },
            {
                "id": "edge",
                "display_name": "Microsoft Edge",
                "app_path": "/Applications/Microsoft Edge.app",
                "binary_path": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "user_data_dir": "/tmp/edge",
                "default_port": 9225,
                "app_exists": False,
                "binary_exists": False,
                "profiles": [{"directory": "Default", "name": "Default", "account": ""}],
            },
        ]

        plan = module.build_background_all_plan(
            browsers,
            provider="chatgpt",
            mode="chat",
            model="Auto",
            headless=False,
            port_offset=100,
        )

        self.assertEqual([item["browser"] for item in plan["launches"]], ["brave"])
        self.assertEqual(plan["launches"][0]["port"], 9322)
        self.assertEqual(plan["skipped"][0]["browser"], "edge")
        self.assertIn("binary is not installed", plan["skipped"][0]["reason"])

    def test_cmd_launch_background_outputs_hidden_plan_in_dry_run(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "opera",
                "display_name": "Opera",
                "app_path": "/Applications/Opera.app",
                "binary_path": "/Applications/Opera.app/Contents/MacOS/Opera",
                "user_data_dir": "/tmp/opera",
                "default_port": 9226,
                "app_exists": True,
                "binary_exists": True,
                "profiles": [{"directory": "Default", "name": "Opera Default", "account": ""}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "launch-background",
                        "--browser",
                        "opera",
                        "--profile",
                        "Default",
                        "--provider",
                        "google",
                        "--mode",
                        "deep-research",
                        "--model",
                        "Pro",
                        "--dry-run",
                    ]
                )
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["execution"]["started"])
        self.assertEqual(payload["plan"]["strategy"], "macos-open-hidden")
        self.assertEqual(payload["plan"]["provider"], "gemini")

    def test_cmd_launch_all_background_outputs_all_launchable_browsers(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9222,
                "app_exists": True,
                "binary_exists": True,
                "profiles": [{"directory": "Default", "name": "Work", "account": ""}],
            },
            {
                "id": "edge",
                "display_name": "Microsoft Edge",
                "app_path": "/Applications/Microsoft Edge.app",
                "binary_path": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "user_data_dir": "/tmp/edge",
                "default_port": 9225,
                "app_exists": False,
                "binary_exists": False,
                "profiles": [{"directory": "Default", "name": "Default", "account": ""}],
            },
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["launch-all-background", "--provider", "chatgpt", "--dry-run"])
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual([item["browser"] for item in payload["plan"]["launches"]], ["brave"])
        self.assertEqual(payload["executions"][0]["dry_run"], True)
        self.assertEqual(payload["plan"]["skipped"][0]["browser"], "edge")

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

    def test_detect_launch_blockers_notices_mixed_cdp_and_non_cdp_processes(self):
        module = load_module()

        blockers = module.detect_launch_blockers(
            browser_name="Google Chrome",
            port=9224,
            port_owner="",
            process_args=(
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n"
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=58554"
            ),
        )

        self.assertIn("Google Chrome is already running without --remote-debugging-port", blockers)

    def test_extract_provider_inventory_from_snapshot_text(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nChatGPT Pro\n"
            "GPT-5.5 Pro\nDeep research\nAgent\nDeep research: 8 remaining\n"
            "Usage resets tomorrow",
        )

        self.assertEqual(inventory["login_state"], "signed-in-or-ready")
        self.assertEqual(inventory["visible_status"]["account"], "work@example.test")
        self.assertEqual(inventory["visible_status"]["plan"], "Pro")
        self.assertIn("GPT-5.5 Pro", inventory["available_models"])
        self.assertIn("Deep research", inventory["available_tools"])
        self.assertTrue(inventory["available_modes"]["deep-research"])
        self.assertTrue(any("remaining" in line for line in inventory["usage_lines"]))

    def test_extract_provider_inventory_classifies_cloudflare_wall_as_not_ready(self):
        module = load_module()

        inventory = module.extract_provider_inventory("chatgpt", "Just a moment...\nhttps://chatgpt.com/\n(no interactive elements)")

        self.assertEqual(inventory["login_state"], "signed-out-or-wall")

    def test_provider_title_alone_is_not_enough_to_mark_login_ready(self):
        module = load_module()

        inventory = module.extract_provider_inventory("chatgpt", "✓ ChatGPT\n  https://chatgpt.com/\n")

        self.assertEqual(inventory["login_state"], "unknown")

    def test_cmd_probe_specs_outputs_provider_paths(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["probe-specs", "--provider", "anthropic"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["provider"], "claude")
        self.assertIn("model_hints", payload["probe_spec"])

    def test_oracle_plan_outputs_attach_status_and_show_commands(self):
        module = load_module()

        plan = module.build_oracle_plan(
            prompt="Review this E2E probe",
            files=["skills/software-development/ai-research-browser/**"],
            cdp_port=9224,
            deep_research=True,
        )

        self.assertIn("--browser-attach-running", plan["consult_dry_run"])
        self.assertIn("--remote-chrome", plan["consult_dry_run"])
        self.assertIn("127.0.0.1:9224", plan["consult_dry_run"])
        self.assertIn("--browser-research", plan["consult_dry_run"])
        self.assertEqual(plan["status"][:3], ["npx", "-y", "@steipete/oracle"])
        self.assertIn("--render", plan["show_session"])

    def test_cmd_oracle_plan_outputs_json_commands(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["oracle-plan", "-p", "Check implementation", "--cdp-port", "9224"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("--browser-attach-running", payload["consult_dry_run"])

    def test_cmd_e2e_probe_parses_captured_text_file(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        text_file = root / "claude.txt"
        text_file.write_text(
            "Claude\nMartin\nMax plan\nOpus 4.7 Adaptive\nYou've used 75% of your weekly limit",
            encoding="utf-8",
        )

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(
                [
                    "e2e-probe",
                    "--artifact-root",
                    str(root / "artifacts"),
                    "--browser",
                    "opera",
                    "--profile",
                    "Default",
                    "--provider",
                    "anthropic",
                    "--mode",
                    "chat",
                    "--text-file",
                    str(text_file),
                ]
            )

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["provider"], "claude")
        self.assertEqual(payload["inventory"]["visible_status"]["plan"], "Max")
        self.assertEqual(payload["inventory"]["visible_status"]["usage"]["used_percent"], 75)
        self.assertTrue(Path(payload["status_json"]).exists())

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

    def test_primary_feature_suite_focuses_requested_provider_workflows(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        con = sqlite3.connect(root / "Cookies")
        con.execute("create table cookies(host_key text, name text)")
        con.execute("insert into cookies(host_key, name) values (?, ?)", (".chatgpt.com", "__Secure-next-auth.session-token.0"))
        con.commit()
        con.close()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "profiles": [{"directory": "Default", "name": "Work", "account": "", "account_state": "signed-in-hidden", "path": str(root)}],
            }
        ]

        suite = module.build_primary_feature_suite(browsers, providers=["chatgpt"])

        self.assertEqual([row["feature"] for row in suite], ["chat", "deep-research", "agent"])
        self.assertEqual(suite[1]["model"], "GPT-5.5 Pro")
        self.assertIn("deep-research-tool", suite[1]["must_verify"])
        self.assertEqual(suite[0]["status"], "queued")

    def test_primary_feature_suite_includes_grok_and_perplexity_when_requested(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        con = sqlite3.connect(root / "Cookies")
        con.execute("create table cookies(host_key text, name text)")
        con.executemany(
            "insert into cookies(host_key, name) values (?, ?)",
            [
                (".grok.com", "sso"),
                (".perplexity.ai", "__Secure-next-auth.session-token"),
            ],
        )
        con.commit()
        con.close()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "profiles": [{"directory": "Default", "name": "Work", "account": "", "account_state": "signed-in-hidden", "path": str(root)}],
            }
        ]

        suite = module.build_primary_feature_suite(browsers, providers=["grok", "perplexity"])

        self.assertEqual(
            [(row["provider"], row["feature"], row["status"]) for row in suite],
            [
                ("grok", "chat", "queued"),
                ("grok", "research", "queued"),
                ("perplexity", "chat", "queued"),
                ("perplexity", "research", "queued"),
            ],
        )

    def test_cmd_feature_suite_outputs_primary_targets(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "opera",
                "display_name": "Opera",
                "profiles": [{"directory": "Default", "name": "Opera Default", "account": "", "account_state": "signed-in-hidden", "path": "/tmp/missing"}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["feature-suite", "--providers", "anthropic"])
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["provider"], "claude")
        self.assertEqual(payload[0]["model"], "Opus 4.7")

    def test_live_probe_ok_requires_captured_and_login_when_asserted(self):
        module = load_module()

        captured = {"status": "captured", "inventory": {"login_state": "signed-in-or-ready"}}
        signed_out = {"status": "signed-out-or-wall", "inventory": {"login_state": "signed-out-or-wall"}}

        self.assertTrue(module.live_probe_ok(captured, assert_login=True))
        self.assertFalse(module.live_probe_ok(signed_out, assert_login=False))
        self.assertFalse(module.live_probe_ok({"status": "captured", "inventory": {"login_state": "unknown"}}, assert_login=True))

    def test_agent_browser_probe_marks_signed_out_snapshot_as_wall(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout='button "Log in"\nbutton "Sign up for free"', stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        original_run = module.run_agent_browser
        module.run_agent_browser = fake_run
        try:
            payload = module.agent_browser_probe(
                cdp_port=9222,
                provider="chatgpt",
                mode="chat",
                artifact_root=root,
                browser="brave",
                profile="Default",
            )
        finally:
            module.run_agent_browser = original_run

        self.assertEqual(payload["status"], "signed-out-or-wall")
        self.assertEqual(payload["inventory"]["login_state"], "signed-out-or-wall")

    def test_provider_composer_selector_returns_generic_editable_targets(self):
        module = load_module()

        selector = module.provider_composer_selector("perplexity")

        self.assertIn("contenteditable", selector)
        self.assertIn("textbox", selector)

    def test_agent_browser_profile_global_args_use_profile_not_user_data_dir_arg(self):
        module = load_module()

        args = module.agent_browser_profile_global_args(
            {"binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
            "/tmp/clone/user-data",
            "Default",
        )

        self.assertIn("--profile", args)
        self.assertIn("/tmp/clone/user-data", args)
        self.assertIn("--executable-path", args)
        self.assertIn("--profile-directory=Default", args[-1])
        self.assertNotIn("--user-data-dir", " ".join(args))

    def test_clone_cdp_launch_args_use_real_browser_binary_and_disposable_profile(self):
        module = load_module()

        args = module.build_clone_cdp_launch_args(
            {"binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
            clone_user_data="/tmp/clone/user-data",
            profile_directory="Default",
            port=9444,
            headless=True,
            initial_url="about:blank",
        )

        self.assertEqual(args[0], "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
        self.assertIn("--remote-debugging-address=127.0.0.1", args)
        self.assertIn("--remote-debugging-port=9444", args)
        self.assertIn("--user-data-dir=/tmp/clone/user-data", args)
        self.assertIn("--profile-directory=Default", args)
        self.assertIn("--headless=new", args)
        self.assertIn("--disable-remote-fonts", args)
        self.assertIn("about:blank", args)
        self.assertNotIn("--password-store=basic", args)
        self.assertNotIn("--use-mock-keychain", args)

    def test_clone_cdp_launch_args_can_load_extension_paths(self):
        module = load_module()

        args = module.build_clone_cdp_launch_args(
            {"binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
            clone_user_data="/tmp/clone/user-data",
            profile_directory="Default",
            port=9444,
            headless=True,
            initial_url="about:blank",
            extension_paths=["/tmp/ext/saveai"],
        )

        self.assertIn("--disable-extensions-except=/tmp/ext/saveai", args)
        self.assertIn("--load-extension=/tmp/ext/saveai", args)

    def test_agent_browser_profile_probe_connects_to_clone_cdp_instead_of_launching_chrome_for_testing(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        profile.mkdir(parents=True)
        (profile / "Preferences").write_text("{}", encoding="utf-8")
        (source / "Local State").write_text("{}", encoding="utf-8")
        root = Path(tempfile.mkdtemp())

        class FakeProcess:
            pid = 12345

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

        fake_process = FakeProcess()
        original_find_port = module.find_available_port
        original_start = module.start_clone_cdp_browser
        original_run = module.run_agent_browser
        module.find_available_port = lambda: 9444
        module.start_clone_cdp_browser = lambda **kwargs: (
            fake_process,
            {"ok": True, "port": kwargs["port"], "launch_args": kwargs["launch_args"], "pid": fake_process.pid},
        )

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            self.assertEqual(args[:2], ["--cdp", "9444"])
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout="ChatGPT\nSigned in as work@example.test\nMessage ChatGPT", stderr="")
            if "screenshot" in args:
                Path(args[-1]).write_bytes(b"png")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        module.run_agent_browser = fake_run
        try:
            payload = module.agent_browser_profile_probe(
                browser={
                    "id": "brave",
                    "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                    "user_data_dir": str(source),
                },
                profile={"directory": "Default"},
                provider="chatgpt",
                mode="chat",
                model="GPT-5.5",
                artifact_root=root / "artifacts",
                clone_root=root / "clones",
            )
        finally:
            module.find_available_port = original_find_port
            module.start_clone_cdp_browser = original_start
            module.run_agent_browser = original_run

        self.assertEqual(payload["status"], "captured")
        self.assertEqual(payload["cdp_port"], 9444)
        self.assertTrue(getattr(fake_process, "terminated", False))
        self.assertTrue(all("--executable-path" not in " ".join(command["args"]) for command in payload["commands"]))

    def test_agent_browser_profile_probe_uses_eval_text_when_snapshot_times_out(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        profile.mkdir(parents=True)
        (profile / "Preferences").write_text("{}", encoding="utf-8")
        (source / "Local State").write_text("{}", encoding="utf-8")
        root = Path(tempfile.mkdtemp())

        class FakeProcess:
            pid = 12345

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        original_find_port = module.find_available_port
        original_start = module.start_clone_cdp_browser
        original_run = module.run_agent_browser
        original_capture = module.capture_cdp_screenshot
        module.find_available_port = lambda: 9445
        module.start_clone_cdp_browser = lambda **kwargs: (FakeProcess(), {"ok": True, "port": kwargs["port"]})
        module.capture_cdp_screenshot = lambda port, screenshot: False

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 1, stdout="", stderr="Timeout")
            if "eval" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout="ChatGPT\nSigned in as work@example.test\nMessage ChatGPT", stderr="")
            if "screenshot" in args:
                return module.subprocess.CompletedProcess(command, 1, stdout="", stderr="Timeout")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        module.run_agent_browser = fake_run
        try:
            payload = module.agent_browser_profile_probe(
                browser={
                    "id": "brave",
                    "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                    "user_data_dir": str(source),
                },
                profile={"directory": "Default"},
                provider="chatgpt",
                mode="chat",
                model="GPT-5.5",
                artifact_root=root / "artifacts",
                clone_root=root / "clones",
            )
        finally:
            module.find_available_port = original_find_port
            module.start_clone_cdp_browser = original_start
            module.run_agent_browser = original_run
            module.capture_cdp_screenshot = original_capture

        self.assertEqual(payload["status"], "captured-without-screenshot")
        self.assertEqual(payload["inventory"]["visible_status"]["account"], "work@example.test")
        self.assertTrue(any(command["label"] == "eval-visible-text" for command in payload["commands"]))

    def test_cdp_screenshot_fallback_invokes_node_and_detects_output(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        screenshot = root / "screen.png"

        def fake_run(command, capture_output=True, text=True, timeout=20):
            screenshot.write_bytes(b"png")
            return module.subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run) as run_mock:
            ok = module.capture_cdp_screenshot(9444, screenshot)

        self.assertTrue(ok)
        self.assertTrue(screenshot.exists())
        self.assertIn("node", run_mock.call_args.args[0][0])

    def test_run_agent_browser_returns_timeout_completed_process(self):
        module = load_module()

        timeout = module.subprocess.TimeoutExpired(["agent-browser"], 5)
        timeout.stdout = b"partial"
        with mock.patch.object(module.subprocess, "run", side_effect=timeout):
            result = module.run_agent_browser(["snapshot"], session="test", timeout=5)

        self.assertEqual(result.returncode, 124)
        self.assertIn("partial", result.stdout)
        self.assertIn("Timed out after 5s", result.stderr)

    def test_clone_browser_profile_for_agent_browser_skips_locks_and_caches(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        (profile / "Cache").mkdir(parents=True)
        (profile / "Extensions" / "big-extension").mkdir(parents=True)
        (profile / "IndexedDB" / "https_chatgpt.com_0.indexeddb.leveldb").mkdir(parents=True)
        (profile / "Preferences").write_text("{}", encoding="utf-8")
        (profile / "SingletonLock").write_text("locked", encoding="utf-8")
        (profile / "Cache" / "entry").write_text("cache", encoding="utf-8")
        (profile / "Extensions" / "big-extension" / "asset").write_text("extension", encoding="utf-8")
        (profile / "IndexedDB" / "https_chatgpt.com_0.indexeddb.leveldb" / "000003.blob").write_text("blob", encoding="utf-8")
        (source / "Local State").write_text("{}", encoding="utf-8")

        clone = module.clone_browser_profile_for_agent_browser(
            {"user_data_dir": str(source)},
            {"directory": "Default"},
            Path(tempfile.mkdtemp()) / "clones",
            run_slug="brave-default-chatgpt",
        )

        clone_profile = Path(clone["clone_profile"])
        self.assertTrue((clone_profile / "Preferences").exists())
        self.assertTrue((Path(clone["clone_user_data"]) / "Local State").exists())
        self.assertFalse((clone_profile / "SingletonLock").exists())
        self.assertFalse((clone_profile / "Cache" / "entry").exists())
        self.assertFalse((clone_profile / "Extensions" / "big-extension" / "asset").exists())
        self.assertFalse((clone_profile / "IndexedDB" / "https_chatgpt.com_0.indexeddb.leveldb" / "000003.blob").exists())

    def test_clone_can_include_selected_ai_exporter_extension(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        extension_id = module.KNOWN_EXTENSION_IDS["ai-exporter"]["ids"][0]
        extension_dir = profile / "Extensions" / extension_id / "4.2.1_0"
        extension_dir.mkdir(parents=True)
        (extension_dir / "manifest.json").write_text(json.dumps({"name": "SaveAI", "version": "4.2.1"}), encoding="utf-8")
        (profile / "Extensions" / "other" / "1").mkdir(parents=True)
        (profile / "Extensions" / "other" / "1" / "manifest.json").write_text("{}", encoding="utf-8")
        (profile / "Preferences").write_text("{}", encoding="utf-8")
        (source / "Local State").write_text("{}", encoding="utf-8")

        clone = module.clone_browser_profile_for_agent_browser(
            {"user_data_dir": str(source)},
            {"directory": "Default"},
            Path(tempfile.mkdtemp()) / "clones",
            run_slug="brave-default-chatgpt",
            include_extension_ids=[extension_id],
        )

        clone_profile = Path(clone["clone_profile"])
        self.assertTrue((clone_profile / "Extensions" / extension_id / "4.2.1_0" / "manifest.json").exists())
        self.assertFalse((clone_profile / "Extensions" / "other" / "1" / "manifest.json").exists())

    def test_discover_extensions_finds_saveai_manifest(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        extension_id = module.KNOWN_EXTENSION_IDS["ai-exporter"]["ids"][0]
        extension_dir = profile / "Extensions" / extension_id / "4.2.1_0"
        extension_dir.mkdir(parents=True)
        (extension_dir / "manifest.json").write_text(
            json.dumps({"name": "SaveAI Popup", "version": "4.2.1", "permissions": ["storage"]}),
            encoding="utf-8",
        )

        payload = module.discover_extensions(
            [
                {
                    "id": "brave",
                    "display_name": "Brave Browser",
                    "profiles": [{"directory": "Default", "name": "Work", "path": str(profile)}],
                }
            ],
            extension_ids=[extension_id],
        )

        self.assertEqual(payload["extensions"][0]["extension"]["id"], extension_id)
        self.assertEqual(payload["extensions"][0]["extension"]["version"], "4.2.1")
        self.assertIn("storage", payload["extensions"][0]["extension"]["permissions"])

    def test_account_audit_matrix_covers_each_provider_and_parses_text_artifacts(self):
        module = load_module()
        text_root = Path(tempfile.mkdtemp())
        (text_root / "brave-default-chatgpt.txt").write_text(
            "Signed in as ui@example.test\nChatGPT Pro\nDeep research: 5 remaining\nAgent tasks: 2 left",
            encoding="utf-8",
        )
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9222,
                "app_exists": True,
                "binary_exists": True,
                "user_data_dir": "/tmp/brave",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "profiles": [{"directory": "Default", "name": "Work", "account": "profile@example.test"}],
            }
        ]

        audit = module.build_account_audit_matrix(
            browsers,
            {"chatgpt": {"url": "https://chatgpt.com/"}, "gemini": {"url": "https://gemini.google.com/app?hl=de"}},
            text_dir=text_root,
            headless=False,
        )

        self.assertEqual(len(audit["rows"]), 2)
        chatgpt = audit["rows"][0]
        self.assertEqual(chatgpt["provider"], "chatgpt")
        self.assertEqual(chatgpt["account_status"]["provider_account"], "ui@example.test")
        self.assertEqual(chatgpt["account_status"]["plan"], "Pro")
        self.assertEqual(chatgpt["account_status"]["quotas"]["deep_research_remaining"], 5)
        self.assertTrue(chatgpt["background_plan"]["launch_command"])
        self.assertEqual(audit["rows"][1]["status"], "needs-ui-capture")

    def test_account_audit_status_marks_detected_sessions_separately_from_missing_ui(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        con = sqlite3.connect(root / "Cookies")
        con.execute("create table cookies(host_key text, name text)")
        con.execute("insert into cookies(host_key, name) values (?, ?)", (".perplexity.ai", "__Secure-next-auth.session-token"))
        con.commit()
        con.close()
        browsers = [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9222,
                "app_exists": True,
                "binary_exists": True,
                "user_data_dir": "/tmp/brave",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "profiles": [{"directory": "Default", "name": "Work", "account": "", "path": str(root)}],
            }
        ]

        audit = module.build_account_audit_matrix(
            browsers,
            {"perplexity": {"url": "https://www.perplexity.ai/"}},
            text_dir=None,
        )

        self.assertEqual(audit["rows"][0]["status"], "session-detected-needs-ui-capture")
        self.assertEqual(audit["rows"][0]["session_evidence"]["confidence"], "likely-logged-in")

    def test_cmd_account_audit_outputs_rows_for_browser_provider_inventory(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "chrome",
                "display_name": "Google Chrome",
                "default_port": 9224,
                "app_exists": True,
                "binary_exists": True,
                "user_data_dir": "/tmp/chrome",
                "binary_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "app_path": "/Applications/Google Chrome.app",
                "profiles": [{"directory": "Profile 2", "name": "Work", "account": "profile@example.test"}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["account-audit", "--providers", "chatgpt,google", "--headless"])
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual([row["provider"] for row in payload["rows"]], ["chatgpt", "gemini"])
        self.assertEqual(payload["rows"][0]["profile_account"], "profile@example.test")
        self.assertEqual(payload["rows"][0]["background_plan"]["visibility"], "headless")
        self.assertIn("session_evidence", payload["rows"][0])

    def test_backend_registry_marks_local_and_managed_options(self):
        module = load_module()

        backends = module.backend_registry()

        self.assertIn("playwright-cdp", backends)
        self.assertIn("computer-use", backends)
        self.assertIn("oracle", backends)
        self.assertIn("openai-cua", backends)
        self.assertIn("unbrowser-local", backends)
        self.assertIn("hyperbrowser", backends)
        self.assertEqual(backends["playwright-cdp"]["scope"], "local")
        self.assertIn("@steipete/oracle", backends["oracle"]["aliases"])
        self.assertIn("@unbrowser/local", backends["unbrowser-local"]["aliases"])
        self.assertIn("Operator", " ".join(backends["openai-cua"]["aliases"]))

    def test_unbrowser_plan_outputs_current_local_package(self):
        module = load_module()

        plan = module.build_unbrowser_plan(url="https://example.test", prompt="Extract title", output="/tmp/out.json")

        self.assertEqual(plan["backend"], "unbrowser-local")
        self.assertEqual(plan["package"], "@unbrowser/local")
        self.assertEqual(plan["commands"]["mcp_server"], ["npx", "-y", "@unbrowser/local", "--profile=core"])
        self.assertEqual(plan["json_rpc_call"]["params"]["name"], "quick_fetch")
        self.assertEqual(plan["json_rpc_call"]["params"]["arguments"]["url"], "https://example.test")
        self.assertIn("unbrowser-mcp-probe", plan["commands"]["probe"])

    def test_cdp_attachment_upload_rejects_missing_files_before_browser_call(self):
        module = load_module()

        result = module.set_cdp_file_input_files(9222, [Path("/tmp/definitely-missing-hermes-attachment.png")])

        self.assertEqual(result.returncode, 1)
        self.assertIn("No existing attachment files", result.stderr)

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

    def test_provider_session_evidence_reads_cookie_names_without_values(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        cookie_db = root / "Cookies"
        con = sqlite3.connect(cookie_db)
        con.execute("create table cookies(host_key text, name text)")
        con.executemany(
            "insert into cookies(host_key, name) values (?, ?)",
            [
                (".chatgpt.com", "__Secure-next-auth.session-token.0"),
                (".openrouter.ai", "__session"),
                (".example.test", "other"),
            ],
        )
        con.commit()
        con.close()
        indexed = root / "IndexedDB" / "https_chatgpt.com_0.indexeddb.leveldb"
        indexed.mkdir(parents=True)

        evidence = module.provider_session_evidence({"path": str(root)}, "chatgpt")

        self.assertEqual(evidence["confidence"], "likely-logged-in")
        self.assertIn(".chatgpt.com", evidence["matched_hosts"])
        self.assertIn("__Secure-next-auth.session-token.0", evidence["session_cookie_names"])
        self.assertIn("https_chatgpt.com_0.indexeddb.leveldb", evidence["indexeddb_origins"])

    def test_url_matches_provider_domains(self):
        module = load_module()

        self.assertTrue(module.url_matches_provider("https://gemini.google.com/app/abc", "google"))
        self.assertTrue(module.url_matches_provider("https://auth.openai.com/login", "chatgpt"))
        self.assertFalse(module.url_matches_provider("https://saveai.net/", "gemini"))

    def test_openrouter_session_evidence_detects_clerk_session_cookie(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        con = sqlite3.connect(root / "Cookies")
        con.execute("create table cookies(host_key text, name text)")
        con.execute("insert into cookies(host_key, name) values (?, ?)", (".clerk.openrouter.ai", "__session_NO6jtgZM"))
        con.commit()
        con.close()

        evidence = module.provider_session_evidence({"path": str(root)}, "open-router")

        self.assertEqual(evidence["provider"], "openrouter")
        self.assertEqual(evidence["confidence"], "likely-logged-in")
        self.assertIn("__session_NO6jtgZM", evidence["session_cookie_names"])

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
        self.assertIn("oracle", payload["backends"])
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

    def test_ai_workflow_spec_has_required_research_and_agent_triggers(self):
        module = load_module()

        chatgpt_research = module.provider_workflow_spec("chatgpt", "deep-research")
        chatgpt_agent = module.provider_workflow_spec("chatgpt", "agent")
        gemini_research = module.provider_workflow_spec("google", "deep-research")
        perplexity_research = module.provider_workflow_spec("perplexity", "research")
        grok_research = module.provider_workflow_spec("grok", "research")

        self.assertIn("Deep research", chatgpt_research["feature_triggers"])
        self.assertIn("/Deepresearch", chatgpt_research["slash_triggers"])
        self.assertGreaterEqual(chatgpt_research["pre_confirm_wait_seconds"], 30)
        self.assertIn("Agent", chatgpt_agent["feature_triggers"])
        self.assertIn("/agent", chatgpt_agent["slash_triggers"])
        self.assertIn("Deep Research", gemini_research["feature_triggers"])
        self.assertIn("Start research", gemini_research["confirmation_triggers"])
        self.assertIn("Research", perplexity_research["feature_triggers"])
        self.assertIn("New Chat", grok_research["pre_prompt_triggers"])
        self.assertEqual(grok_research["menu_triggers"], [])

    def test_build_workflow_plan_uses_clone_cdp_and_preserves_live_browser(self):
        module = load_module()

        plan = module.build_ai_workflow_plan(
            browser={"id": "brave", "display_name": "Brave Browser", "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
            profile={"directory": "Profile 2", "name": "work"},
            provider="chatgpt",
            mode="agent",
            prompt="Test prompt",
            artifact_root=Path("/tmp/artifacts"),
            clone_root=Path("/tmp/clones"),
            submit=True,
            confirm_start=True,
            wait_seconds=5,
        )

        self.assertEqual(plan["provider"], "chatgpt")
        self.assertEqual(plan["mode"], "agent")
        self.assertEqual(plan["browser"], "brave")
        self.assertEqual(plan["profile"], "Profile 2")
        self.assertEqual(plan["isolation"], "temporary-profile-clone-cdp")
        self.assertTrue(plan["safety"]["does_not_close_existing_browser_windows"])
        self.assertEqual(plan["actions"][0]["label"], "open-provider")
        self.assertIn("select-feature", [action["label"] for action in plan["actions"]])
        self.assertIn("confirm-start", [action["label"] for action in plan["actions"]])

    def test_build_workflow_plan_records_attachment_step(self):
        module = load_module()

        plan = module.build_ai_workflow_plan(
            browser={"id": "brave", "display_name": "Brave Browser", "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
            profile={"directory": "Profile 2", "name": "work"},
            provider="gemini",
            mode="deep-research",
            prompt="Analyze this image",
            artifact_root=Path("/tmp/artifacts"),
            clone_root=Path("/tmp/clones"),
            attachments=[Path("/tmp/example-image.png")],
        )

        attachment_actions = [action for action in plan["actions"] if action["label"] == "attach-files"]
        self.assertEqual(plan["attachments"], ["/tmp/example-image.png"])
        self.assertEqual(attachment_actions[0]["method"], "cdp-dom-set-file-input-files")
        self.assertEqual(attachment_actions[0]["file_count"], 1)

    def test_snapshot_ref_helpers_prefer_exact_textbox_and_button_refs(self):
        module = load_module()
        snapshot = "\n".join(
            [
                '- link "KI Modelle für Voice-Agent" [ref=e14]',
                '- button "Add files and more" [ref=e34]',
                '- textbox "Chat with ChatGPT" [ref=e35]',
                '- button "Agent" [ref=e42]',
            ]
        )

        self.assertEqual(module.find_snapshot_ref(snapshot, "Add files and more", roles=("button",)), "e34")
        self.assertEqual(module.find_snapshot_ref(snapshot, "Agent", roles=("button",)), "e42")
        self.assertEqual(module.find_composer_ref(snapshot), "e35")

    def test_snapshot_ref_helper_does_not_match_start_dictation_for_start(self):
        module = load_module()
        snapshot = "\n".join(
            [
                '- button "Start dictation" [ref=e47]',
                '- button "Start Voice" [ref=e48]',
            ]
        )

        self.assertEqual(module.find_snapshot_ref(snapshot, "Start", roles=("button",)), "")

    def test_exact_confirmation_ref_accepts_only_real_start_controls(self):
        module = load_module()
        snapshot = "\n".join(
            [
                '- button "Start dictation" [ref=e47]',
                '- button "Start research" [ref=e51]',
            ]
        )

        self.assertEqual(module.find_confirmation_ref(snapshot, ["Start research", "Start"]), "e51")

    def test_composer_js_fill_script_includes_prompt_and_dispatches_input(self):
        module = load_module()

        script = module.composer_js_fill_script("hello")

        self.assertIn("hello", script)
        self.assertIn("InputEvent", script)
        self.assertIn("contenteditable", script)

    def test_click_text_js_script_clicks_visible_text_without_voice_controls(self):
        module = load_module()

        script = module.click_text_js_script("Agent")

        self.assertIn("Agent", script)
        self.assertIn("dictation", script)
        self.assertIn("el.click()", script)

    def test_wait_milliseconds_returns_integer_agent_browser_wait_arg(self):
        module = load_module()

        self.assertEqual(module.wait_milliseconds(1.671, maximum_ms=3000), "1671")
        self.assertEqual(module.wait_milliseconds(0.2, maximum_ms=3000), "1000")
        self.assertEqual(module.wait_milliseconds(9.0, maximum_ms=3000), "3000")

    def test_extract_workflow_output_prefers_provider_report_selectors(self):
        module = load_module()

        body = "\n".join(
            [
                "ChatGPT",
                "Sources",
                "Research complete",
                "Final answer",
                "The result text",
            ]
        )
        extracted = module.extract_workflow_output_from_text(body, provider="chatgpt", mode="deep-research")

        self.assertEqual(extracted["status"], "complete")
        self.assertIn("The result text", extracted["text"])

    def test_chatgpt_deep_research_sources_ui_alone_is_not_complete(self):
        module = load_module()

        extracted = module.extract_workflow_output_from_text(
            "Deep research\nSites, search the web, no sites saved\nSources",
            provider="chatgpt",
            mode="deep-research",
        )

        self.assertEqual(extracted["status"], "captured")
        self.assertEqual(extracted["completion_markers_found"], [])

    def test_cmd_workflow_plan_outputs_safe_json(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9222,
                "profiles": [{"directory": "Profile 2", "name": "work", "account": ""}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-plan",
                        "--browser",
                        "brave",
                        "--profile",
                        "work",
                        "--provider",
                        "chatgpt",
                        "--mode",
                        "deep-research",
                        "--prompt",
                        "Find sources",
                        "--submit",
                        "--confirm-start",
                    ]
                )
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["profile"], "Profile 2")
        self.assertTrue(payload["safety"]["uses_profile_clone"])
        self.assertTrue(payload["submit"])
        self.assertTrue(payload["confirm_start"])

    def test_workflow_suite_targets_include_primary_agent_and_research_features(self):
        module = load_module()

        targets = module.workflow_suite_targets()
        pairs = {(target["provider"], target["mode"]) for target in targets}

        self.assertIn(("chatgpt", "agent"), pairs)
        self.assertIn(("chatgpt", "deep-research"), pairs)
        self.assertIn(("gemini", "deep-research"), pairs)
        self.assertIn(("perplexity", "research"), pairs)
        self.assertIn(("grok", "research"), pairs)
        self.assertIn(("claude", "research"), pairs)

    def test_cmd_workflow_suite_plan_outputs_clone_rows(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9222,
                "profiles": [{"directory": "Profile 2", "name": "work", "account": "", "path": ""}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--browsers",
                        "brave",
                        "--profile",
                        "work",
                        "--providers",
                        "chatgpt",
                        "--features",
                        "chatgpt:agent,chatgpt:deep-research",
                        "--plan-only",
                        "--submit",
                        "--confirm-start",
                    ]
                )
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "planned")
        self.assertTrue(payload["submit"])
        self.assertEqual([row["mode"] for row in payload["rows"]], ["agent", "deep-research"])
        self.assertEqual(payload["rows"][0]["profile_directory"], "Profile 2")

    def test_compact_workflow_run_payload_omits_large_command_logs(self):
        module = load_module()

        compact = module.compact_workflow_run_payload(
            {
                "status": "verified",
                "status_json": "/tmp/status.json",
                "commands": [{"stdout": "x" * 10000}],
                "inventory": {"provider": "grok", "visible_status": {"account": "a@test"}, "usage_lines": ["large"]},
                "output": {"status": "complete", "text": "large", "text_length": 5},
                "clone": {"clone_user_data": "/tmp/example/user-data", "source_profile": "/source", "profile_directory": "Default"},
            }
        )

        self.assertEqual(compact["status"], "verified")
        self.assertNotIn("commands", compact)
        self.assertNotIn("text", compact["output"])
        self.assertEqual(compact["output"]["text_length"], 5)

    def test_workflow_followup_reopens_chat_sends_prompt_and_exports_markdown(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        profile.mkdir(parents=True)
        (profile / "Preferences").write_text("{}", encoding="utf-8")
        (source / "Local State").write_text("{}", encoding="utf-8")
        root = Path(tempfile.mkdtemp())

        class FakeProcess:
            pid = 12345

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

        fake_process = FakeProcess()
        original_find_port = module.find_available_port
        original_start = module.start_clone_cdp_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_key = module.run_cdp_keypress
        original_capture = module.capture_cdp_screenshot
        module.find_available_port = lambda: 9446
        module.start_clone_cdp_browser = lambda **kwargs: (
            fake_process,
            {"ok": True, "port": kwargs["port"], "launch_args": kwargs["launch_args"], "pid": fake_process.pid},
        )
        module.run_cdp_navigate = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/abc", "")
            if "const text =" in script:
                return module.subprocess.CompletedProcess(["js"], 0, '{"ok":true}', "")
            return module.subprocess.CompletedProcess(["js"], 0, "ChatGPT\nIsagi yoichi\nPro\nFinal answer\nKurzfassung", "")

        module.run_cdp_javascript = fake_js
        module.run_cdp_keypress = lambda port, key, timeout=10.0: module.subprocess.CompletedProcess(["key"], 0, "ok", "")
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        try:
            payload = module.agent_browser_profile_followup_run(
                browser={"id": "brave", "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "user_data_dir": str(source)},
                profile={"directory": "Default", "path": str(profile)},
                provider="chatgpt",
                chat_url="https://chatgpt.com/c/abc",
                prompt="Fass zusammen",
                artifact_root=root / "artifacts",
                clone_root=root / "clones",
                wait_seconds=1,
                cache_root=root / "cache",
            )
        finally:
            module.find_available_port = original_find_port
            module.start_clone_cdp_browser = original_start
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.run_cdp_keypress = original_key
            module.capture_cdp_screenshot = original_capture

        self.assertEqual(payload["status"], "verified")
        self.assertTrue(Path(payload["export_markdown"]).exists())
        self.assertTrue(Path(payload["cache"]["text_path"]).exists())
        self.assertTrue(getattr(fake_process, "terminated", False))


if __name__ == "__main__":
    unittest.main()
