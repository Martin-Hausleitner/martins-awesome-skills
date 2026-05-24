from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

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

    def test_work_alias_falls_back_to_single_profile(self):
        module = load_module()

        resolved = module.resolve_profile(
            [{"directory": "Default", "name": "Neptune", "account": "", "account_state": "signed-in-hidden"}],
            "work",
        )

        self.assertEqual(resolved["name"], "Neptune")

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

    def test_parse_grok_free_plan_from_account_with_supergrok_upsell(self):
        module = load_module()

        status = module.parse_visible_status(
            "kleinstein.fragen@gmail.com\n"
            "What do you want to know?\n"
            "Fast\n"
            "Connectors allow Grok to interact with apps directly in conversations.\n"
            "Unlock extended capabilities\n"
            "Try for $0.00",
            provider="grok",
        )

        self.assertEqual(status["account"], "kleinstein.fragen@gmail.com")
        self.assertEqual(status["plan"], "Free")
        self.assertEqual(status["model"], "Fast")

    def test_parse_grok_model_ignores_history_explore_titles(self):
        module = load_module()

        status = module.parse_visible_status(
            "kleinstein.fragen@gmail.com\n"
            "Grok Modellentwicklung erkunden\n"
            "Fast\n"
            "Unlock extended capabilities\n"
            "Try for $0.00",
            provider="grok",
        )

        self.assertEqual(status["model"], "Fast")

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

    def test_parse_claude_account_from_user_menu_aria(self):
        module = load_module()

        status = module.parse_visible_status(
            "M Martin Max plan\nOpus 4.7 Adaptive\nMartin, Settings",
            provider="claude",
        )

        self.assertEqual(status["account"], "Martin")
        self.assertEqual(status["plan"], "Max")

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

    def test_gemini_conversation_markers_override_side_login_text(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "gemini",
            "Gemini\nAnmelden\nNew chat\nUnterhaltung mit Gemini\nDu hast gesagt\nGemini hat gesagt\n"
            "Safe Browser Automation Practices in 2026\nTools\nFlash\nDeep Research",
        )

        self.assertEqual(inventory["login_state"], "signed-in-or-ready")

    def test_research_text_about_cloudflare_is_not_a_login_wall(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "gemini",
            "Unterhaltung mit Gemini\nDu hast gesagt\nGemini hat gesagt\n"
            "A report about Cloudflare Turnstile and safe browser automation practices.",
        )

        self.assertEqual(inventory["login_state"], "signed-in-or-ready")

    def test_provider_login_urls_are_hard_login_walls(self):
        module = load_module()

        self.assertTrue(module.url_indicates_login_wall("https://claude.ai/login?from=logout", "claude"))
        self.assertTrue(module.url_indicates_login_wall("https://accounts.google.com/v3/signin/identifier", "chatgpt"))
        self.assertFalse(module.url_indicates_login_wall("https://claude.ai/chat/abc123", "claude"))

    def test_browser_live_cdp_defaults_do_not_assign_brave_to_9222(self):
        module = load_module()

        self.assertEqual(module.BROWSER_CANDIDATES["brave"]["default_port"], 9223)
        self.assertEqual(module.BROWSER_CANDIDATES["comet"]["default_port"], 9333)

    def test_strategy_router_prefers_live_cdp_then_restart_then_blocks_without_explicit_sibling(self):
        module = load_module()

        live = module.choose_workflow_strategy(
            requested="auto",
            real_session_preflight={"can_attach": True, "blockers": []},
            allow_browser_restart=False,
            sibling_available=True,
        )
        restart = module.choose_workflow_strategy(
            requested="auto",
            real_session_preflight={"can_attach": False, "blockers": ["browser-running-without-remote-debugging"]},
            allow_browser_restart=True,
            sibling_available=True,
        )
        sibling = module.choose_workflow_strategy(
            requested="auto",
            real_session_preflight={"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"]},
            allow_browser_restart=False,
            sibling_available=True,
        )
        explicit_sibling = module.choose_workflow_strategy(
            requested="auto",
            real_session_preflight={"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"]},
            allow_browser_restart=False,
            sibling_available=True,
            allow_sibling_fallback=True,
        )

        self.assertEqual(live["strategy"], "live-cdp")
        self.assertEqual(restart["strategy"], "restart-cdp")
        self.assertEqual(sibling["strategy"], "blocked")
        self.assertEqual(explicit_sibling["strategy"], "persistent-sibling")
        self.assertEqual(restart["rejected"][0]["strategy"], "live-cdp")

    def test_workflow_run_auto_blocks_instead_of_starting_sibling_without_allow_flag(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_preflight = module.build_real_session_preflight
        original_sibling = module.run_sibling_workflow_payload
        sibling_called = {"value": False}
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9223,
                "profiles": [{"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"}],
            }
        ]
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"], "session_evidence": {}}

        def fake_sibling(**kwargs):
            sibling_called["value"] = True
            return {"status": "opened"}

        module.run_sibling_workflow_payload = fake_sibling
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-run",
                        "--browser",
                        "brave",
                        "--profile",
                        "work",
                        "--provider",
                        "chatgpt",
                        "--mode",
                        "chat",
                        "--prompt",
                        "Say READY",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.build_real_session_preflight = original_preflight
            module.run_sibling_workflow_payload = original_sibling

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(sibling_called["value"])
        self.assertEqual(payload["strategy"]["strategy"], "blocked")
        self.assertFalse(payload["sibling_fallback_allowed"])

    def test_workflow_run_oracle_runner_is_blocked_by_local_guards(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_preflight = module.build_real_session_preflight
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9223,
                "profiles": [{"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"}],
            }
        ]
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"], "session_evidence": {}}
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-run",
                        "--browser",
                        "brave",
                        "--profile",
                        "work",
                        "--provider",
                        "chatgpt",
                        "--mode",
                        "agent",
                        "--prompt",
                        "Debug Oracle runner",
                        "--oracle-mode",
                        "runner",
                        "--allow-paid-quota-use",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.build_real_session_preflight = original_preflight

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["oracle"]["mode"], "runner")
        self.assertEqual(payload["oracle"]["runner_status"], "blocked-by-local-guards")
        self.assertTrue(payload["oracle"]["reattach_available"])

    def test_workflow_run_sibling_fallback_requires_explicit_allow_flag(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_preflight = module.build_real_session_preflight
        original_sibling = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9223,
                "profiles": [{"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"}],
            }
        ]
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"], "session_evidence": {}}
        sibling_calls = []

        def fake_sibling(**kwargs):
            sibling_calls.append(kwargs)
            return {"status": "opened", "inventory": {"login_state": "signed-in-or-ready"}, "screenshot": "/tmp/s.png"}

        module.run_sibling_workflow_payload = fake_sibling
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-run",
                        "--browser",
                        "brave",
                        "--profile",
                        "work",
                        "--provider",
                        "chatgpt",
                        "--mode",
                        "chat",
                        "--prompt",
                        "Say READY",
                        "--allow-sibling-fallback",
                        "--allow-paid-quota-use",
                        "--pacing",
                        "normal",
                        "--min-action-delay-ms",
                        "2500",
                        "--max-daily-paid-runs",
                        "3",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.build_real_session_preflight = original_preflight
            module.run_sibling_workflow_payload = original_sibling

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["sibling_fallback_allowed"])
        self.assertEqual(payload["strategy"]["strategy"], "persistent-sibling")
        self.assertEqual(len(sibling_calls), 1)
        self.assertFalse(sibling_calls[0]["allow_active_tab_navigation_fallback"])
        self.assertTrue(sibling_calls[0]["allow_paid_quota_use"])
        self.assertEqual(sibling_calls[0]["pacing"], "normal")
        self.assertEqual(sibling_calls[0]["min_action_delay_ms"], 2500)
        self.assertEqual(sibling_calls[0]["max_daily_paid_runs"], 3)

    def test_real_session_preflight_blocks_wrong_cdp_port_owner_even_when_endpoint_answers(self):
        module = load_module()
        original_endpoint = module.detect_cdp_endpoint
        original_owner = module.lsof_port_owner
        original_main_args = module.browser_main_process_args
        original_session = module.provider_session_evidence
        original_pid_args = getattr(module, "process_args_for_pid", None)
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": "http://127.0.0.1:9222", "version": {"Browser": "Chrome/148"}, "attempts": []}
        module.lsof_port_owner = lambda port: {"port": port, "listening": True, "command": "Code Helper", "pid": "296", "raw": "Code Helper 296 mh TCP 127.0.0.1:9222"}
        module.browser_main_process_args = lambda browser: ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
        module.provider_session_evidence = lambda profile, provider: {"confidence": "likely-logged-in"}
        module.process_args_for_pid = lambda pid: "/Applications/Code Helper.app/Contents/MacOS/Code Helper --remote-debugging-port=9222"
        try:
            preflight = module.build_real_session_preflight(
                browser={"id": "brave", "display_name": "Brave Browser", "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "user_data_dir": "/tmp/brave"},
                profile={"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"},
                provider="chatgpt",
                port=9222,
            )
        finally:
            module.detect_cdp_endpoint = original_endpoint
            module.lsof_port_owner = original_owner
            module.browser_main_process_args = original_main_args
            module.provider_session_evidence = original_session
            if original_pid_args is not None:
                module.process_args_for_pid = original_pid_args

        self.assertFalse(preflight["can_attach"])
        self.assertIn("cdp-port-owned-by-unexpected-process", preflight["blockers"])
        self.assertFalse(preflight["cdp_owner_verification"]["owner_matches_browser"])

    def test_real_session_preflight_accepts_user_data_dir_with_spaces(self):
        module = load_module()
        original_endpoint = module.detect_cdp_endpoint
        original_owner = module.lsof_port_owner
        original_main_args = module.browser_main_process_args
        original_session = module.provider_session_evidence
        original_pid_args = getattr(module, "process_args_for_pid", None)
        user_data = "/Users/example/Library/Application Support/BraveSoftware/Brave-Browser"
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": "http://127.0.0.1:9223", "version": {"Browser": "Chrome/148"}, "attempts": []}
        module.lsof_port_owner = lambda port: {"port": port, "listening": True, "command": "Brave\\x20", "pid": "27886", "raw": ""}
        module.browser_main_process_args = lambda browser: [
            f"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser --remote-debugging-port=9223 --user-data-dir={user_data} --profile-directory=Default"
        ]
        module.provider_session_evidence = lambda profile, provider: {"confidence": "likely-logged-in"}
        module.process_args_for_pid = lambda pid: (
            f"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser --remote-debugging-port=9223 --user-data-dir={user_data} --profile-directory=Default"
        )
        try:
            preflight = module.build_real_session_preflight(
                browser={
                    "id": "brave",
                    "display_name": "Brave Browser",
                    "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                    "user_data_dir": user_data,
                    "default_port": 9223,
                },
                profile={"directory": "Default", "name": "Work", "path": f"{user_data}/Default"},
                provider="chatgpt",
                port=9223,
            )
        finally:
            module.detect_cdp_endpoint = original_endpoint
            module.lsof_port_owner = original_owner
            module.browser_main_process_args = original_main_args
            module.provider_session_evidence = original_session
            if original_pid_args is not None:
                module.process_args_for_pid = original_pid_args

        self.assertTrue(preflight["can_attach"])
        self.assertEqual(preflight["blockers"], [])
        self.assertTrue(preflight["cdp_owner_verification"]["ok"])
        self.assertTrue(preflight["cdp_owner_verification"]["user_data_dir_matches"])

    def test_strategy_router_never_treats_clone_as_real_login_path(self):
        module = load_module()

        choice = module.choose_workflow_strategy(
            requested="diagnostic-clone",
            real_session_preflight={"can_attach": False, "blockers": ["cdp-endpoint-not-reachable"]},
            allow_browser_restart=False,
            sibling_available=False,
        )

        self.assertEqual(choice["strategy"], "diagnostic-clone")
        self.assertFalse(choice["counts_as_real_login"])

    def test_account_baseline_requires_ready_login_account_plan_and_screenshot(self):
        module = load_module()

        baseline = module.build_account_baseline(
            {
                "provider": "chatgpt",
                "login_state": "signed-in-or-ready",
                "visible_status": {"account": "martin@example.test", "plan": "Pro", "model": "GPT-5.5"},
                "available_models": ["GPT-5.5"],
                "available_tools": ["Deep research"],
                "available_modes": {"chat": True, "deep-research": True},
            },
            screenshot="/tmp/screen.png",
        )
        incomplete = module.build_account_baseline(
            {
                "provider": "chatgpt",
                "login_state": "unknown",
                "visible_status": {"account": "", "plan": ""},
                "available_models": [],
                "available_tools": [],
                "available_modes": {},
            },
            screenshot="",
        )

        self.assertTrue(baseline["ready_for_prompt"])
        self.assertEqual(baseline["account"], "martin@example.test")
        self.assertFalse(incomplete["ready_for_prompt"])
        self.assertIn("login-not-ready", incomplete["missing"])
        self.assertIn("screenshot-missing", incomplete["missing"])

    def test_build_browser_cdp_recover_plan_is_safe_dry_run_by_default(self):
        module = load_module()
        browser = {
            "id": "brave",
            "display_name": "Brave Browser",
            "app_path": "/Applications/Brave Browser.app",
            "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "user_data_dir": "/tmp/brave",
        }
        profile = {"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"}

        plan = module.build_browser_cdp_recover_plan(
            browser=browser,
            profile=profile,
            provider="chatgpt",
            port=9444,
        )

        self.assertEqual(plan["strategy"], "restart-cdp")
        self.assertTrue(plan["approval_required"])
        self.assertFalse(plan["will_execute"])
        self.assertIn("--remote-debugging-port=9444", plan["launch_args"])
        self.assertIn("--restore-last-session", plan["launch_args"])
        self.assertEqual(plan["snapshot"]["status"], "planned")

    def test_create_automation_target_command_reports_background_target_without_minimizing(self):
        module = load_module()
        captured = {}

        def fake_run(command, capture_output, text, timeout, env=None, check=False):
            captured["command"] = command
            return module.subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"ok": True, "targetId": "target-1", "windowId": 7, "bounds": "background"}),
                stderr="",
            )

        original_run = module.subprocess.run
        module.subprocess.run = fake_run
        try:
            result = module.run_cdp_create_automation_target(9222, "https://chatgpt.com/", timeout=3)
        finally:
            module.subprocess.run = original_run

        self.assertEqual(result.returncode, 0)
        self.assertIn("Target.createTarget", captured["command"][3])
        self.assertNotIn("Browser.setWindowBounds", captured["command"][3])
        self.assertEqual(json.loads(result.stdout)["targetId"], "target-1")

    def test_cmd_browser_cdp_recover_dry_run_outputs_restart_plan(self):
        module = load_module()
        original_discover = module.discover_browsers
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "app_path": "/Applications/Brave Browser.app",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": "/tmp/brave",
                "default_port": 9444,
                "profiles": [{"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"}],
            }
        ]
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["browser-cdp-recover", "--browser", "brave", "--profile", "work", "--provider", "chatgpt", "--dry-run"])
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["strategy"], "restart-cdp")
        self.assertTrue(payload["dry_run"])
        self.assertIn("--remote-debugging-address=127.0.0.1", payload["launch_args"])

    def test_browser_cdp_recover_plan_uses_free_port_when_requested_port_has_wrong_owner(self):
        module = load_module()
        original_preflight = module.build_real_session_preflight
        original_find_port = module.find_available_port

        def fake_preflight(**kwargs):
            if kwargs["port"] == 9333:
                return {
                    "can_attach": False,
                    "blockers": ["port-listener-is-not-cdp", "cdp-port-owned-by-unexpected-process"],
                    "port_owner": {"listening": True, "command": "Code Helper"},
                    "cdp_endpoint": {"ok": False},
                }
            return {
                "can_attach": False,
                "blockers": ["cdp-endpoint-not-reachable"],
                "port_owner": {"listening": False},
                "cdp_endpoint": {"ok": False},
            }

        module.build_real_session_preflight = fake_preflight
        module.find_available_port = lambda: 9523
        try:
            plan = module.build_browser_cdp_recover_plan(
                browser={
                    "id": "comet",
                    "display_name": "Comet",
                    "app_path": "/Applications/Comet.app",
                    "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                    "user_data_dir": "/tmp/comet",
                },
                profile={"directory": "Default", "name": "Work", "path": "/tmp/comet/Default"},
                provider="google",
                port=9333,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.find_available_port = original_find_port

        self.assertEqual(plan["requested_port"], 9333)
        self.assertEqual(plan["port"], 9523)
        self.assertTrue(plan["port_selection"]["fallback_used"])
        self.assertIn("--remote-debugging-port=9523", plan["launch_args"])

    def test_lsof_port_owner_prefers_real_debug_browser_over_code_helper_on_dual_stack_port(self):
        module = load_module()
        original_owners = module.lsof_port_owners
        original_args = module.process_args_for_pid
        module.lsof_port_owners = lambda port: [
            {
                "port": port,
                "listening": True,
                "command": "Code\\x20H",
                "pid": "111",
                "raw": "header\nCode Helper\nComet\n",
                "line": "Code Helper 111 mh TCP 127.0.0.1:9334 (LISTEN)",
            },
            {
                "port": port,
                "listening": True,
                "command": "Comet",
                "pid": "222",
                "raw": "header\nCode Helper\nComet\n",
                "line": "Comet 222 mh TCP [::1]:9334 (LISTEN)",
            },
        ]
        module.process_args_for_pid = lambda pid: (
            "/Applications/Comet.app/Contents/MacOS/Comet --remote-debugging-port=9334"
            if str(pid) == "222"
            else "/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper.app/Contents/MacOS/Code Helper"
        )
        try:
            owner = module.lsof_port_owner(9334)
        finally:
            module.lsof_port_owners = original_owners
            module.process_args_for_pid = original_args

        self.assertEqual(owner["command"], "Comet")
        self.assertEqual(owner["pid"], "222")

    def test_recovery_launch_command_uses_macos_open_for_app_bundles(self):
        module = load_module()
        launch_args = [
            "/Applications/Comet.app/Contents/MacOS/Comet",
            "--remote-debugging-port=9334",
            "--user-data-dir=/tmp/comet",
            "about:blank",
        ]
        with mock.patch.object(module.sys, "platform", "darwin"), mock.patch.object(module.Path, "exists", return_value=True):
            command, method = module.recovery_launch_command({"app_path": "/Applications/Comet.app"}, launch_args)

        self.assertEqual(method, "macos-open-new-instance")
        self.assertEqual(command[:5], ["open", "-g", "-na", "/Applications/Comet.app", "--args"])
        self.assertIn("--remote-debugging-port=9334", command)

    def test_restart_recovery_execute_requires_confirm_or_explicit_no_popup(self):
        module = load_module()
        original_preflight = module.build_real_session_preflight
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": False, "blockers": ["browser-running-without-remote-debugging"], "session_evidence": {}}
        try:
            payload = module.execute_browser_cdp_recover(
                browser={
                    "id": "brave",
                    "display_name": "Brave Browser",
                    "app_path": "/Applications/Brave Browser.app",
                    "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                    "user_data_dir": "/tmp/brave",
                },
                profile={"directory": "Default", "name": "Work", "path": "/tmp/brave/Default"},
                provider="chatgpt",
                port=9223,
                confirm_restart=False,
                no_popup=False,
            )
        finally:
            module.build_real_session_preflight = original_preflight

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("requires --confirm-restart", payload["blocker"])

    def test_restart_recovery_execute_blocks_on_empty_snapshot_before_quit(self):
        module = load_module()
        original_preflight = module.build_real_session_preflight
        original_confirm = module.confirm_cdp_restart_popup
        original_snapshot = module.snapshot_macos_browser_windows
        original_run = module.subprocess.run
        confirm_calls = {"count": 0}
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": False,
            "blockers": ["cdp-endpoint-not-reachable"],
            "port_owner": {"listening": False},
            "cdp_endpoint": {"ok": False},
        }
        def fake_confirm(plan):
            confirm_calls["count"] += 1
            return {"shown": True, "accepted": True}

        module.confirm_cdp_restart_popup = fake_confirm
        module.snapshot_macos_browser_windows = lambda *args, **kwargs: {
            "status": "captured",
            "window_count": 0,
            "tab_count": 0,
            "path": "/tmp/empty-tabs.json",
        }

        def fail_if_quit(command, *args, **kwargs):
            if command[:2] == ["osascript", "-e"] and "quit" in command[-1]:
                raise AssertionError("browser quit should not run when snapshot is empty")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        module.subprocess.run = fail_if_quit
        try:
            payload = module.execute_browser_cdp_recover(
                browser={
                    "id": "comet",
                    "display_name": "Comet",
                    "app_path": "/Applications/Comet.app",
                    "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                    "user_data_dir": "/tmp/comet",
                },
                profile={"directory": "Default", "name": "Work", "path": "/tmp/comet/Default"},
                provider="google",
                port=9523,
                confirm_restart=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.confirm_cdp_restart_popup = original_confirm
            module.snapshot_macos_browser_windows = original_snapshot
            module.subprocess.run = original_run

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("non-empty browser window/tab snapshot", payload["blocker"])
        self.assertEqual(confirm_calls["count"], 0)
        self.assertFalse(payload["confirmation"]["shown"])
        self.assertTrue(payload["quit"]["skipped"])

    def test_restart_recovery_execute_requires_post_launch_owner_verification(self):
        module = load_module()
        original_preflight = module.build_real_session_preflight
        original_confirm = module.confirm_cdp_restart_popup
        original_snapshot = module.snapshot_macos_browser_windows
        original_run = module.subprocess.run
        original_popen = module.subprocess.Popen
        original_detect = module.detect_cdp_endpoint

        calls = {"preflight": 0}

        def fake_preflight(**kwargs):
            calls["preflight"] += 1
            if calls["preflight"] >= 2:
                return {
                    "can_attach": False,
                    "blockers": ["cdp-port-owned-by-unexpected-process"],
                    "port_owner": {"listening": True, "command": "Code Helper"},
                    "cdp_endpoint": {"ok": True},
                }
            return {
                "can_attach": False,
                "blockers": ["cdp-endpoint-not-reachable"],
                "port_owner": {"listening": False},
                "cdp_endpoint": {"ok": False},
            }

        class FakeProcess:
            pid = 4242

            def poll(self):
                return None

        module.build_real_session_preflight = fake_preflight
        module.confirm_cdp_restart_popup = lambda plan: {"shown": True, "accepted": True}
        module.snapshot_macos_browser_windows = lambda *args, **kwargs: {
            "status": "captured",
            "window_count": 1,
            "tab_count": 2,
            "path": "/tmp/tabs.json",
            "browser_was_frontmost": False,
        }
        module.subprocess.run = lambda command, *args, **kwargs: module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        module.subprocess.Popen = lambda *args, **kwargs: FakeProcess()
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": f"http://127.0.0.1:{port}", "version": {"Browser": "Chrome"}}
        try:
            payload = module.execute_browser_cdp_recover(
                browser={
                    "id": "comet",
                    "display_name": "Comet",
                    "app_path": "/Applications/Comet.app",
                    "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                    "user_data_dir": "/tmp/comet",
                },
                profile={"directory": "Default", "name": "Work", "path": "/tmp/comet/Default"},
                provider="google",
                port=9523,
                confirm_restart=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.confirm_cdp_restart_popup = original_confirm
            module.snapshot_macos_browser_windows = original_snapshot
            module.subprocess.run = original_run
            module.subprocess.Popen = original_popen
            module.detect_cdp_endpoint = original_detect

        self.assertEqual(payload["status"], "restart-failed")
        self.assertIn("post-launch CDP owner/profile verification failed", payload["blocker"])
        self.assertIn("cdp-port-owned-by-unexpected-process", payload["post_launch_preflight"]["blockers"])

    def test_compact_workflow_payload_preserves_strategy_target_and_baseline(self):
        module = load_module()

        compact = module.compact_workflow_run_payload(
            {
                "status": "verified",
                "strategy": {"selected": "live-cdp"},
                "target_id": "target-1",
                "account_baseline": {"status": "ready", "account": "work@example.test"},
                "inventory": {"login_state": "signed-in-or-ready"},
                "output": {"text_length": 42},
            }
        )

        self.assertEqual(compact["strategy"]["selected"], "live-cdp")
        self.assertEqual(compact["target_id"], "target-1")
        self.assertEqual(compact["account_baseline"]["account"], "work@example.test")

    def test_cdp_helpers_accept_target_id_and_pass_it_to_node_bridge(self):
        module = load_module()
        original_detect = module.detect_cdp_endpoint
        original_run = module.subprocess.run
        commands = []
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": "http://127.0.0.1:9444"}

        def fake_run(command, **kwargs):
            commands.append(command)
            return module.subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        module.subprocess.run = fake_run
        try:
            module.run_cdp_javascript(9444, "location.href", target_id="automation-target-1")
            module.run_cdp_keypress(9444, "Enter", target_id="automation-target-1")
            module.run_cdp_navigate(9444, "https://chatgpt.com/", target_id="automation-target-1")
        finally:
            module.detect_cdp_endpoint = original_detect
            module.subprocess.run = original_run

        self.assertTrue(all("automation-target-1" in command for command in commands))
        self.assertTrue(all("targetId" in command[3] for command in commands))
        self.assertTrue(all("Requested CDP target not found" in command[3] for command in commands))
        self.assertEqual(commands[0][-1], "0")

    def test_cdp_javascript_can_request_all_contexts(self):
        module = load_module()
        original_detect = module.detect_cdp_endpoint
        original_run = module.subprocess.run
        commands = []
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": "http://127.0.0.1:9444"}

        def fake_run(command, **kwargs):
            commands.append(command)
            return module.subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        module.subprocess.run = fake_run
        try:
            module.run_cdp_javascript(9444, "document.body.innerText", target_id="automation-target-1", all_contexts=True)
        finally:
            module.detect_cdp_endpoint = original_detect
            module.subprocess.run = original_run

        self.assertEqual(commands[0][-2], "automation-target-1")
        self.assertEqual(commands[0][-1], "1")

    def test_chatgpt_pro_thinking_counts_as_running_and_is_cleaned(self):
        module = load_module()

        output = module.extract_workflow_output_from_text("Pro thinking\nExtended Pro", provider="chatgpt", mode="chat")
        cleaned = module.clean_workflow_response_text("Pro thinking\nBRAVE_CHATGPT_E2E_OK\nExtended Pro", provider="chatgpt")

        self.assertEqual(output["status"], "running")
        self.assertIn("Pro thinking", output["running_markers_found"])
        self.assertEqual(cleaned, "BRAVE_CHATGPT_E2E_OK")

    def test_recovery_snapshot_file_is_redacted_by_default(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_run = module.subprocess.run
        full_url = "https://chatgpt.com/c/private-secret?token=abc"

        def fake_run(command, **kwargs):
            payload = {
                "appName": "Brave Browser",
                "frontmost": "Notes",
                "browserWasFrontmost": False,
                "windows": [{"index": 0, "activeTabIndex": 0, "tabs": [{"index": 0, "title": "Secret chat", "url": full_url}]}],
            }
            return module.subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        module.subprocess.run = fake_run
        try:
            snapshot = module.snapshot_macos_browser_windows({"id": "brave", "display_name": "Brave Browser"}, artifact_root=root)
        finally:
            module.subprocess.run = original_run

        saved = Path(snapshot["path"]).read_text(encoding="utf-8")
        self.assertNotIn(full_url, saved)
        self.assertNotIn("private-secret", saved)
        self.assertIn("chatgpt.com", saved)

    def test_recovery_snapshot_timeout_returns_best_effort_failed(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_run = module.subprocess.run

        def fake_run(command, **kwargs):
            raise module.subprocess.TimeoutExpired(command, 8, output="", stderr="hung")

        module.subprocess.run = fake_run
        try:
            snapshot = module.snapshot_macos_browser_windows({"id": "comet", "display_name": "Comet"}, artifact_root=root)
        finally:
            module.subprocess.run = original_run

        self.assertEqual(snapshot["status"], "best-effort-failed")
        self.assertEqual(snapshot["window_count"], 0)
        self.assertIn("timed out", Path(snapshot["path"]).read_text(encoding="utf-8").casefold())

    def test_recovery_snapshot_falls_back_to_chromium_session_files_redacted(self):
        module = load_module()
        original_run = module.subprocess.run

        def fake_run(command, **kwargs):
            return module.subprocess.CompletedProcess(command, 1, stdout="", stderr="window api unavailable")

        module.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sessions = root / "Profile 1" / "Sessions"
                sessions.mkdir(parents=True)
                (sessions / "Session_1").write_bytes(
                    b"prefix https://gemini.google.com/app/private-chat?token=secret\x00"
                    b" middle https://claude.ai/chat/private-id\x00"
                )
                snapshot = module.snapshot_macos_browser_windows(
                    {"id": "comet", "display_name": "Comet", "user_data_dir": str(root)},
                    artifact_root=root / "artifacts",
                    profile_directory="Profile 1",
                )
                saved = Path(snapshot["path"]).read_text(encoding="utf-8")
        finally:
            module.subprocess.run = original_run

        self.assertEqual(snapshot["status"], "captured")
        self.assertEqual(snapshot["method"], "chromium-session-files")
        self.assertEqual(snapshot["fallback_from"], "macos-window-snapshot")
        self.assertEqual(snapshot["tab_count"], 2)
        self.assertIn("gemini.google.com", saved)
        self.assertIn("claude.ai", saved)
        self.assertNotIn("private-chat", saved)
        self.assertNotIn("secret", saved)

    def test_restart_confirmation_timeout_is_non_destructive_cancel(self):
        module = load_module()
        original_run = module.subprocess.run

        def fake_timeout(command, **kwargs):
            raise module.subprocess.TimeoutExpired(command, 120, output="", stderr="")

        module.subprocess.run = fake_timeout
        try:
            confirmation = module.confirm_cdp_restart_popup({"browser_name": "Comet", "profile_directory": "Default", "port": 9333})
        finally:
            module.subprocess.run = original_run

        self.assertTrue(confirmation["shown"])
        self.assertFalse(confirmation["accepted"])
        self.assertTrue(confirmation["timed_out"])

    def test_provider_session_evidence_removes_cookie_temp_copies(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        profile = root / "Default"
        network = profile / "Network"
        network.mkdir(parents=True)
        con = sqlite3.connect(network / "Cookies")
        con.execute("create table cookies(host_key text, name text)")
        con.execute("insert into cookies(host_key, name) values (?, ?)", (".chatgpt.com", "__Secure-next-auth.session-token"))
        con.commit()
        con.close()
        original_tempdir = module.tempfile.tempdir
        temp_root = root / "tmp"
        temp_root.mkdir()
        module.tempfile.tempdir = str(temp_root)
        try:
            evidence = module.provider_session_evidence({"path": str(profile)}, "chatgpt")
        finally:
            module.tempfile.tempdir = original_tempdir

        self.assertEqual(evidence["confidence"], "likely-logged-in")
        self.assertEqual(list(temp_root.glob("ai-research-cookie-scan-*")), [])

    def test_command_log_redaction_removes_prompt_urls_and_stdout(self):
        module = load_module()

        redacted = module.redact_command_log_entry(
            {
                "label": "fill-prompt-js",
                "args": ["agent-browser", "eval", "document.body.innerText = 'secret prompt https://chatgpt.com/c/private'"],
                "stdout": "secret prompt response",
                "stderr": "https://accounts.google.com/private",
            },
            privacy="redacted",
        )

        self.assertNotIn("secret prompt", json.dumps(redacted))
        self.assertNotIn("chatgpt.com/c/private", json.dumps(redacted))
        self.assertIn("<redacted", json.dumps(redacted))

    def test_typing_guard_requires_feature_evidence_and_paid_confirmation(self):
        module = load_module()
        inventory = {
            "provider": "chatgpt",
            "login_state": "signed-in-or-ready",
            "visible_status": {"account": "work@example.test", "plan": "Pro", "model": "GPT-5.5"},
            "available_models": ["GPT-5.5"],
            "available_tools": ["Deep research"],
            "available_modes": {"chat": True, "deep-research": False},
        }

        blocked = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="deep-research",
            requested_model="GPT-5.5",
            screenshot_path="/tmp/screenshot.png",
            allow_paid_quota_use=False,
        )
        allowed = module.provider_typing_guard(
            {**inventory, "available_modes": {"deep-research": True}},
            provider="chatgpt",
            mode="deep-research",
            requested_model="GPT-5.5",
            screenshot_path="/tmp/screenshot.png",
            allow_paid_quota_use=True,
        )

        self.assertFalse(blocked["allowed"])
        self.assertIn("feature-not-verified", blocked["errors"])
        self.assertIn("paid-quota-use-not-allowed", blocked["errors"])
        self.assertTrue(allowed["allowed"])

    def test_typing_guard_accepts_model_hint_but_blocks_missing_model_evidence(self):
        module = load_module()
        base_inventory = {
            "provider": "chatgpt",
            "login_state": "signed-in-or-ready",
            "visible_status": {"account": "work@example.test", "plan": "Pro", "model": ""},
            "available_models": [],
            "available_tools": ["Agent"],
            "available_modes": {"agent": True},
        }

        blocked = module.provider_typing_guard(
            base_inventory,
            provider="chatgpt",
            mode="agent",
            screenshot_path="/tmp/screenshot.png",
            allow_paid_quota_use=True,
        )
        allowed = module.provider_typing_guard(
            {**base_inventory, "matched_hints": {"model_hints": ["Auto"]}},
            provider="chatgpt",
            mode="agent",
            screenshot_path="/tmp/screenshot.png",
            allow_paid_quota_use=True,
        )

        self.assertFalse(blocked["allowed"])
        self.assertIn("model-not-verified", blocked["errors"])
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["model"], "Auto")

    def test_diagnostic_clone_workflow_blocks_prompt_fill_when_pre_submit_guard_fails(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_clone = module.clone_browser_profile_for_agent_browser
        original_start = module.start_clone_cdp_browser
        original_port = module.find_available_port
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_key = module.run_cdp_keypress
        original_capture = module.capture_cdp_screenshot
        original_guard = module.provider_typing_guard
        original_fill = module.fill_agent_browser_composer
        original_preflight = module.build_real_session_preflight
        fill_calls = []

        class FakeProcess:
            def __init__(self):
                self.terminated = False

            def poll(self):
                return None if not self.terminated else 0

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.terminated = True

        visible = "ChatGPT\nwork@example.test\nPro\nGPT-5.5\nMessage ChatGPT"
        module.clone_browser_profile_for_agent_browser = lambda *args, **kwargs: {
            "ok": True,
            "clone_user_data": str(root / "clone-user-data"),
        }
        module.start_clone_cdp_browser = lambda *args, **kwargs: (FakeProcess(), {"ok": True, "pid": 1234})
        module.find_available_port = lambda: 9444
        module.run_cdp_navigate = lambda port, url, timeout=20.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_keypress = lambda port, key, timeout=10.0: module.subprocess.CompletedProcess(["key"], 0, "ok", "")
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/clone", "")
            return module.subprocess.CompletedProcess(["js"], 0, visible, "")

        def fake_guard(*args, **kwargs):
            return {
                "allowed": False,
                "errors": ["feature-not-verified"],
                "provider": "chatgpt",
                "mode": "chat",
                "account": "work@example.test",
                "plan": "Pro",
                "model": "GPT-5.5",
                "paid_mode": False,
            }

        def fail_fill(*args, **kwargs):
            fill_calls.append(kwargs.get("label", ""))
            raise AssertionError("prompt fill must not run when the pre-submit guard blocks")

        module.run_cdp_javascript = fake_js
        module.provider_typing_guard = fake_guard
        module.fill_agent_browser_composer = fail_fill
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": False, "session_evidence": {}, "blockers": ["diagnostic-clone"]}
        try:
            payload = module.agent_browser_profile_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser", "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
                profile={"directory": "Default", "name": "Work", "path": str(root / "Default")},
                provider="chatgpt",
                mode="chat",
                prompt="Do not type this",
                artifact_root=root / "artifacts",
                clone_root=root / "clones",
            )
        finally:
            module.clone_browser_profile_for_agent_browser = original_clone
            module.start_clone_cdp_browser = original_start
            module.find_available_port = original_port
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.run_cdp_keypress = original_key
            module.capture_cdp_screenshot = original_capture
            module.provider_typing_guard = original_guard
            module.fill_agent_browser_composer = original_fill
            module.build_real_session_preflight = original_preflight

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(fill_calls)
        self.assertFalse(payload["pre_submit_guard"]["allowed"])
        self.assertTrue(
            any(
                event.get("event") == "fill-prompt" and event.get("skipped") == "pre-submit-guard-blocked"
                for event in payload["workflow_events"]
            )
        )

    def test_live_workflow_blocks_slash_fallback_before_pre_submit_guard(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_keypress = module.run_cdp_keypress
        original_capture = module.capture_cdp_screenshot
        original_sleep = module.time.sleep
        original_create_target = module.run_cdp_create_automation_target
        original_fill = module.fill_agent_browser_composer
        original_click_text = module.click_first_agent_browser_text
        fill_calls = []

        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(
            ["target"],
            0,
            '{"targetId":"automation-target-1"}',
            "",
        )
        module.run_cdp_navigate = lambda port, url, timeout=20.0, target_id="": module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_keypress = lambda port, key, timeout=10.0, target_id="": module.subprocess.CompletedProcess(["key"], 0, "", "")
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0, target_id="": (screenshot.write_bytes(b"png") or True)
        module.time.sleep = lambda seconds: None

        def fake_run(args, *, session="", timeout=45.0):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0, target_id="", all_contexts=False):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/live", "")
            return module.subprocess.CompletedProcess(
                ["js"],
                0,
                "ChatGPT\nSigned in as work@example.test\nPlus plan\nModel: GPT-5.5 Pro\nMessage ChatGPT",
                "",
            )

        def fail_fill(*args, **kwargs):
            fill_calls.append(kwargs.get("label", ""))
            raise AssertionError("slash and prompt fills must wait for a passing pre-submit guard")

        module.run_agent_browser = fake_run
        module.run_cdp_javascript = fake_js
        module.fill_agent_browser_composer = fail_fill
        module.click_first_agent_browser_text = lambda *args, **kwargs: {"clicked": False, "label": "", "attempts": []}
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Automation"},
                provider="chatgpt",
                mode="deep-research",
                prompt="Do not type this",
                artifact_root=root / "artifacts",
                cdp_port=9336,
                submit=False,
                allow_paid_quota_use=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.run_cdp_keypress = original_keypress
            module.capture_cdp_screenshot = original_capture
            module.time.sleep = original_sleep
            module.run_cdp_create_automation_target = original_create_target
            module.fill_agent_browser_composer = original_fill
            module.click_first_agent_browser_text = original_click_text

        self.assertEqual(payload["status"], "model-safety-blocked")
        self.assertFalse(fill_calls)
        self.assertIn("chatgpt-pro-model-blocked", payload["pre_submit_guard"]["errors"])
        self.assertTrue(
            any(
                event.get("event") == "slash-feature" and event.get("skipped") == "pre-submit-guard-blocked"
                for event in payload["workflow_events"]
            )
        )

    def test_pacing_budget_blocks_excess_paid_runs(self):
        module = load_module()
        state = {"version": 1, "entries": {}, "history": []}
        first = module.check_and_record_pacing_budget(
            state,
            provider="chatgpt",
            account="work@example.test",
            mode="deep-research",
            max_daily_paid_runs=1,
            min_action_delay_ms=0,
            now=1000,
            record=True,
        )
        second = module.check_and_record_pacing_budget(
            state,
            provider="chatgpt",
            account="work@example.test",
            mode="deep-research",
            max_daily_paid_runs=1,
            min_action_delay_ms=0,
            now=1010,
            record=True,
        )

        self.assertTrue(first["allowed"])
        self.assertFalse(second["allowed"])
        self.assertIn("daily-paid-run-budget-exceeded", second["errors"])

    def test_pacing_budget_blocks_too_fast_repeat_actions(self):
        module = load_module()
        state = {"version": 1, "entries": {}, "history": []}
        first = module.check_and_record_pacing_budget(
            state,
            provider="gemini",
            account="work@example.test",
            mode="deep-research",
            max_daily_paid_runs=0,
            min_action_delay_ms=5000,
            now=1000,
            record=True,
        )
        second = module.check_and_record_pacing_budget(
            state,
            provider="gemini",
            account="work@example.test",
            mode="deep-research",
            max_daily_paid_runs=0,
            min_action_delay_ms=5000,
            now=1002,
            record=True,
        )

        self.assertTrue(first["allowed"])
        self.assertFalse(second["allowed"])
        self.assertIn("minimum-action-spacing-active", second["errors"])
        self.assertGreaterEqual(second["remaining_delay_seconds"], 3)

    def test_rate_limit_key_can_include_account_identity(self):
        module = load_module()

        without_account = module.rate_limit_key(browser="brave", profile="Default", provider="chatgpt", mode="chat")
        with_account = module.rate_limit_key(browser="brave", profile="Default", provider="chatgpt", mode="chat", account="work@example.test")

        self.assertNotEqual(without_account, with_account)
        self.assertIn("work-example-test", with_account)

    def test_provider_typing_guard_blocks_captcha_marker_before_fill(self):
        module = load_module()
        inventory = {
            "login_state": "signed-in-or-ready",
            "visible_status": {"account": "work@example.test", "plan": "Pro", "model": "GPT-5"},
            "available_modes": {"chat": True},
            "matched_markers": ["captcha challenge"],
        }

        guard = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="chat",
            screenshot_path="/tmp/pre-submit.png",
        )

        self.assertFalse(guard["allowed"])
        self.assertIn("captcha-or-challenge-wall", guard["errors"])

    def test_inventory_url_guard_marks_login_page_signed_out(self):
        module = load_module()

        inventory = module.extract_provider_inventory_with_url_guard(
            "claude",
            "Claude\nWhat can I help you with today?",
            "https://claude.ai/login?from=logout&returnTo=%2Fnew",
        )

        self.assertEqual(inventory["login_state"], "signed-out-or-wall")

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
            output_path = Path(tempfile.mkdtemp()) / "launch.json"
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
                        "--output",
                        str(output_path),
                    ]
                )
        finally:
            module.discover_browsers = original_discover

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["execution"]["started"])
        self.assertEqual(payload["plan"]["strategy"], "macos-open-hidden")
        self.assertEqual(payload["plan"]["provider"], "gemini")
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["plan"]["provider"], "gemini")

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

    def test_extract_provider_inventory_session_expired_overrides_visible_account(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nIsagi yoichi\nPro\nYour session has expired\nPlease log in again to continue using the app.\nLog in",
        )

        self.assertEqual(inventory["login_state"], "signed-out-or-wall")

    def test_extract_provider_inventory_records_active_chatgpt_model_and_mode(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nPlus plan\nModel: GPT-5.5 Thinking\nDeep research\nAgent\n",
        )

        self.assertEqual(inventory["active_model"], "GPT-5.5 Thinking")
        self.assertEqual(inventory["active_mode"], "thinking")
        self.assertEqual(inventory["visible_status"]["model"], "GPT-5.5 Thinking")

    def test_extract_provider_inventory_does_not_treat_chatgpt_plus_as_model(self):
        module = load_module()

        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nChat GPT Plus\nPro plan\nDeep research\nAgent\n",
        )

        self.assertEqual(inventory["active_model"], "")
        self.assertEqual(inventory["visible_status"]["model"], "")

    def test_chatgpt_model_safety_blocks_visible_extended_pro_model(self):
        module = load_module()
        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nPlus plan\nExtended Pro\nMessage ChatGPT\n",
        )

        guard = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="chat",
            requested_model=inventory["active_model"],
            screenshot_path="/tmp/chatgpt.png",
            allow_paid_quota_use=True,
        )

        self.assertEqual(inventory["active_model"], "Extended Pro")
        self.assertFalse(guard["allowed"])
        self.assertIn("chatgpt-pro-model-blocked", guard["errors"])

    def test_chatgpt_model_safety_blocks_visible_pro_model_label_in_model_context(self):
        module = load_module()
        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nPlus plan\nSelected model\nPro\nMessage ChatGPT\n",
        )

        guard = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="chat",
            requested_model=inventory["active_model"],
            screenshot_path="/tmp/chatgpt.png",
            allow_paid_quota_use=True,
        )

        self.assertEqual(inventory["active_model"], "Pro")
        self.assertFalse(guard["allowed"])
        self.assertIn("chatgpt-pro-model-blocked", guard["errors"])

    def test_chatgpt_model_safety_does_not_treat_plan_labels_as_active_model(self):
        module = load_module()
        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nChatGPT Plus\nChatGPT Pro plan\nMessage ChatGPT\n",
        )

        guard = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="chat",
            requested_model="",
            screenshot_path="/tmp/chatgpt.png",
            allow_paid_quota_use=True,
        )

        self.assertEqual(inventory["active_model"], "")
        self.assertNotIn("chatgpt-pro-model-blocked", guard["errors"])

    def test_chatgpt_model_safety_blocks_pro_model_before_typing(self):
        module = load_module()
        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nPro plan\nModel: GPT-5.5 Pro\nDeep research\nAgent\n",
        )

        guard = module.provider_typing_guard(
            inventory,
            provider="chatgpt",
            mode="deep-research",
            requested_model="GPT-5.5 Pro",
            screenshot_path="/tmp/chatgpt.png",
            allow_paid_quota_use=True,
        )

        self.assertFalse(guard["allowed"])
        self.assertIn("chatgpt-pro-model-blocked", guard["errors"])
        self.assertEqual(guard["model_safety"]["status"], "blocked")

    def test_chatgpt_model_safety_allows_thinking_agent_and_deep_research(self):
        module = load_module()
        inventory = module.extract_provider_inventory(
            "chatgpt",
            "ChatGPT\nSigned in as work@example.test\nPlus plan\nModel: GPT-5.5 Thinking\nDeep research\nAgent\n",
        )

        for mode in ["thinking", "agent", "deep-research"]:
            guard = module.provider_typing_guard(
                inventory,
                provider="chatgpt",
                mode=mode,
                requested_model="GPT-5.5 Thinking",
                screenshot_path="/tmp/chatgpt.png",
                allow_paid_quota_use=True,
            )
            self.assertNotIn("chatgpt-pro-model-blocked", guard["errors"])
            self.assertEqual(guard["model_safety"]["status"], "allowed")

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
            research_depth="deep",
            model="gpt-5.5-instant",
            browser_attachment_timeout=240,
        )

        self.assertEqual(plan["package"], "@steipete/oracle@0.13.0")
        self.assertIn("--browser-attach-running", plan["consult_dry_run"])
        self.assertIn("--remote-chrome", plan["consult_dry_run"])
        self.assertIn("127.0.0.1:9224", plan["consult_dry_run"])
        self.assertIn("--browser-research", plan["consult_dry_run"])
        self.assertIn("gpt-5.5-instant", plan["consult_dry_run"])
        self.assertIn("--browser-attachment-timeout", plan["consult_dry_run"])
        self.assertIn("240", plan["consult_dry_run"])
        self.assertEqual(plan["status"][:3], ["npx", "-y", "@steipete/oracle@0.13.0"])
        self.assertIn("reattach", plan)
        self.assertIn("--render", plan["show_session"])

    def test_cmd_oracle_plan_outputs_json_commands(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(
                [
                    "oracle-plan",
                    "-p",
                    "Check implementation",
                    "--remote-chrome",
                    "127.0.0.1:9224",
                    "--research-depth",
                    "max",
                    "--model",
                    "gpt-5.5-instant",
                ]
            )

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("--browser-attach-running", payload["consult_dry_run"])
        self.assertIn("max", payload["consult_dry_run"])
        self.assertIn("gpt-5.5-instant", payload["consult_dry_run"])

    def test_build_oracle_plan_uses_provider_mode_safe_defaults(self):
        module = load_module()

        thinking = module.build_oracle_plan(prompt="Debug", provider="chatgpt", mode="thinking", cdp_port=9223)
        agent = module.build_oracle_plan(prompt="Debug", provider="chatgpt", mode="agent", cdp_port=9223)
        gemini = module.build_oracle_plan(prompt="Debug", provider="gemini", mode="deep-research", cdp_port=9223)

        self.assertIn("GPT-5.5 Thinking", thinking["consult_dry_run"])
        self.assertNotIn("gpt-5.5 pro", " ".join(thinking["consult_dry_run"]).lower())
        self.assertIn("--browser-research", agent["consult_dry_run"])
        self.assertIn("deep", agent["consult_dry_run"])
        self.assertEqual(gemini["execution_policy"], "assist-only")

    def test_provider_workflow_spec_maps_chatgpt_thinking_to_chat_flow(self):
        module = load_module()

        spec = module.provider_workflow_spec("chatgpt", "thinking")

        self.assertEqual(spec["provider"], "chatgpt")
        self.assertEqual(spec["mode"], "chat")
        self.assertEqual(spec["url"], "https://chatgpt.com/")

    def test_oracle_assist_payload_redacts_prompt_and_exposes_commands(self):
        module = load_module()
        plan = module.build_oracle_assist_payload(
            prompt="secret prompt https://chatgpt.com/c/private",
            provider="chatgpt",
            mode="agent",
            cdp_port=9223,
            artifact_privacy="redacted",
        )
        serialized = json.dumps(plan)

        self.assertEqual(plan["mode"], "assist")
        self.assertTrue(plan["reattach_available"])
        self.assertIn("commands", plan)
        self.assertNotIn("secret prompt", serialized)
        self.assertNotIn("chatgpt.com/c/private", serialized)

    def test_cmd_oracle_e2e_smoke_requires_opt_in(self):
        module = load_module()

        out = StringIO()
        with mock.patch.dict("os.environ", {}, clear=True), redirect_stdout(out):
            exit_code = module.main(["oracle-e2e-smoke", "--browser", "brave", "--profile", "work", "--provider", "chatgpt", "--mode", "thinking"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("AI_RESEARCH_BROWSER_E2E=1", payload["blocker"])
        self.assertFalse(payload["safety"]["pro_model_allowed"])

    def test_cloakbrowser_plan_redacts_proxy_file(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        proxy_file = root / "proxies.txt"
        proxy_file.write_text("203.0.113.10:5432:secret-user:secret-pass\n", encoding="utf-8")
        proxy_file.chmod(0o600)

        plan = module.build_cloakbrowser_preflight_plan(
            manager_url="http://127.0.0.1:18080",
            proxy_file=str(proxy_file),
        )

        serialized = json.dumps(plan)
        self.assertTrue(plan["proxy_file"]["ok"])
        self.assertEqual(plan["proxy_file"]["count"], 1)
        self.assertNotIn("203.0.113.10", serialized)
        self.assertNotIn("secret-user", serialized)
        self.assertNotIn("secret-pass", serialized)
        self.assertIn("<redacted-proxy>", serialized)

    def test_cloakbrowser_proxy_file_requires_private_permissions(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        proxy_file = root / "proxies.txt"
        proxy_file.write_text("203.0.113.10:5432:secret-user:secret-pass\n", encoding="utf-8")
        proxy_file.chmod(0o644)

        result = module.inspect_cloakbrowser_proxy_file(str(proxy_file))

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "insecure-permissions")
        self.assertNotIn("secret-user", json.dumps(result))

    def test_cmd_cloakbrowser_manager_plan_outputs_docker_health_commands(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["cloakbrowser-manager-plan", "--port", "18080"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["backend"], "cloakbrowser")
        self.assertIn("cloakhq/cloakbrowser-manager", payload["commands"]["docker_run"])
        self.assertEqual(payload["health_url"], "http://127.0.0.1:18080/api/status")

    def test_cmd_cloakbrowser_profile_plan_blocks_without_verified_baseline(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(["cloakbrowser-profile-plan", "--profile-name", "chatgpt-work", "--provider", "chatgpt"])

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("verified account baseline", payload["blocker"])

    def test_workflow_run_cloakbrowser_blocks_without_account_baseline(self):
        module = load_module()

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(
                [
                    "workflow-run",
                    "--backend",
                    "cloakbrowser",
                    "--provider",
                    "chatgpt",
                    "--prompt",
                    "smoke",
                ]
            )

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("--account-baseline", payload["blocker"])

    def test_workflow_run_cloakbrowser_blocks_without_cdp_port_after_baseline(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        baseline = root / "baseline.json"
        baseline.write_text(json.dumps({"verified": True, "login_state": "signed-in-or-ready"}), encoding="utf-8")

        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main(
                [
                    "workflow-run",
                    "--backend",
                    "cloakbrowser",
                    "--account-baseline",
                    str(baseline),
                    "--provider",
                    "chatgpt",
                    "--prompt",
                    "smoke",
                ]
            )

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("--cdp-port", payload["blocker"])

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

        self.assertEqual([row["feature"] for row in suite], ["chat", "deep-research", "agent", "image"])
        self.assertEqual(suite[1]["model"], "GPT-5.5")
        self.assertNotIn("GPT-5.5 Pro", [row["model"] for row in suite])
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

    def test_agent_browser_suite_signed_out_only_is_not_success(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_probe = module.agent_browser_profile_probe
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "profiles": [{"directory": "Default", "name": "Work", "path": "/tmp/missing"}],
            }
        ]
        module.agent_browser_profile_probe = lambda **kwargs: {
            "status": "signed-out-or-wall",
            "inventory": {"login_state": "signed-out-or-wall"},
        }
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(["agent-browser-suite", "--providers", "chatgpt", "--max-runs", "1"])
        finally:
            module.discover_browsers = original_discover
            module.agent_browser_profile_probe = original_probe

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["summary"]["signed_out_or_wall"], 1)

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

        def fake_run(command, capture_output=True, text=True, timeout=20, check=False):
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

    def test_ai_exporter_capabilities_parse_hosts_actions_and_notion_state(self):
        module = load_module()
        source = Path(tempfile.mkdtemp())
        profile = source / "Default"
        extension_id = module.KNOWN_EXTENSION_IDS["ai-exporter"]["ids"][0]
        extension_dir = profile / "Extensions" / extension_id / "4.2.1_0"
        extension_dir.mkdir(parents=True)
        (extension_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "SaveAI Popup",
                    "version": "4.2.1",
                    "content_scripts": [{"matches": ["https://chatgpt.com/*", "https://gemini.google.com/*"]}],
                    "permissions": ["storage", "cookies"],
                }
            ),
            encoding="utf-8",
        )

        payload = module.build_ai_exporter_capabilities(
            [
                {
                    "id": "brave",
                    "display_name": "Brave Browser",
                    "profiles": [{"directory": "Default", "name": "Work", "path": str(profile), "account_state": "signed-in-hidden"}],
                }
            ]
        )

        row = payload["rows"][0]
        self.assertIn("chatgpt", row["supported_providers"])
        self.assertIn("gemini", row["supported_providers"])
        self.assertIn("saveFullChatsToNotion", row["actions"])
        self.assertTrue(row["notion"]["requires_notion_login"])
        self.assertEqual(row["notion"]["session_evidence"]["confidence"], "none")

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
        self.assertIn("cloakbrowser", backends)
        self.assertIn("openai-cua", backends)
        self.assertIn("unbrowser-local", backends)
        self.assertIn("hyperbrowser", backends)
        self.assertEqual(backends["playwright-cdp"]["scope"], "local")
        self.assertIn("@steipete/oracle", backends["oracle"]["aliases"])
        self.assertEqual(backends["cloakbrowser"]["scope"], "isolated-cdp-profile")
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

    def test_real_session_preflight_reports_cdp_blocker_and_session_evidence(self):
        module = load_module()
        original_endpoint = module.detect_cdp_endpoint
        original_owner = module.lsof_port_owner
        original_args = module.browser_main_process_args
        original_evidence = module.provider_session_evidence
        module.detect_cdp_endpoint = lambda port, hosts=None: {"ok": False, "base": "", "version": {}, "attempts": []}
        module.lsof_port_owner = lambda port: {"port": port, "listening": True, "command": "Code\\x20H", "pid": "123", "raw": ""}
        module.browser_main_process_args = lambda browser: ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
        module.provider_session_evidence = lambda profile, provider: {"provider": provider, "confidence": "likely-logged-in"}
        try:
            payload = module.build_real_session_preflight(
                browser={"id": "brave", "display_name": "Brave Browser", "default_port": 9223, "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="google",
            )
        finally:
            module.detect_cdp_endpoint = original_endpoint
            module.lsof_port_owner = original_owner
            module.browser_main_process_args = original_args
            module.provider_session_evidence = original_evidence

        self.assertFalse(payload["can_attach"])
        self.assertIn("cdp-port-owned-by-unexpected-process", payload["blockers"])
        self.assertFalse(payload["cdp_owner_verification"]["ok"])
        self.assertIn("browser-running-without-remote-debugging", payload["blockers"])
        self.assertEqual(payload["session_evidence"]["confidence"], "likely-logged-in")

    def test_real_session_requirement_preserves_login_wall_as_blocker(self):
        module = load_module()

        status, inventory = module.apply_real_session_requirement(
            "opened",
            {"login_state": "signed-out-or-wall"},
            {"session_evidence": {"confidence": "likely-logged-in"}},
        )

        self.assertEqual(status, "real-session-required")
        self.assertEqual(inventory["login_state"], "signed-out-or-wall")

    def test_real_session_requirement_never_upgrades_login_wall_to_verified(self):
        module = load_module()

        status, inventory = module.apply_real_session_requirement(
            "verified",
            {"login_state": "signed-out-or-wall"},
            {"session_evidence": {"confidence": "unknown"}},
        )

        self.assertEqual(status, "signed-out-or-wall")
        self.assertEqual(inventory["login_state"], "signed-out-or-wall")

    def test_notion_export_plan_requires_explicit_external_write(self):
        module = load_module()

        plan = module.build_notion_export_plan(
            requested=True,
            allow_external_write=False,
            provider="google",
            ai_exporter_capabilities={
                "rows": [
                    {
                        "browser": "brave",
                        "profile_directory": "Default",
                        "supported_providers": ["gemini"],
                        "extension": {"version": "4.2.1"},
                        "actions": ["openFullNotionExport", "saveFullChatsToNotion"],
                        "notion": {"session_evidence": {"confidence": "likely-logged-in"}},
                    }
                ]
            },
            workflow_payload={"status": "captured", "output_text_path": "/tmp/out.txt"},
            followup_payload=None,
        )

        self.assertFalse(plan["eligible"])
        self.assertIn("external-write-not-enabled", plan["blocked_reasons"])
        self.assertEqual(plan["ai_exporter_rows"][0]["notion_session_confidence"], "likely-logged-in")

    def test_unbrowser_session_management_arguments(self):
        module = load_module()

        args = module.build_unbrowser_tool_arguments(
            tool="session_management",
            session_action="health",
            session_domain="gemini.google.com",
            session_profile="martin-work",
        )

        self.assertEqual(
            args,
            {
                "action": "health",
                "domain": "gemini.google.com",
                "sessionProfile": "martin-work",
            },
        )

    def test_provider_domain_uses_provider_url(self):
        module = load_module()

        self.assertEqual(module.provider_domain("google"), "gemini.google.com")
        self.assertEqual(module.provider_domain("chatgpt"), "chatgpt.com")

    def test_compact_unbrowser_payload_keeps_status_without_schema_noise(self):
        module = load_module()

        compact = module.compact_unbrowser_payload(
            {
                "backend": "unbrowser-local",
                "status": "ok",
                "profile": "core",
                "tool": "session_management",
                "tools": ["smart_browse", "session_management"],
                "tool_schemas": [{"name": "very-large-schema"}],
                "call_response": {"result": {"content": [{"type": "text", "text": "x" * 2000}]}},
                "events_path": "/tmp/events.json",
            }
        )

        self.assertEqual(compact["status"], "ok")
        self.assertNotIn("tool_schemas", compact)
        self.assertEqual(len(compact["call_text_preview"]), 1200)

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
        self.assertIn("Recherche starten", gemini_research["confirmation_triggers"])
        self.assertTrue(gemini_research["requires_post_submit_confirmation"])
        self.assertGreaterEqual(gemini_research["pre_confirm_wait_seconds"], 90)
        self.assertIn("Research", perplexity_research["feature_triggers"])
        self.assertIn("New Chat", grok_research["pre_prompt_triggers"])
        self.assertEqual(grok_research["menu_triggers"], [])

    def test_gemini_deep_research_auto_enables_post_submit_confirmation(self):
        module = load_module()

        plan = module.build_live_ai_workflow_plan(
            browser={"id": "brave", "display_name": "Brave Browser"},
            profile={"directory": "Default", "name": "Default"},
            provider="google",
            mode="deep-research",
            prompt="Research",
            artifact_root=Path("/tmp/artifacts"),
            cdp_port=9223,
            submit=True,
            confirm_start=False,
        )

        self.assertFalse(plan["confirm_start_requested"])
        self.assertTrue(plan["confirm_start"])
        self.assertTrue(plan["confirm_start_auto_enabled"])
        self.assertIn("confirm-start", [action["label"] for action in plan["actions"]])

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
        self.assertIn("Datei hochladen", " ".join(attachment_actions[0]["menu_triggers"]))

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

    def test_click_text_js_script_avoids_composer_text_and_prioritizes_menu_items(self):
        module = load_module()

        script = module.click_text_js_script("Deep Research")

        self.assertIn('[role="textbox"]', script)
        self.assertIn("menuitemcheckbox", script)
        self.assertIn("exact.length ? exact : contains", script)

    def test_gemini_select_tool_js_script_opens_tools_and_clicks_menuitemcheckbox(self):
        module = load_module()

        script = module.gemini_select_tool_js_script("Deep Research")

        self.assertIn("uploads", script)
        self.assertIn('[role="menuitemcheckbox"]', script)
        self.assertIn("tool-item-not-found", script)
        self.assertIn("Deep Research", script)

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

    def test_find_snapshot_ref_supports_chatgpt_tool_menuitemradio(self):
        module = load_module()
        snapshot = '- menuitemradio "Deep research" [checked=false, ref=e9]'

        ref = module.find_snapshot_ref(
            snapshot,
            "Deep research",
            roles=("button", "menuitem", "menuitemradio", "menuitemcheckbox", "option", "link"),
        )

        self.assertEqual(ref, "e9")

    def test_chatgpt_deep_research_prompt_instruction_final_answer_is_not_complete(self):
        module = load_module()

        extracted = module.extract_workflow_output_from_text(
            "Use ChatGPT Deep Research for a narrow diagnostic. End the final answer with exactly this marker: "
            "BRAVE_CHATGPT_DEEP_RESEARCH_SHORT_E2E_OK\nDeep research\nApps\nSites\nInstant",
            provider="chatgpt",
            mode="deep-research",
        )

        self.assertEqual(extracted["status"], "captured")
        self.assertEqual(extracted["completion_markers_found"], [])

    def test_chatgpt_deep_research_stop_research_counts_as_running(self):
        module = load_module()

        extracted = module.extract_workflow_output_from_text(
            "Live CLI OOPIF eval debugging\nExploring alternatives for GitHub code search...\nStop research",
            provider="chatgpt",
            mode="deep-research",
        )

        self.assertEqual(extracted["status"], "running")
        self.assertIn("Stop research", extracted["running_markers_found"])

    def test_chatgpt_chat_treats_thinking_as_running(self):
        module = load_module()

        extracted = module.extract_workflow_output_from_text(
            "End-to-end clipboard extraction test\nThinking\nStop answering",
            provider="chatgpt",
            mode="chat",
        )

        self.assertEqual(extracted["status"], "running")
        self.assertIn("Stop answering", extracted["running_markers_found"])

    def test_clean_workflow_response_removes_prompt_and_chatgpt_ui_lines(self):
        module = load_module()

        cleaned = module.clean_workflow_response_text(
            "Reply only with this exact token: TOKEN_123\nThought for 5s\nTOKEN_123\nThinking\nIs this conversation helpful so far?",
            provider="chatgpt",
            prompt="Reply only with this exact token: TOKEN_123",
        )

        self.assertEqual(cleaned, "TOKEN_123")

    def test_clean_workflow_response_removes_chatgpt_composer_only_status(self):
        module = load_module()
        prompt = "E2E smoke test: answer one short sentence confirming ChatGPT chat is usable."

        cleaned = module.clean_workflow_response_text(
            f"{prompt}\nInstant\nChatGPT can make mistakes. Check important info.\n{prompt}\nInstant",
            provider="chatgpt",
            prompt=prompt,
        )

        self.assertEqual(cleaned, "")

    def test_clean_workflow_response_removes_foreign_suite_prompt_echo(self):
        module = load_module()
        prompt = "E2E smoke test: answer one short sentence confirming ChatGPT chat is usable."
        echoed_research_prompt = (
            "Use ChatGPT Deep Research to research safe browser automation practices in 2026. "
            "Create a concise report with sources. If a plan appears, start the research."
        )

        cleaned = module.clean_workflow_response_text(
            f"{echoed_research_prompt}\n{echoed_research_prompt}",
            provider="chatgpt",
            prompt=prompt,
        )

        self.assertEqual(cleaned, "")

    def test_pre_submit_login_gate_blocks_unknown_or_signed_out_inventory(self):
        module = load_module()

        self.assertTrue(module.should_block_submit_before_login_inventory({"login_state": "unknown"}, submit=True))
        self.assertTrue(module.should_block_submit_before_login_inventory({"login_state": "signed-out-or-wall"}, submit=True))
        self.assertFalse(module.should_block_submit_before_login_inventory({"login_state": "signed-in-or-ready"}, submit=True))
        self.assertFalse(module.should_block_submit_before_login_inventory({"login_state": "unknown"}, submit=False))
        self.assertTrue(module.should_block_typing_before_login_inventory({"login_state": "unknown"}))
        self.assertFalse(module.should_block_typing_before_login_inventory({"login_state": "signed-in-or-ready"}))

        event = module.pre_submit_login_gate_event({"login_state": "unknown", "visible_status": {"plan": "Plus"}})
        self.assertEqual(event["event"], "pre-typing-login-gate")
        self.assertEqual(event["visible_status"]["plan"], "Plus")

    def test_wait_for_response_does_not_verify_cleaned_empty_chatgpt_output(self):
        module = load_module()
        prompt = "E2E smoke test: answer one short sentence confirming ChatGPT chat is usable."
        composer_text = f"{prompt}\nInstant\nChatGPT can make mistakes. Check important info.\n{prompt}\nInstant"

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, composer_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="chat",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "timeout")
        self.assertTrue(all(poll.get("ignored_composer_output") for poll in event["polls"]))

    def test_wait_for_response_ignores_stable_composer_with_attachment_names(self):
        module = load_module()
        prompt = "E2E smoke test: answer one short sentence confirming ChatGPT chat is usable."
        composer_text = "\n".join(
            [
                "How can I help, Isagi?",
                prompt,
                "Extended Pro",
                "e2e-note.txt",
                "Document",
                "e2e-video.mp4",
                "File",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, composer_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="chat",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
            attachment_names=["e2e-note.txt", "e2e-video.mp4"],
        )

        self.assertEqual(event["status"], "timeout")
        self.assertTrue(all(poll.get("ignored_composer_output") for poll in event["polls"]))

    def test_wait_for_response_completes_on_requested_e2e_marker(self):
        module = load_module()
        prompt = "Research briefly and end exactly with CHATGPT_DEEP_RESEARCH_E2E_OK"
        response_text = "Short researched answer without generic Done marker.\nCHATGPT_DEEP_RESEARCH_E2E_OK"

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, response_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=5,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "complete")
        self.assertEqual(event["output"]["requested_markers_found"], ["CHATGPT_DEEP_RESEARCH_E2E_OK"])

    def test_wait_for_response_marker_overrides_chatgpt_composer_chrome(self):
        module = load_module()
        prompt = "Reply exactly with CHATGPT_CHAT_WAITERFIX_E2E_OK"
        response_text = "\n".join(
            [
                "How can I help, Isagi?",
                prompt,
                "Document",
                "Instant",
                "CHATGPT_CHAT_WAITERFIX_E2E_OK",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, response_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="chat",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=5,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "complete")
        self.assertFalse(event["polls"][0].get("ignored_composer_output", False))

    def test_wait_for_response_prefers_focused_chatgpt_output_over_page_chrome(self):
        module = load_module()
        prompt = "Reply with exactly this marker and one short sentence: BRAVE_CHATGPT_COOLDOWN_E2E_125248"
        snapshot_text = "\n".join(
            [
                "How can I help, Isagi?",
                prompt,
                "Extended Pro",
                "Document",
            ]
        )
        response_text = "BRAVE_CHATGPT_COOLDOWN_E2E_125248 System cooldown check completed successfully."

        def fake_invoke(label, args):
            if label.startswith("extract-response"):
                return module.subprocess.CompletedProcess(["agent-browser", *args], 0, response_text, "")
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, snapshot_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="chat",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=5,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "stable")
        self.assertEqual(event["output"]["text"], response_text)
        self.assertFalse(event["polls"][-1].get("ignored_composer_output", False))

    def test_wait_for_response_deep_research_does_not_verify_stable_plan(self):
        module = load_module()
        prompt = "Research and end with GEMINI_DEEP_RESEARCH_STRICT_E2E_OK"
        plan_text = "\n".join(
            [
                prompt,
                "Gemini hat gesagt",
                "Der Plan hat 3 Schritte, 1. Schritt",
                "Recherche starten",
                "Antwort stoppen",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, plan_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="gemini",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "timeout")

    def test_wait_for_response_does_not_complete_on_marker_only_in_prompt(self):
        module = load_module()
        prompt = "Reply exactly with CHATGPT_DEEP_RESEARCH_E2E_OK"

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, prompt, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "timeout")

    def test_wait_for_response_requires_requested_marker_even_with_provider_completion(self):
        module = load_module()
        prompt = "Research and end with GEMINI_DEEP_RESEARCH_STRICT_E2E_OK"
        response_text = "Ich bin mit deiner Recherche fertig.\nA useful report without the requested marker."

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, response_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="gemini",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "timeout")

    def test_wait_for_response_does_not_complete_on_marker_inside_running_research_plan(self):
        module = load_module()
        prompt = "Research and end with COMET_GEMINI_DEEP_E2E_OK"
        running_plan_text = "\n".join(
            [
                "Here's the plan I've put together.",
                "(5) Ensure the final compiled research ends exactly with the requested marker COMET_GEMINI_DEEP_E2E_OK.",
                "Start research",
                "Researching websites...",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, running_plan_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="gemini",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "running-timeout")
        self.assertEqual(event["reason"], "provider-still-running")
        self.assertTrue(all("requested_markers_found" not in poll for poll in event["polls"]))

    def test_chatgpt_deep_research_does_not_complete_on_multiline_prompt_marker_echo_while_running(self):
        module = load_module()
        prompt = "Use ChatGPT Deep Research for the current OOPIF bug.\nBRAVE_CHATGPT_DEEP_RESEARCH_E2E_OK"
        running_echo_text = "\n".join(
            [
                prompt,
                "Live CLI OOPIF eval debugging",
                "Searching for all_contexts handling...",
                "Stop research",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, running_echo_text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="deep-research",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=0.25,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "running-timeout")
        self.assertTrue(all(poll.get("status") != "complete" for poll in event["polls"]))

    def test_wait_for_response_stops_on_session_expired_wall(self):
        module = load_module()
        text = "\n".join(
            [
                "Isagi yoichi",
                "Pro",
                "Your session has expired",
                "Please log in again to continue using the app.",
                "Log in",
                "Stop answering",
            ]
        )

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, text, "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="chatgpt",
            mode="agent",
            output_selectors=[],
            visible_text_parts=[],
            response_timeout=30,
            poll_interval=0.05,
            prompt="Agent diagnostic",
        )

        self.assertEqual(event["status"], "signed-out-or-wall")
        self.assertEqual(event["reason"], "login-wall-during-response")
        self.assertEqual(event["login_wall"]["kind"], "login-wall")

    def test_wait_for_response_prefers_completed_focused_report_over_stale_page_running_text(self):
        module = load_module()
        prompt = "Research and end with COMET_GEMINI_DEEP_E2E_OK"
        snapshot_text = "Researching websites...\nOld progress card"
        report_text = "Final report\n\nCOMET_GEMINI_DEEP_E2E_OK"

        def fake_invoke(label, args):
            if label.startswith("snapshot-response"):
                return module.subprocess.CompletedProcess(["agent-browser", *args], 0, snapshot_text, "")
            if label.startswith("extract-response"):
                return module.subprocess.CompletedProcess(["agent-browser", *args], 0, report_text, "")
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, "", "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="gemini",
            mode="deep-research",
            output_selectors=["#extended-response-markdown-content"],
            visible_text_parts=[],
            response_timeout=5,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "complete")
        self.assertEqual(event["polls"][0]["source"], "focused-output")
        self.assertEqual(event["output"]["requested_markers_found"], ["COMET_GEMINI_DEEP_E2E_OK"])

    def test_wait_for_response_marker_wins_over_stale_gemini_thoughts(self):
        module = load_module()
        prompt = "Research and end with BRAVE_GEMINI_DEEP_E2E_OK"
        report_text = "\n".join(
            [
                "Browser Automation CAPTCHA Pause Strategies",
                "Safe pausing strategies for CAPTCHA and rate-limit screens.",
                "BRAVE_GEMINI_DEEP_E2E_OK",
                "Gedanken",
                "Researching websites...",
            ]
        )

        def fake_invoke(label, args):
            if label.startswith("extract-response"):
                return module.subprocess.CompletedProcess(["agent-browser", *args], 0, report_text, "")
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, "Old progress card", "")

        event = module.wait_for_workflow_response(
            invoke=fake_invoke,
            provider="gemini",
            mode="deep-research",
            output_selectors=["#extended-response-markdown-content"],
            visible_text_parts=[],
            response_timeout=5,
            poll_interval=0.05,
            prompt=prompt,
        )

        self.assertEqual(event["status"], "complete")
        self.assertEqual(event["output"]["requested_markers_found"], ["BRAVE_GEMINI_DEEP_E2E_OK"])

    def test_wait_for_paid_response_stops_on_no_progress(self):
        module = load_module()
        prompt = "Agent diagnostic and end with CHATGPT_AGENT_NO_PROGRESS_E2E_OK"
        static_text = "User prompt submitted, but no assistant response yet."
        ticks = {"value": 0.0}
        original_monotonic = module.time.monotonic
        original_sleep = module.time.sleep

        def fake_monotonic():
            ticks["value"] += 6.0
            return ticks["value"]

        def fake_sleep(_seconds):
            return None

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, static_text, "")

        module.time.monotonic = fake_monotonic
        module.time.sleep = fake_sleep
        try:
            event = module.wait_for_workflow_response(
                invoke=fake_invoke,
                provider="chatgpt",
                mode="agent",
                output_selectors=[],
                visible_text_parts=[],
                response_timeout=180,
                poll_interval=2,
                prompt=prompt,
            )
        finally:
            module.time.monotonic = original_monotonic
            module.time.sleep = original_sleep

        self.assertEqual(event["status"], "no-progress")

    def test_chatgpt_deep_research_top_level_echo_waits_for_timeout(self):
        module = load_module()
        prompt = "Use ChatGPT Deep Research for iframe diagnostics."
        static_text = f"{prompt}\nDeep research\nApps\nSites\nInstant"
        ticks = {"value": 0.0}
        original_monotonic = module.time.monotonic
        original_sleep = module.time.sleep

        def fake_monotonic():
            ticks["value"] += 6.0
            return ticks["value"]

        def fake_sleep(_seconds):
            return None

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, static_text, "")

        module.time.monotonic = fake_monotonic
        module.time.sleep = fake_sleep
        try:
            event = module.wait_for_workflow_response(
                invoke=fake_invoke,
                provider="chatgpt",
                mode="deep-research",
                output_selectors=[],
                visible_text_parts=[],
                response_timeout=60,
                poll_interval=2,
                prompt=prompt,
            )
        finally:
            module.time.monotonic = original_monotonic
            module.time.sleep = original_sleep

        self.assertEqual(event["status"], "timeout")

    def test_chatgpt_deep_research_running_timeout_is_explicit(self):
        module = load_module()
        prompt = "Use ChatGPT Deep Research for iframe diagnostics."
        running_text = "Live CLI OOPIF eval debugging\nSearching for menuitemradio info in ARIA/MDN...\nStop research"
        ticks = {"value": 0.0}
        original_monotonic = module.time.monotonic
        original_sleep = module.time.sleep

        def fake_monotonic():
            ticks["value"] += 30.0
            return ticks["value"]

        def fake_sleep(_seconds):
            return None

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(["agent-browser", *args], 0, running_text, "")

        module.time.monotonic = fake_monotonic
        module.time.sleep = fake_sleep
        try:
            event = module.wait_for_workflow_response(
                invoke=fake_invoke,
                provider="chatgpt",
                mode="deep-research",
                output_selectors=[],
                visible_text_parts=[],
                response_timeout=60,
                poll_interval=2,
                prompt=prompt,
            )
        finally:
            module.time.monotonic = original_monotonic
            module.time.sleep = original_sleep

        self.assertEqual(event["status"], "running-timeout")
        self.assertEqual(event["reason"], "provider-still-running")

    def test_wait_for_paid_running_response_stops_when_progress_stalls(self):
        module = load_module()
        ticks = {"value": 0.0}
        progress_events = []
        original_monotonic = module.time.monotonic
        original_sleep = module.time.sleep

        def fake_monotonic():
            ticks["value"] += 30.0
            return ticks["value"]

        def fake_sleep(_seconds):
            return None

        def fake_invoke(label, args):
            return module.subprocess.CompletedProcess(
                ["agent-browser", *args],
                0,
                "Agent\nWorking\nExploring event listener evidence...",
                "",
            )

        module.time.monotonic = fake_monotonic
        module.time.sleep = fake_sleep
        try:
            event = module.wait_for_workflow_response(
                invoke=fake_invoke,
                provider="chatgpt",
                mode="agent",
                output_selectors=[],
                visible_text_parts=[],
                response_timeout=900,
                poll_interval=2,
                prompt="Agent diagnostic without a completion marker.",
                progress_callback=progress_events.append,
            )
        finally:
            module.time.monotonic = original_monotonic
            module.time.sleep = original_sleep

        self.assertEqual(event["status"], "no-progress")
        self.assertEqual(event["reason"], "paid-workflow-progress-stalled")
        self.assertGreaterEqual(len(progress_events), 10)
        self.assertEqual(progress_events[-1]["status"], "polling")

    def test_latest_response_script_keeps_useful_tail_for_long_reports(self):
        module = load_module()
        script = module.browser_eval_latest_response_script("gemini", [])

        self.assertIn("slice(-60000)", script)
        self.assertIn("#extended-response-markdown-content", script)

    def test_composer_fill_script_uses_prosemirror_insert_text_path(self):
        module = load_module()
        script = module.composer_js_fill_script("hello")

        self.assertIn("document.execCommand('insertText'", script)
        self.assertIn("beforeinput", script)

    def test_parse_json_stdout_accepts_nested_json_string(self):
        module = load_module()

        self.assertEqual(module.parse_json_stdout('"{\\"ok\\": true, \\"method\\": \\"js\\"}"'), {"ok": True, "method": "js"})

    def test_gemini_confirm_script_targets_confirm_button(self):
        module = load_module()
        script = module.gemini_confirm_deep_research_js_script()

        self.assertIn('data-test-id="confirm-button"', script)
        self.assertIn("Recherche starten", script)
        self.assertIn("Start Deep Research", script)
        self.assertIn("Create report", script)

    def test_requested_completion_marker_detection_uses_cleaned_response(self):
        module = load_module()
        prompt = "Reply exactly with CHATGPT_DEEP_RESEARCH_E2E_OK"

        self.assertEqual(
            module.requested_completion_markers_in_response(prompt, provider="chatgpt", prompt=prompt),
            [],
        )
        self.assertEqual(
            module.requested_completion_markers_in_response(
                f"{prompt}\nA real answer.\nCHATGPT_DEEP_RESEARCH_E2E_OK",
                provider="chatgpt",
                prompt=prompt,
            ),
            ["CHATGPT_DEEP_RESEARCH_E2E_OK"],
        )
        self.assertEqual(
            module.requested_completion_markers_in_response(
                f"{prompt}\nReliability check completed successfully CHATGPT_DEEP_RESEARCH_E2E_OK",
                provider="chatgpt",
                prompt=prompt,
            ),
            ["CHATGPT_DEEP_RESEARCH_E2E_OK"],
        )
        self.assertEqual(
            module.requested_completion_markers_in_response(
                f"{prompt}\n(5) End with the marker 'CHATGPT_DEEP_RESEARCH_E2E_OK'.",
                provider="chatgpt",
                prompt=prompt,
            ),
            [],
        )

    def test_submit_prompt_waits_for_attachments_and_clicks_enabled_send_button(self):
        module = load_module()
        calls = []
        states = iter(
            [
                {"ok": True, "sendReady": False, "sendDisabled": True, "composerHasPrompt": True, "attachmentNamesFound": ["e2e-note.txt"]},
                {"ok": True, "sendReady": True, "sendDisabled": False, "composerHasPrompt": True, "attachmentNamesFound": ["e2e-note.txt"]},
                {"ok": True, "sendReady": False, "sendDisabled": True, "composerHasPrompt": False, "attachmentNamesFound": []},
            ]
        )

        def fake_invoke(label, args):
            calls.append((label, args))
            if args[:1] == ["eval"] and "__AI_RESEARCH_COMPOSER_STATE__" in args[1]:
                return module.subprocess.CompletedProcess(["eval"], 0, json.dumps(next(states)), "")
            if args[:1] == ["eval"] and "__AI_RESEARCH_SUBMIT_PROMPT__" in args[1]:
                return module.subprocess.CompletedProcess(["eval"], 0, json.dumps({"ok": True, "method": "button-click"}), "")
            if args[:1] == ["wait"]:
                return module.subprocess.CompletedProcess(["wait"], 0, "", "")
            return module.subprocess.CompletedProcess(["cmd"], 0, "", "")

        event = module.submit_agent_browser_prompt(
            invoke=fake_invoke,
            provider="chatgpt",
            prompt="hello",
            attachment_names=["e2e-note.txt"],
            max_wait_seconds=3,
        )

        self.assertTrue(event["submitted"])
        self.assertEqual(event["method"], "button-click")
        self.assertGreaterEqual(len(event["readiness_polls"]), 2)
        self.assertTrue(any(label == "submit-prompt-js-click" for label, _ in calls))

    def test_submit_prompt_without_attachments_does_not_wait_for_readiness(self):
        module = load_module()
        calls = []

        def fake_invoke(label, args):
            calls.append((label, args))
            if args[:1] == ["eval"] and "__AI_RESEARCH_COMPOSER_STATE__" in args[1]:
                return module.subprocess.CompletedProcess(["eval"], 0, "", "")
            if args[:1] == ["eval"] and "__AI_RESEARCH_SUBMIT_PROMPT__" in args[1]:
                return module.subprocess.CompletedProcess(["eval"], 0, json.dumps({"ok": False}), "")
            if args[:1] == ["press"]:
                return module.subprocess.CompletedProcess(["press"], 0, "", "")
            raise AssertionError(f"unexpected wait or command: {label} {args}")

        event = module.submit_agent_browser_prompt(
            invoke=fake_invoke,
            provider="chatgpt",
            prompt="hello",
            attachment_names=[],
            max_wait_seconds=30,
        )

        self.assertTrue(event["submitted"])
        self.assertEqual(event["method"], "enter")
        self.assertEqual([label for label, _ in calls], ["submit-readiness-0", "submit-prompt-js-click", "submit-prompt-enter"])

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

    def test_workflow_suite_sibling_run_passes_response_clipboard_and_attachments(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        source_root = root / "source"
        source_profile = source_root / "Default"
        source_profile.mkdir(parents=True)
        (source_root / "Local State").write_text("{}", encoding="utf-8")
        (source_profile / "Preferences").write_text("{}", encoding="utf-8")
        attachment = root / "note.txt"
        attachment.write_text("hello", encoding="utf-8")

        class FakeProcess:
            pid = 8181

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

        fake_process = FakeProcess()
        calls = []
        original_discover = module.discover_browsers
        original_start = module.start_sibling_cdp_browser
        original_live = module.agent_browser_live_workflow_run
        original_port = module.find_available_port
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": str(source_root),
                "default_port": 9222,
                "profiles": [{"directory": "Default", "name": "Work", "path": str(source_profile)}],
            }
        ]
        module.start_sibling_cdp_browser = lambda **kwargs: (
            fake_process,
            {"ok": True, "pid": fake_process.pid, "port": kwargs["port"], "launch_args": kwargs["launch_args"]},
        )
        module.find_available_port = lambda: 9449

        def fake_live(**kwargs):
            calls.append(kwargs)
            return {
                "status": "verified",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": "brave",
                "profile": "Default",
                "status_json": str(root / "status.json"),
                "output_text_path": str(root / "output.txt"),
                "clipboard": {"requested": kwargs["copy_output"], "copied": True, "text_length": 4},
            }

        module.agent_browser_live_workflow_run = fake_live
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "brave",
                        "--profile",
                        "work",
                        "--providers",
                        "chatgpt",
                        "--features",
                        "chatgpt:chat",
                        "--submit",
                        "--copy-output",
                        "--response-timeout",
                        "7",
                        "--attachment",
                        str(attachment),
                        "--session-state",
                        str(root / "session-state.json"),
                        "--close-after",
                        "--continue-on-failure",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.start_sibling_cdp_browser = original_start
            module.agent_browser_live_workflow_run = original_live
            module.find_available_port = original_port

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(calls[0]["response_timeout"], 7.0)
        self.assertTrue(calls[0]["copy_output"])
        self.assertEqual(calls[0]["attachments"], [attachment])
        self.assertEqual(calls[0]["browser"]["user_data_dir"], str(module.default_sibling_user_data_dir(browser="brave", profile="Default")))
        self.assertTrue(getattr(fake_process, "terminated", False))

    def test_detect_rate_limit_from_text_parses_wait_minutes(self):
        module = load_module()

        detected = module.detect_rate_limit_from_text("Rate limit reached. Please wait 5 minutes before trying again.")
        detected_de = module.detect_rate_limit_from_text("Bitte warte 7 Minuten, bevor du es erneut versuchst.")
        safe_report = module.detect_rate_limit_from_text("Respect robots.txt, rate limits, terms of service, and applicable law.")

        self.assertTrue(detected["limited"])
        self.assertEqual(detected["wait_seconds"], 300)
        self.assertTrue(detected_de["limited"])
        self.assertEqual(detected_de["wait_seconds"], 420)
        self.assertFalse(safe_report["limited"])

    def test_captcha_challenge_triggers_long_cooldown(self):
        module = load_module()

        detected = module.detect_rate_limit_from_text("Cloudflare Turnstile challenge: verify you are human")

        self.assertTrue(detected["limited"])
        self.assertEqual(detected["kind"], "challenge")
        self.assertGreaterEqual(detected["wait_seconds"], 30 * 60)

    def test_detect_rate_limit_from_payload_sees_guard_challenge(self):
        module = load_module()

        detected = module.detect_rate_limit_from_payload(
            {
                "status": "blocked",
                "pre_submit_guard": {
                    "errors": ["captcha-or-challenge-wall"],
                    "matched_markers": ["Turnstile challenge"],
                },
            }
        )

        self.assertTrue(detected["limited"])
        self.assertEqual(detected["kind"], "challenge")

    def test_rate_limit_state_records_and_blocks_active_key(self):
        module = load_module()
        state = {"version": 1, "entries": {}, "history": []}
        key = module.rate_limit_key(browser="brave", profile="Default", provider="chatgpt", mode="chat")

        entry = module.record_rate_limit(
            state,
            key,
            wait_seconds=120,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            mode="chat",
            reason="Please wait 2 minutes",
            source="/tmp/status.json",
            now=1000,
        )
        active = module.active_rate_limit(state, key, now=1050)
        module.cleanup_expired_rate_limits(state, now=1201)

        self.assertEqual(entry["learned_wait_seconds"], 120)
        self.assertIsNotNone(active)
        self.assertEqual(active["remaining_seconds"], 70)
        self.assertNotIn(key, state["entries"])

    def test_workflow_suite_skips_active_rate_limited_row_and_falls_back(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        state_path = root / "rate-limit-state.json"
        state = {"version": 1, "entries": {}, "history": []}
        key = module.rate_limit_key(browser="brave", profile="Default", provider="chatgpt", mode="chat")
        module.record_rate_limit(
            state,
            key,
            wait_seconds=3600,
            browser="brave",
            profile="Default",
            provider="chatgpt",
            mode="chat",
            reason="message limit",
            source="/tmp/status.json",
        )
        module.write_rate_limit_state(state_path, state)
        calls = []
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": str(root / "brave"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "brave" / "Default")}],
            },
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(root / "comet"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "comet" / "Default")}],
            },
        ]

        def fake_run(**kwargs):
            calls.append(kwargs)
            return {
                "status": "verified",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": kwargs["browser"]["id"],
                "profile": kwargs["source_profile"]["directory"],
            }

        module.run_sibling_workflow_payload = fake_run
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "brave,comet",
                        "--profile",
                        "Default",
                        "--providers",
                        "chatgpt",
                        "--features",
                        "chatgpt:chat",
                        "--submit",
                        "--no-rate-limit-wait",
                        "--rate-limit-state",
                        str(state_path),
                        "--session-state",
                        str(root / "session-state.json"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["summary"]["rate_limited"], 1)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(payload["results"][0]["run_status"], "rate-limited")
        self.assertTrue(payload["results"][0]["fallback"]["continued_to_next_row"])
        self.assertEqual(payload["results"][1]["run_status"], "verified")
        self.assertEqual([call["browser"]["id"] for call in calls], ["comet"])

    def test_workflow_suite_records_rate_limit_from_payload(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        state_path = root / "rate-limit-state.json"
        output_text = root / "output.txt"
        output_text.write_text("Message limit reached. Please wait 2 minutes before trying again.", encoding="utf-8")
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": str(root / "brave"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "brave" / "Default")}],
            }
        ]
        module.run_sibling_workflow_payload = lambda **kwargs: {
            "status": "captured",
            "provider": kwargs["provider"],
            "mode": kwargs["mode"],
            "browser": kwargs["browser"]["id"],
            "profile": kwargs["source_profile"]["directory"],
            "output_text_path": str(output_text),
        }
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "brave",
                        "--profile",
                        "Default",
                        "--providers",
                        "chatgpt",
                        "--features",
                        "chatgpt:chat",
                        "--submit",
                        "--no-rate-limit-wait",
                        "--rate-limit-state",
                        str(state_path),
                        "--session-state",
                        str(root / "session-state.json"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        stored_state = json.loads(state_path.read_text(encoding="utf-8"))
        key = module.rate_limit_key(browser="brave", profile="Default", provider="chatgpt", mode="chat")
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["summary"]["rate_limited"], 1)
        self.assertEqual(payload["results"][0]["run_status"], "rate-limited")
        self.assertIn(key, stored_state["entries"])
        self.assertEqual(stored_state["entries"][key]["learned_wait_seconds"], 120)

    def test_record_rate_limit_from_payload_persists_account_cooldown(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        state_path = root / "rate-limit-state.json"

        result = module.record_rate_limit_from_payload(
            {
                "status": "blocked",
                "pre_submit_guard": {
                    "account": "work@example.test",
                    "errors": ["captcha-or-challenge-wall"],
                },
            },
            browser="brave",
            profile="Default",
            provider="chatgpt",
            mode="chat",
            state_path=state_path,
            source="/tmp/status.json",
        )

        stored_state = json.loads(state_path.read_text(encoding="utf-8"))
        key = module.rate_limit_key(
            browser="brave",
            profile="Default",
            provider="chatgpt",
            mode="chat",
            account="work@example.test",
        )
        self.assertTrue(result["detected"])
        self.assertIn(key, stored_state["entries"])
        self.assertEqual(stored_state["entries"][key]["reason"], "challenge")
        self.assertGreaterEqual(stored_state["entries"][key]["learned_wait_seconds"], 30 * 60)

    def test_workflow_suite_row_timeout_marks_timeout_and_continues(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        calls = []
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": str(root / "brave"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "brave" / "Default")}],
            },
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(root / "comet"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "comet" / "Default")}],
            },
        ]

        def fake_run(**kwargs):
            calls.append(kwargs["browser"]["id"])
            if kwargs["browser"]["id"] == "brave":
                time.sleep(3)
            return {
                "status": "verified",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": kwargs["browser"]["id"],
                "profile": kwargs["source_profile"]["directory"],
            }

        module.run_sibling_workflow_payload = fake_run
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "brave,comet",
                        "--profile",
                        "Default",
                        "--providers",
                        "chatgpt",
                        "--features",
                        "chatgpt:agent",
                        "--submit",
                        "--continue-on-failure",
                        "--row-timeout-seconds",
                        "1",
                        "--session-state",
                        str(root / "session-state.json"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(calls, ["brave", "comet"])
        self.assertEqual(payload["results"][0]["run_status"], "timeout")
        self.assertEqual(payload["results"][1]["run_status"], "verified")
        self.assertEqual(payload["summary"]["blocked"], 1)

    def test_workflow_suite_summary_counts_real_session_required_as_blocked(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "binary_path": "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "user_data_dir": str(root / "brave"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "brave" / "Default")}],
            }
        ]

        def fake_run(**kwargs):
            return {
                "status": "real-session-required",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": kwargs["browser"]["id"],
                "profile": kwargs["source_profile"]["directory"],
                "inventory": {"login_state": "signed-out-or-wall"},
            }

        module.run_sibling_workflow_payload = fake_run
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "brave",
                        "--profile",
                        "Default",
                        "--features",
                        "claude:chat",
                        "--submit",
                        "--continue-on-failure",
                        "--session-state",
                        str(root / "session-state.json"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["summary"]["blocked"], 1)
        self.assertEqual(payload["summary"]["real_session_required"], 1)

    def test_workflow_suite_quality_gate_fails_short_or_unknown_success(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(root / "comet"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "comet" / "Default")}],
            }
        ]

        def fake_run(**kwargs):
            return {
                "status": "verified",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": kwargs["browser"]["id"],
                "profile": kwargs["source_profile"]["directory"],
                "chat_url": "https://chatgpt.com/",
                "inventory": {"login_state": "unknown"},
                "output": {"status": "captured", "text_length": 7},
            }

        module.run_sibling_workflow_payload = fake_run
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "comet",
                        "--profile",
                        "Default",
                        "--features",
                        "chatgpt:deep-research",
                        "--submit",
                        "--continue-on-failure",
                        "--require-login-state",
                        "--min-output-chars",
                        "40",
                        "--min-research-output-chars",
                        "500",
                        "--session-state",
                        str(root / "session-state.json"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["results"][0]["run_status"], "quality-failed")
        self.assertEqual(payload["results"][0]["raw_run_status"], "verified")
        self.assertIn("output-too-short:7<500", payload["results"][0]["quality_errors"])
        self.assertIn("login-state-not-ready:unknown", payload["results"][0]["quality_errors"])
        self.assertEqual(payload["summary"]["quality_failed"], 1)

    def test_session_regression_tracking_flags_disappearing_account(self):
        module = load_module()
        state = {"version": 1, "entries": {}, "history": []}
        ok_result = {
            "browser": "comet",
            "profile_directory": "Default",
            "provider": "gemini",
            "run_status": "verified",
            "ok": True,
            "chat_url": "https://gemini.google.com/app/good",
            "inventory": {"login_state": "signed-in-or-ready"},
            "output": {"text_length": 1200},
        }

        recorded, event = module.apply_session_regression_tracking(ok_result, state, now=1000)
        self.assertIsNone(event)
        self.assertEqual(recorded["session_baseline"]["status"], "recorded")

        bad_result = {
            "browser": "comet",
            "profile_directory": "Default",
            "provider": "gemini",
            "run_status": "verified",
            "ok": True,
            "chat_url": "https://gemini.google.com/app",
            "inventory": {"login_state": "signed-out-or-wall"},
            "output": {"text_length": 80},
        }
        regressed, event = module.apply_session_regression_tracking(bad_result, state, now=1200)

        self.assertIsNotNone(event)
        self.assertEqual(regressed["run_status"], "session-regressed")
        self.assertFalse(regressed["ok"])
        self.assertEqual(event["previous_chat_url"], "https://gemini.google.com/app/good")

    def test_workflow_suite_marks_session_regression_from_state_file(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        state_path = root / "session-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": {
                        "comet|default|chatgpt": {
                            "key": "comet|default|chatgpt",
                            "browser": "comet",
                            "profile": "Default",
                            "provider": "chatgpt",
                            "login_state": "signed-in-or-ready",
                            "last_ok_at": 1000,
                            "last_chat_url": "https://chatgpt.com/c/previous",
                        }
                    },
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        original_discover = module.discover_browsers
        original_run = module.run_sibling_workflow_payload
        module.discover_browsers = lambda: [
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(root / "comet"),
                "profiles": [{"directory": "Default", "name": "Default", "path": str(root / "comet" / "Default")}],
            }
        ]

        def fake_run(**kwargs):
            return {
                "status": "verified",
                "provider": kwargs["provider"],
                "mode": kwargs["mode"],
                "browser": kwargs["browser"]["id"],
                "profile": kwargs["source_profile"]["directory"],
                "chat_url": "https://chatgpt.com/",
                "inventory": {"login_state": "unknown"},
                "output": {"status": "captured", "text_length": 80},
            }

        module.run_sibling_workflow_payload = fake_run
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-suite",
                        "--sibling",
                        "--browsers",
                        "comet",
                        "--profile",
                        "Default",
                        "--features",
                        "chatgpt:chat",
                        "--submit",
                        "--continue-on-failure",
                        "--session-state",
                        str(state_path),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.run_sibling_workflow_payload = original_run

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["summary"]["session_regressed"], 1)
        self.assertEqual(payload["results"][0]["run_status"], "session-regressed")
        self.assertEqual(payload["results"][0]["session_regression"]["previous_chat_url"], "https://chatgpt.com/c/previous")

    def test_sibling_workflow_real_session_required_includes_healing_command(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        source_root = root / "source"
        source_profile = source_root / "Default"
        source_profile.mkdir(parents=True)
        (source_root / "Local State").write_text("{}", encoding="utf-8")
        (source_profile / "Preferences").write_text("{}", encoding="utf-8")

        class FakeProcess:
            pid = 9292

            def poll(self):
                return None

        original_start = module.start_sibling_cdp_browser
        original_live = module.agent_browser_live_workflow_run
        original_port = module.find_available_port
        module.start_sibling_cdp_browser = lambda **kwargs: (FakeProcess(), {"ok": True, "pid": 9292, "port": kwargs["port"]})
        module.find_available_port = lambda: 9550
        module.agent_browser_live_workflow_run = lambda **kwargs: {
            "status": "real-session-required",
            "provider": kwargs["provider"],
            "mode": kwargs["mode"],
            "browser": "comet",
            "profile": "Default",
            "status_json": str(root / "status.json"),
        }
        try:
            payload = module.run_sibling_workflow_payload(
                browser={
                    "id": "comet",
                    "display_name": "Comet",
                    "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                    "user_data_dir": str(source_root),
                },
                source_profile={"directory": "Default", "name": "Neptune", "path": str(source_profile)},
                provider="gemini",
                mode="deep-research",
                prompt="Research",
                artifact_root=root / "artifacts",
                submit=True,
                confirm_start=True,
                wait_seconds=1,
                response_timeout=1,
                copy_output=True,
                timeout=10,
                cache_root=None,
                refresh_cache=True,
                include_extension_ids=None,
                attachments=[],
                close_after=False,
                sibling_user_data=root / "sibling",
            )
        finally:
            module.start_sibling_cdp_browser = original_start
            module.agent_browser_live_workflow_run = original_live
            module.find_available_port = original_port

        self.assertEqual(payload["status"], "real-session-required")
        self.assertEqual(payload["healing"]["reason"], "provider-login-or-consent-required-in-sibling-profile")
        self.assertIn("sibling-profile-init", payload["healing"]["command"])
        self.assertIn("--provider", payload["healing"]["command"])
        self.assertIn("gemini", payload["healing"]["command"])

    def test_create_e2e_attachment_assets_writes_text_image_and_video(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())

        assets = module.create_e2e_attachment_assets(root)

        self.assertEqual([path.suffix for path in assets], [".txt", ".png", ".mp4"])
        self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in assets))

    def test_create_e2e_attachment_assets_uses_ffmpeg_for_valid_video_when_available(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_which = module.shutil.which
        original_run = module.subprocess.run
        calls = []
        module.shutil.which = lambda name: "/opt/homebrew/bin/ffmpeg" if name == "ffmpeg" else None

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            Path(cmd[-1]).write_bytes(b"valid-mp4")
            return module.subprocess.CompletedProcess(cmd, 0, "", "")

        module.subprocess.run = fake_run
        try:
            assets = module.create_e2e_attachment_assets(root)
        finally:
            module.shutil.which = original_which
            module.subprocess.run = original_run

        self.assertEqual(assets[-1].read_bytes(), b"valid-mp4")
        self.assertTrue(any("ffmpeg" in cmd[0] for cmd in calls))

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
            if "__AI_RESEARCH_COMPOSER_STATE__" in script:
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

    def test_build_live_workflow_plan_opens_new_tab_and_preserves_existing_tabs(self):
        module = load_module()

        plan = module.build_live_ai_workflow_plan(
            browser={"id": "brave", "display_name": "Brave Browser"},
            profile={"directory": "Default", "name": "Work"},
            provider="chatgpt",
            mode="agent",
            prompt="Test agent",
            artifact_root=Path("/tmp/artifacts"),
            cdp_port=9222,
            submit=True,
            confirm_start=True,
        )

        self.assertEqual(plan["isolation"], "live-cdp-background-tab")
        self.assertEqual(plan["cdp_port"], 9222)
        self.assertFalse(plan["safety"]["uses_profile_clone"])
        self.assertTrue(plan["safety"]["opens_new_tab_only"])
        self.assertTrue(plan["safety"]["does_not_close_existing_tabs"])
        self.assertEqual(plan["actions"][0]["label"], "open-background-tab")
        self.assertNotIn("open-provider", [action["label"] for action in plan["actions"]])

    def test_live_workflow_uses_cdp_tab_new_and_leaves_tab_open(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        commands_seen: list[list[str]] = []

        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_key = module.run_cdp_keypress
        original_capture = module.capture_cdp_screenshot
        original_create_target = module.run_cdp_create_automation_target
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }

        def fake_run(args, *, session="", timeout=45.0):
            commands_seen.append(args)
            command = ["agent-browser", *args]
            if args[:3] == ["--cdp", "9222", "tab"]:
                return module.subprocess.CompletedProcess(command, 0, stdout="new tab", stderr="")
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(
                    command,
                    0,
                    stdout='ChatGPT\nIsagi yoichi\nPro\ntextbox "Message ChatGPT" [ref=e35]',
                    stderr="",
                )
            if "click" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/live", "")
            if "const text =" in script:
                return module.subprocess.CompletedProcess(["js"], 0, '{"ok":true}', "")
            if "el.click()" in script:
                return module.subprocess.CompletedProcess(["js"], 0, '{"ok":false,"reason":"not-found"}', "")
            return module.subprocess.CompletedProcess(["js"], 0, "ChatGPT\nIsagi yoichi\nPro\nMessage ChatGPT\nFinal answer\nReady", "")

        module.run_agent_browser = fake_run
        module.run_cdp_navigate = lambda port, url, timeout=20.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_javascript = fake_js
        module.run_cdp_keypress = lambda port, key, timeout=10.0: module.subprocess.CompletedProcess(["key"], 0, "ok", "")
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(
            ["target"],
            0,
            '{"targetId":"automation-target-1"}',
            "",
        )
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="chatgpt",
                mode="chat",
                prompt="Say READY",
                artifact_root=root / "artifacts",
                cdp_port=9222,
                wait_seconds=1,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.run_cdp_keypress = original_key
            module.capture_cdp_screenshot = original_capture
            module.run_cdp_create_automation_target = original_create_target

        self.assertEqual(payload["status"], "real-session-required")
        self.assertEqual(payload["isolation"], "live-cdp-background-tab")
        self.assertFalse(any(args[:3] == ["--cdp", "9222", "tab"] for args in commands_seen))
        self.assertFalse(any("close" in args for args in commands_seen))
        self.assertTrue(Path(payload["screenshot"]).exists())
        self.assertTrue(any(event.get("event") == "pre-typing-login-gate" for event in payload["workflow_events"]))

    def test_live_workflow_does_not_type_slash_feature_before_pre_submit_guard(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        scripts_seen: list[str] = []

        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_capture = module.capture_cdp_screenshot
        original_create_target = module.run_cdp_create_automation_target
        original_sleep = module.time.sleep
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }

        visible = "ChatGPT\nSigned in as work@example.test\nPlus plan\nExtended Pro\nDeep research\nAgent\nMessage ChatGPT\n"

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout='- textbox "Message ChatGPT" [ref=e1]\n', stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            scripts_seen.append(script)
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/live", "")
            if "const wanted =" in script:
                return module.subprocess.CompletedProcess(["js"], 0, '{"ok":false,"reason":"not-found"}', "")
            return module.subprocess.CompletedProcess(["js"], 0, visible, "")

        module.run_agent_browser = fake_run
        module.run_cdp_navigate = lambda port, url, timeout=20.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_javascript = fake_js
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(
            ["target"],
            0,
            '{"targetId":"automation-target-1"}',
            "",
        )
        module.time.sleep = lambda seconds: None
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="chatgpt",
                mode="deep-research",
                prompt="Research why slash fallback must be guard-gated.",
                artifact_root=root / "artifacts",
                cdp_port=9223,
                submit=True,
                wait_seconds=1,
                response_timeout=1,
                allow_paid_quota_use=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.capture_cdp_screenshot = original_capture
            module.run_cdp_create_automation_target = original_create_target
            module.time.sleep = original_sleep

        self.assertEqual(payload["status"], "model-safety-blocked")
        self.assertIn("chatgpt-pro-model-blocked", payload["pre_submit_guard"]["errors"])
        self.assertFalse(any("/Deepresearch" in script or "/deep research" in script for script in scripts_seen))
        self.assertTrue(
            any(
                event.get("event") == "slash-feature" and event.get("skipped") == "pre-submit-guard-blocked"
                for event in payload["workflow_events"]
            )
        )

    def test_live_workflow_blocks_when_real_cdp_session_is_not_attachable(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": False,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": ["browser-running-without-remote-debugging"],
        }
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="gemini",
                mode="deep-research",
                prompt="Research",
                artifact_root=root / "artifacts",
                cdp_port=9222,
            )
        finally:
            module.build_real_session_preflight = original_preflight

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("not attachable", payload["blocker"])
        self.assertIn("browser-running-without-remote-debugging", payload["real_session_preflight"]["blockers"])

    def test_live_workflow_requires_automation_target_before_navigation(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_create = module.run_cdp_create_automation_target
        original_nav = module.run_cdp_navigate
        nav_called = {"value": False}
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": True, "blockers": [], "session_evidence": {"confidence": "likely-logged-in"}}
        module.run_cdp_create_automation_target = lambda *args, **kwargs: module.subprocess.CompletedProcess(["create"], 1, "", "failed")

        def fake_nav(*args, **kwargs):
            nav_called["value"] = True
            return module.subprocess.CompletedProcess(["nav"], 0, "", "")

        module.run_cdp_navigate = fake_nav
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="chatgpt",
                mode="chat",
                prompt="Say READY",
                artifact_root=root / "artifacts",
                cdp_port=9223,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_cdp_create_automation_target = original_create
            module.run_cdp_navigate = original_nav

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("automation target creation failed", payload["blocker"].lower())
        self.assertFalse(nav_called["value"])

    def test_cmd_workflow_live_run_outputs_blocker_without_closing_browser(self):
        module = load_module()
        original_discover = module.discover_browsers
        original_preflight = module.build_real_session_preflight
        module.discover_browsers = lambda: [
            {
                "id": "brave",
                "display_name": "Brave Browser",
                "default_port": 9222,
                "profiles": [{"directory": "Default", "name": "Work", "path": ""}],
            }
        ]
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": False,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": ["browser-running-without-remote-debugging"],
        }
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-live-run",
                        "--browser",
                        "brave",
                        "--profile",
                        "work",
                        "--provider",
                        "google",
                        "--mode",
                        "deep-research",
                        "--prompt",
                        "Research safely",
                        "--cdp-port",
                        "9222",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.build_real_session_preflight = original_preflight

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["isolation"], "live-cdp-background-tab")
        self.assertTrue(payload["safety"]["does_not_close_existing_browser_windows"])

    def test_default_sibling_profile_dir_is_separate_from_source_profile(self):
        module = load_module()

        path = module.default_sibling_user_data_dir(browser="Comet", profile="Default")

        self.assertEqual(path.name, "user-data")
        self.assertIn("comet-default", str(path))
        self.assertIn(".cache/ai-research-browser/sibling-profiles", str(path))

    def test_clean_sibling_profile_locks_removes_startup_locks_only(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        profile = root / "Default"
        profile.mkdir()
        for name in ["SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort"]:
            (root / name).write_text("stale", encoding="utf-8")
        (profile / "LOCK").write_text("stale", encoding="utf-8")
        (profile / "Preferences").write_text("{}", encoding="utf-8")

        removed = module.clean_sibling_profile_locks(root, "Default")

        self.assertEqual(
            sorted(Path(item).name for item in removed),
            ["DevToolsActivePort", "LOCK", "SingletonCookie", "SingletonLock", "SingletonSocket"],
        )
        self.assertTrue((profile / "Preferences").exists())

    def test_prepare_sibling_profile_seeds_reuses_and_can_refresh(self):
        module = load_module()
        source_root = Path(tempfile.mkdtemp())
        source_profile = source_root / "Default"
        source_profile.mkdir(parents=True)
        (source_root / "Local State").write_text('{"profile":{}}', encoding="utf-8")
        (source_profile / "Preferences").write_text('{"profile":{"name":"Work"}}', encoding="utf-8")
        (source_profile / "SingletonLock").write_text("do-not-copy", encoding="utf-8")
        sibling_user_data = Path(tempfile.mkdtemp()) / "sibling" / "user-data"

        first = module.prepare_sibling_profile(
            browser={"id": "brave", "user_data_dir": str(source_root)},
            profile={"directory": "Default", "path": str(source_profile)},
            sibling_user_data=sibling_user_data,
            refresh=False,
        )
        second = module.prepare_sibling_profile(
            browser={"id": "brave", "user_data_dir": str(source_root)},
            profile={"directory": "Default", "path": str(source_profile)},
            sibling_user_data=sibling_user_data,
            refresh=False,
        )
        refreshed = module.prepare_sibling_profile(
            browser={"id": "brave", "user_data_dir": str(source_root)},
            profile={"directory": "Default", "path": str(source_profile)},
            sibling_user_data=sibling_user_data,
            refresh=True,
        )

        self.assertEqual(first["status"], "seeded")
        self.assertEqual(second["status"], "reused")
        self.assertEqual(refreshed["status"], "refreshed")
        self.assertTrue((sibling_user_data / "Default" / "Preferences").exists())
        self.assertTrue((sibling_user_data / "Local State").exists())
        self.assertFalse((sibling_user_data / "Default" / "SingletonLock").exists())
        self.assertNotEqual(first["sibling_user_data"], str(source_root))

    def test_sibling_launch_args_are_headful_offscreen_by_default(self):
        module = load_module()

        args = module.build_sibling_cdp_launch_args(
            {"binary_path": "/Applications/Comet.app/Contents/MacOS/Comet"},
            sibling_user_data="/tmp/sibling/user-data",
            profile_directory="Default",
            port=9333,
            provider="google",
            headless=False,
        )

        self.assertEqual(args[0], "/Applications/Comet.app/Contents/MacOS/Comet")
        self.assertIn("--remote-debugging-port=9333", args)
        self.assertIn("--user-data-dir=/tmp/sibling/user-data", args)
        self.assertIn("--profile-directory=Default", args)
        self.assertIn("--window-position=-9999,0", args)
        self.assertIn("--disable-background-timer-throttling", args)
        self.assertNotIn("--headless=new", args)
        self.assertEqual(args[-1], "https://gemini.google.com/app?hl=de")

    def test_start_clone_waits_for_cdp_endpoint_not_only_open_port(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        attempts = []

        class FakeProcess:
            pid = 9090

            def poll(self):
                return None

        original_popen = module.subprocess.Popen
        original_is_port_open = module.is_port_open
        original_detect = module.detect_cdp_endpoint
        original_sleep = module.time.sleep
        module.subprocess.Popen = lambda *args, **kwargs: FakeProcess()
        module.is_port_open = lambda port: True

        def fake_detect(port):
            attempts.append(port)
            return {"ok": len(attempts) >= 3, "base": "http://127.0.0.1:9444" if len(attempts) >= 3 else "", "attempts": []}

        module.detect_cdp_endpoint = fake_detect
        module.time.sleep = lambda seconds: None
        try:
            process, status = module.start_clone_cdp_browser(
                launch_args=["/Applications/Fake.app/Contents/MacOS/Fake", "--remote-debugging-port=9444"],
                port=9444,
                log_path=root / "browser.log",
                startup_timeout=1.0,
            )
        finally:
            module.subprocess.Popen = original_popen
            module.is_port_open = original_is_port_open
            module.detect_cdp_endpoint = original_detect
            module.time.sleep = original_sleep

        self.assertIsNotNone(process)
        self.assertTrue(status["ok"])
        self.assertEqual(status["cdp_base"], "http://127.0.0.1:9444")
        self.assertGreaterEqual(len(attempts), 3)

    def test_real_session_preflight_can_ignore_existing_non_cdp_for_sibling(self):
        module = load_module()
        original_endpoint = module.detect_cdp_endpoint
        original_owner = module.lsof_port_owner
        original_args = module.browser_main_process_args
        original_evidence = module.provider_session_evidence
        module.detect_cdp_endpoint = lambda port, hosts=None: {"ok": True, "base": "http://127.0.0.1:9333", "version": {"Browser": "Comet"}, "attempts": []}
        module.lsof_port_owner = lambda port: {"port": port, "listening": True, "command": "Comet", "pid": "123", "raw": ""}
        module.browser_main_process_args = lambda browser: ["/Applications/Comet.app/Contents/MacOS/Comet"]
        module.provider_session_evidence = lambda profile, provider: {"provider": provider, "confidence": "likely-logged-in"}
        try:
            payload = module.build_real_session_preflight(
                browser={"id": "comet", "display_name": "Comet", "default_port": 9333, "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet"},
                profile={"directory": "Default", "name": "Automation"},
                provider="google",
                ignore_existing_non_cdp=True,
            )
        finally:
            module.detect_cdp_endpoint = original_endpoint
            module.lsof_port_owner = original_owner
            module.browser_main_process_args = original_args
            module.provider_session_evidence = original_evidence

        self.assertTrue(payload["can_attach"])
        self.assertEqual(payload["blockers"], [])
        self.assertTrue(payload["ignored_existing_non_cdp_processes"])

    def test_real_session_preflight_cli_passes_ignore_existing_non_cdp(self):
        module = load_module()
        original_resolve = module.resolve_workflow_browser_profile
        original_preflight = module.build_real_session_preflight
        captured = {}
        module.resolve_workflow_browser_profile = lambda args: (
            {"id": "brave", "display_name": "Brave Browser", "default_port": 9444},
            {"directory": "Default", "name": "Work"},
        )

        def fake_preflight(**kwargs):
            captured.update(kwargs)
            return {"can_attach": True, "blockers": [], "ignored_existing_non_cdp_processes": kwargs.get("ignore_existing_non_cdp")}

        module.build_real_session_preflight = fake_preflight
        try:
            args = module.build_parser().parse_args(
                [
                    "real-session-preflight",
                    "--browser",
                    "brave",
                    "--profile",
                    "Default",
                    "--provider",
                    "chatgpt",
                    "--port",
                    "9444",
                    "--ignore-existing-non-cdp",
                ]
            )
            rc = module.cmd_real_session_preflight(args)
        finally:
            module.resolve_workflow_browser_profile = original_resolve
            module.build_real_session_preflight = original_preflight

        self.assertEqual(rc, 0)
        self.assertTrue(captured["ignore_existing_non_cdp"])

    def test_workflow_sibling_run_prepares_launches_and_uses_live_runner(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        source_root = root / "source"
        source_profile = source_root / "Default"
        source_profile.mkdir(parents=True)
        (source_root / "Local State").write_text("{}", encoding="utf-8")
        (source_profile / "Preferences").write_text("{}", encoding="utf-8")

        class FakeProcess:
            pid = 4242

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

        fake_process = FakeProcess()
        original_discover = module.discover_browsers
        original_start = module.start_sibling_cdp_browser
        original_live = module.agent_browser_live_workflow_run
        module.discover_browsers = lambda: [
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(source_root),
                "default_port": 9223,
                "profiles": [{"directory": "Default", "name": "Neptune", "path": str(source_profile)}],
            }
        ]
        module.start_sibling_cdp_browser = lambda **kwargs: (
            fake_process,
            {"ok": True, "pid": fake_process.pid, "port": kwargs["port"], "launch_args": kwargs["launch_args"]},
        )

        def fake_live(**kwargs):
            self.assertEqual(kwargs["browser"]["user_data_dir"], str(root / "sibling" / "user-data"))
            self.assertEqual(kwargs["cdp_port"], 9333)
            return {
                "status": "opened",
                "provider": "gemini",
                "mode": "deep-research",
                "browser": "comet",
                "profile": "Default",
                "status_json": str(root / "status.json"),
                "output_text_path": str(root / "output.txt"),
            }

        module.agent_browser_live_workflow_run = fake_live
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "workflow-sibling-run",
                        "--browser",
                        "comet",
                        "--profile",
                        "work",
                        "--provider",
                        "google",
                        "--mode",
                        "deep-research",
                        "--prompt",
                        "Research",
                        "--cdp-port",
                        "9333",
                        "--sibling-user-data",
                        str(root / "sibling" / "user-data"),
                        "--close-after",
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.start_sibling_cdp_browser = original_start
            module.agent_browser_live_workflow_run = original_live

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "opened")
        self.assertEqual(payload["execution_mode"], "sibling-cdp-automation-profile")
        self.assertEqual(payload["sibling_profile"]["status"], "seeded")
        self.assertTrue(payload["launch"]["ok"])
        self.assertTrue(payload["closed_after"])
        self.assertTrue(getattr(fake_process, "terminated", False))

    def test_sibling_workflow_escalates_cookie_evidence_wall_to_real_session_required(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_capture = module.capture_cdp_screenshot
        original_clipboard = module.copy_text_to_clipboard
        original_create_target = module.run_cdp_create_automation_target
        copied = []
        agent_browser_calls = []
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }

        def fake_run(args, *, session="", timeout=45.0):
            agent_browser_calls.append(args)
            command = ["agent-browser", *args]
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 124, stdout="", stderr="snapshot should be skipped")
            if args[:3] == ["--cdp", "9335", "tab"]:
                return module.subprocess.CompletedProcess(command, 0, stdout="https://gemini.google.com/app?hl=de\n", stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://gemini.google.com/app?hl=de", "")
            return module.subprocess.CompletedProcess(["js"], 0, "Anmelden\nGemini\nEinen Prompt für Gemini eingeben", "")

        module.run_agent_browser = fake_run
        module.run_cdp_navigate = lambda port, url, timeout=20.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_javascript = fake_js
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        module.copy_text_to_clipboard = lambda text: copied.append(text) or {"copied": True, "text_length": len(text)}
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(
            ["target"],
            0,
            '{"targetId":"automation-target-1"}',
            "",
        )
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "comet", "display_name": "Comet"},
                profile={"directory": "Default", "name": "Automation"},
                provider="google",
                mode="deep-research",
                prompt="Research",
                artifact_root=root / "artifacts",
                cdp_port=9335,
                allow_real_session_required=True,
                copy_output=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.capture_cdp_screenshot = original_capture
            module.copy_text_to_clipboard = original_clipboard
            module.run_cdp_create_automation_target = original_create_target

        self.assertEqual(payload["status"], "real-session-required")
        self.assertEqual(payload["inventory"]["login_state"], "signed-out-or-wall")
        self.assertEqual(payload["healing"]["reason"], "provider-login-or-consent-required-in-sibling-profile")
        self.assertIn("sibling-profile-init", payload["healing"]["command"])
        self.assertEqual(copied, [])
        self.assertFalse(payload["clipboard"]["copied"])
        self.assertFalse(any("snapshot" in call for call in agent_browser_calls))

    def test_live_login_heal_clicks_login_and_reports_healed(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_js = module.run_cdp_javascript
        original_capture = module.capture_cdp_screenshot
        evals = []
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            if args[:3] == ["--cdp", "9442", "tab"]:
                return module.subprocess.CompletedProcess(command, 0, stdout="https://chatgpt.com/\n", stderr="")
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout='- button "Log in" [ref=e1]\n', stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            evals.append(script)
            if "__AI_RESEARCH_LOGIN_HEAL__" in script:
                return module.subprocess.CompletedProcess(["js"], 0, json.dumps({"ok": True, "label": "Log in"}), "")
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/", "")
            if len([item for item in evals if "__AI_RESEARCH_LOGIN_HEAL__" not in item and "location.href" not in item]) < 2:
                return module.subprocess.CompletedProcess(["js"], 0, "Log in\nSign up for free\nChatGPT", "")
            return module.subprocess.CompletedProcess(["js"], 0, "Isagi\nPro\nMessage ChatGPT\nGPT-5", "")

        module.run_agent_browser = fake_run
        module.run_cdp_javascript = fake_js
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        try:
            payload = module.agent_browser_live_login_heal(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="chatgpt",
                artifact_root=root / "artifacts",
                cdp_port=9442,
                wait_seconds=1,
                timeout=10,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_javascript = original_js
            module.capture_cdp_screenshot = original_capture

        self.assertEqual(payload["status"], "healed")
        self.assertEqual(payload["before_inventory"]["login_state"], "signed-out-or-wall")
        self.assertEqual(payload["after_inventory"]["login_state"], "signed-in-or-ready")
        self.assertEqual(payload["click"]["label"], "Log in")
        self.assertTrue(payload["screenshot"].endswith("screenshot.png"))

    def test_live_login_heal_can_chain_safe_provider_sso_clicks(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_js = module.run_cdp_javascript
        original_capture = module.capture_cdp_screenshot
        texts = iter(
            [
                "Log in\nChatGPT",
                json.dumps({"ok": True, "label": "Log in"}),
                "Log in or sign up\nContinue with Google\nContinue with Apple",
                json.dumps({"ok": True, "label": "Continue with Google"}),
                "Isagi\nPro\nMessage ChatGPT\nGPT-5",
            ]
        )
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": True, "session_evidence": {"confidence": "likely-logged-in"}, "blockers": []}
        module.run_agent_browser = lambda args, session="", timeout=45.0: module.subprocess.CompletedProcess(["agent-browser", *args], 0, "https://chatgpt.com/\n" if "tab" in args else "", "")

        def fake_js(port, script, timeout=15.0):
            if "__AI_RESEARCH_LOGIN_HEAL__" not in script and "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/", "")
            return module.subprocess.CompletedProcess(["js"], 0, next(texts), "")

        module.run_cdp_javascript = fake_js
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        try:
            payload = module.agent_browser_live_login_heal(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Work"},
                provider="chatgpt",
                artifact_root=root / "artifacts",
                cdp_port=9443,
                wait_seconds=1,
                timeout=10,
                max_steps=3,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_javascript = original_js
            module.capture_cdp_screenshot = original_capture

        self.assertEqual(payload["status"], "healed")
        self.assertEqual([step["result"]["label"] for step in payload["click_steps"]], ["Log in", "Continue with Google"])

    def test_login_heal_script_contains_safe_login_labels_but_no_password_fill(self):
        module = load_module()

        script = module.login_heal_js_script("chatgpt")

        self.assertIn("__AI_RESEARCH_LOGIN_HEAL__", script)
        self.assertIn("Log in", script)
        self.assertNotIn("password", script.lower())
        self.assertNotIn(".value =", script)

    def test_copy_text_to_clipboard_uses_pbcopy_without_echoing_text(self):
        module = load_module()
        calls = []
        original_run = module.subprocess.run

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return module.subprocess.CompletedProcess(cmd, 0, "", "")

        module.subprocess.run = fake_run
        try:
            result = module.copy_text_to_clipboard("E2E_RESPONSE_READY")
        finally:
            module.subprocess.run = original_run

        self.assertTrue(result["copied"])
        self.assertEqual(result["text_length"], len("E2E_RESPONSE_READY"))
        self.assertEqual(calls[0][0], ["pbcopy"])
        self.assertEqual(calls[0][1]["input"], "E2E_RESPONSE_READY")
        self.assertTrue(calls[0][1]["text"])
        self.assertTrue(calls[0][1]["capture_output"])

    def test_live_workflow_submit_waits_for_response_and_copies_output(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_keypress = module.run_cdp_keypress
        original_capture = module.capture_cdp_screenshot
        original_sleep = module.time.sleep
        original_clipboard = module.copy_text_to_clipboard
        original_create_target = module.run_cdp_create_automation_target
        eval_texts = iter(
            [
                "ChatGPT\nIsagi yoichi\nPro\nGPT\nMessage ChatGPT",
                "ChatGPT\nIsagi yoichi\nPro\nGPT\nMessage ChatGPT",
                "ChatGPT\nIsagi yoichi\nPro\nGPT\nStop generating\nE2E answer is loading",
                "ChatGPT\nIsagi yoichi\nPro\nGPT\nFinal answer\nE2E_RESPONSE_READY\nDone",
                "ChatGPT\nIsagi yoichi\nPro\nGPT\nFinal answer\nE2E_RESPONSE_READY\nDone",
            ]
        )
        copied = []
        module.build_real_session_preflight = lambda **kwargs: {
            "can_attach": True,
            "session_evidence": {"confidence": "likely-logged-in"},
            "blockers": [],
        }

        def fake_run(args, *, session="", timeout=45.0):
            command = ["agent-browser", *args]
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout='- textbox "Message ChatGPT" [ref=e1]\n', stderr="")
            if args[:3] == ["--cdp", "9336", "tab"]:
                return module.subprocess.CompletedProcess(command, 0, stdout="https://chatgpt.com/\n", stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://chatgpt.com/c/e2e", "")
            if "__AI_RESEARCH_LATEST_RESPONSE__" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "E2E_RESPONSE_READY", "")
            try:
                text = next(eval_texts)
            except StopIteration:
                text = "ChatGPT\nIsagi yoichi\nPro\nGPT\nFinal answer\nE2E_RESPONSE_READY\nDone"
            return module.subprocess.CompletedProcess(["js"], 0, text, "")

        module.run_agent_browser = fake_run
        module.run_cdp_navigate = lambda port, url, timeout=20.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_javascript = fake_js
        module.run_cdp_keypress = lambda port, key, timeout=10.0: module.subprocess.CompletedProcess(["keypress"], 0, "", "")
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        module.time.sleep = lambda seconds: None
        module.copy_text_to_clipboard = lambda text: copied.append(text) or {"copied": True, "text_length": len(text)}
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(
            ["target"],
            0,
            '{"targetId":"automation-target-1"}',
            "",
        )
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "brave", "display_name": "Brave Browser"},
                profile={"directory": "Default", "name": "Automation"},
                provider="chatgpt",
                mode="chat",
                prompt="Reply with E2E_RESPONSE_READY",
                artifact_root=root / "artifacts",
                cdp_port=9336,
                submit=True,
                wait_seconds=1,
                response_timeout=3,
                copy_output=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.run_cdp_keypress = original_keypress
            module.capture_cdp_screenshot = original_capture
            module.time.sleep = original_sleep
            module.copy_text_to_clipboard = original_clipboard
            module.run_cdp_create_automation_target = original_create_target

        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["output"]["text"], "E2E_RESPONSE_READY")
        self.assertEqual(copied, [payload["output"]["text"]])
        self.assertTrue(payload["clipboard"]["copied"])
        self.assertTrue(any(event["event"] == "wait-for-response" and event["status"] in {"complete", "stable"} for event in payload["workflow_events"]))

    def test_sibling_profile_init_opens_visible_manual_login_session(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        source_root = root / "source"
        source_profile = source_root / "Default"
        source_profile.mkdir(parents=True)
        (source_root / "Local State").write_text("{}", encoding="utf-8")
        (source_profile / "Preferences").write_text("{}", encoding="utf-8")

        class FakeProcess:
            pid = 5151

            def poll(self):
                return None

        original_discover = module.discover_browsers
        original_start = module.start_sibling_cdp_browser
        module.discover_browsers = lambda: [
            {
                "id": "comet",
                "display_name": "Comet",
                "binary_path": "/Applications/Comet.app/Contents/MacOS/Comet",
                "user_data_dir": str(source_root),
                "default_port": 9223,
                "profiles": [{"directory": "Default", "name": "Neptune", "path": str(source_profile)}],
            }
        ]

        def fake_start(**kwargs):
            self.assertIn("--window-position=80,80", kwargs["launch_args"])
            self.assertNotIn("--window-position=-9999,0", kwargs["launch_args"])
            return FakeProcess(), {"ok": True, "pid": 5151, "port": kwargs["port"], "launch_args": kwargs["launch_args"]}

        module.start_sibling_cdp_browser = fake_start
        try:
            out = StringIO()
            with redirect_stdout(out):
                exit_code = module.main(
                    [
                        "sibling-profile-init",
                        "--browser",
                        "comet",
                        "--profile",
                        "work",
                        "--provider",
                        "google",
                        "--cdp-port",
                        "9445",
                        "--sibling-user-data",
                        str(root / "sibling" / "user-data"),
                    ]
                )
        finally:
            module.discover_browsers = original_discover
            module.start_sibling_cdp_browser = original_start

        payload = json.loads(out.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "opened-for-manual-login")
        self.assertEqual(payload["execution_mode"], "sibling-profile-init")
        self.assertTrue(payload["manual_action_required"])
        self.assertEqual(payload["sibling_profile"]["status"], "seeded")

    def test_live_workflow_blocks_instead_of_active_tab_fallback_when_target_missing(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        original_preflight = module.build_real_session_preflight
        original_run = module.run_agent_browser
        original_nav = module.run_cdp_navigate
        original_js = module.run_cdp_javascript
        original_capture = module.capture_cdp_screenshot
        original_create_target = module.run_cdp_create_automation_target
        module.build_real_session_preflight = lambda **kwargs: {"can_attach": True, "session_evidence": {"confidence": "likely-logged-in"}, "blockers": []}
        sessions = []

        def fake_run(args, *, session="", timeout=45.0):
            sessions.append(session)
            command = ["agent-browser", *args]
            if args[:3] == ["--cdp", "9334", "tab"]:
                return module.subprocess.CompletedProcess(command, 1, stdout="", stderr="tab timeout")
            if "snapshot" in args:
                return module.subprocess.CompletedProcess(command, 0, stdout="Gemini\nPrompt eingeben\nDeep Research", stderr="")
            return module.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def fake_js(port, script, timeout=15.0):
            if "location.href" in script:
                return module.subprocess.CompletedProcess(["js"], 0, "https://gemini.google.com/app", "")
            if "const text =" in script:
                return module.subprocess.CompletedProcess(["js"], 0, '{"ok":true}', "")
            return module.subprocess.CompletedProcess(["js"], 0, "Gemini\nPrompt eingeben\nDeep Research", "")

        module.run_agent_browser = fake_run
        module.run_cdp_navigate = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(["nav"], 0, url, "")
        module.run_cdp_javascript = fake_js
        module.capture_cdp_screenshot = lambda port, screenshot, timeout=20.0: (screenshot.write_bytes(b"png") or True)
        module.run_cdp_create_automation_target = lambda port, url, timeout=15.0: module.subprocess.CompletedProcess(["target"], 1, "", "tab timeout")
        try:
            payload = module.agent_browser_live_workflow_run(
                browser={"id": "comet", "display_name": "Comet"},
                profile={"directory": "Default", "name": "Automation"},
                provider="google",
                mode="deep-research",
                prompt="Research",
                artifact_root=root / "artifacts",
                cdp_port=9334,
                allow_active_tab_navigation_fallback=True,
            )
        finally:
            module.build_real_session_preflight = original_preflight
            module.run_agent_browser = original_run
            module.run_cdp_navigate = original_nav
            module.run_cdp_javascript = original_js
            module.capture_cdp_screenshot = original_capture
            module.run_cdp_create_automation_target = original_create_target

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["blocker"], "CDP automation target creation failed")
        self.assertEqual(sessions, [])
        self.assertFalse(any(event["event"] == "open-background-tab-fallback-navigate" for event in payload["workflow_events"]))
        self.assertTrue(any(event.get("active_tab_navigation_fallback_requested") for event in payload["workflow_events"]))

    def test_cdp_helpers_use_detected_loopback_endpoint(self):
        module = load_module()
        original_detect = module.detect_cdp_endpoint
        original_run = module.subprocess.run
        commands = []
        module.detect_cdp_endpoint = lambda port: {"ok": True, "base": "http://[::1]:9444"}

        def fake_run(command, **kwargs):
            commands.append(command)
            return module.subprocess.CompletedProcess(command, 0, stdout="https://gemini.google.com/app", stderr="")

        module.subprocess.run = fake_run
        try:
            result = module.run_cdp_navigate(9444, "https://gemini.google.com/app")
        finally:
            module.detect_cdp_endpoint = original_detect
            module.subprocess.run = original_run

        self.assertEqual(result.returncode, 0)
        self.assertEqual(commands[0][4], "http://[::1]:9444")


if __name__ == "__main__":
    unittest.main()
