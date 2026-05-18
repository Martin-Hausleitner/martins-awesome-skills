#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


BROWSER_CANDIDATES = {
    "brave": {
        "display_name": "Brave Browser",
        "app_path": "/Applications/Brave Browser.app",
        "binary_rel": "Contents/MacOS/Brave Browser",
        "user_data_dir": "~/Library/Application Support/BraveSoftware/Brave-Browser",
        "default_port": 9222,
    },
    "comet": {
        "display_name": "Comet",
        "aliases": ["komet"],
        "app_path": "/Applications/Comet.app",
        "binary_rel": "Contents/MacOS/Comet",
        "user_data_dir": "~/Library/Application Support/Comet",
        "default_port": 9223,
    },
    "chrome": {
        "display_name": "Google Chrome",
        "app_path": "/Applications/Google Chrome.app",
        "binary_rel": "Contents/MacOS/Google Chrome",
        "user_data_dir": "~/Library/Application Support/Google/Chrome",
        "default_port": 9224,
    },
    "edge": {
        "display_name": "Microsoft Edge",
        "app_path": "/Applications/Microsoft Edge.app",
        "binary_rel": "Contents/MacOS/Microsoft Edge",
        "user_data_dir": "~/Library/Application Support/Microsoft Edge",
        "default_port": 9225,
    },
    "opera": {
        "display_name": "Opera",
        "app_path": "/Applications/Opera.app",
        "binary_rel": "Contents/MacOS/Opera",
        "user_data_dir": "~/Library/Application Support/com.operasoftware.Opera",
        "default_port": 9226,
    },
    "atlas": {
        "display_name": "ChatGPT Atlas",
        "app_path": "/Applications/ChatGPT Atlas.app",
        "binary_rel": "Contents/MacOS/ChatGPT Atlas",
        "user_data_dir": "~/Library/Application Support/com.openai.atlas/browser-data/host",
        "default_port": 9227,
    },
}


def provider_registry() -> dict[str, dict[str, Any]]:
    return {
        "chatgpt": {
            "url": "https://chatgpt.com/",
            "modes": ["chat", "deep-research", "agent"],
            "models": ["Auto", "GPT-5.3 Instant", "GPT-5.5", "GPT-5.5 Thinking", "GPT-5.5 Pro"],
            "tools": ["Deep research", "Agent", "Codex", "Search", "Canvas", "Data analysis", "Image generation"],
            "source_urls": ["https://help.openai.com/en/articles/11909943-gpt-52-in-chatgpt"],
            "mode_markers": {
                "deep-research": ["Deep research", "/Deepresearch", "Start research"],
                "agent": ["Agent", "/agent", "Take control", "Codex"],
                "chat": ["ChatGPT", "Message ChatGPT"],
            },
        },
        "gemini": {
            "url": "https://gemini.google.com/app?hl=de",
            "aliases": ["google", "google-gemini"],
            "modes": ["chat", "deep-research", "agent"],
            "models": ["Auto", "Fast", "Flash", "Complex", "Pro", "Thinking with 3 Pro", "Deep Think"],
            "tools": ["Deep Research", "Agent", "Deep Think", "Gmail", "Drive", "Google Search"],
            "source_urls": ["https://support.google.com/gemini/answer/16275805"],
            "mode_markers": {
                "deep-research": ["Deep Research", "Recherche starten", "Start research"],
                "agent": ["Agent", "Confirm", "Bestätigen"],
                "chat": ["Gemini", "Prompt eingeben"],
            },
        },
        "perplexity": {
            "url": "https://www.perplexity.ai/",
            "modes": ["chat", "research"],
            "models": [
                "Auto",
                "Sonar",
                "Sonar Pro",
                "Sonar Reasoning Pro",
                "Sonar Deep Research",
                "GPT-5.5",
                "Claude Sonnet 4.6",
                "Gemini 3.1 Pro",
            ],
            "tools": ["Search", "Pro Search", "Research", "Deep Research", "Agent API", "Spaces", "MCP"],
            "source_urls": ["https://docs.perplexity.ai/docs/sonar/models"],
            "mode_markers": {"research": ["Research", "Deep Research"], "chat": ["Perplexity"]},
        },
        "claude": {
            "url": "https://claude.ai/new",
            "aliases": ["anthropic", "entropic"],
            "modes": ["chat", "research", "artifacts"],
            "models": ["Auto", "Opus 4.7", "Sonnet 4.6", "Haiku"],
            "tools": ["Search", "Research", "Artifacts", "Computer use", "Claude Code"],
            "source_urls": ["https://support.claude.com/en/articles/11088861-using-research-on-claude"],
            "mode_markers": {
                "chat": ["Claude", "How can I help"],
                "research": ["Research", "Search", "Sources"],
                "artifacts": ["Artifacts", "Artifact", "Preview"],
            },
        },
        "grok": {
            "url": "https://grok.com/",
            "aliases": ["grog", "xai"],
            "modes": ["chat", "research"],
            "models": ["Auto", "Grok 4.20", "Grok 4.20 Reasoning", "Grok 4.1", "Grok 4.1 Thinking", "Grok 4.1 Fast Reasoning"],
            "tools": ["DeepSearch", "Think", "Search", "X realtime", "Agent Tools API", "Connectors"],
            "source_urls": ["https://x.ai/news/grok-4-1-fast", "https://docs.x.ai/developers/models/grok-4-1-fast-reasoning"],
            "mode_markers": {"research": ["Research", "DeepSearch", "Think"], "chat": ["Grok", "Ask anything"]},
        },
        "openrouter": {
            "url": "https://openrouter.ai/",
            "aliases": ["open-router"],
            "modes": ["chat", "models", "credits"],
            "models": ["Auto", "Claude", "GPT", "Gemini", "Grok", "DeepSeek", "Qwen"],
            "tools": ["Chat", "Models", "Credits", "API Keys", "Activity"],
            "source_urls": ["https://openrouter.ai/docs"],
            "mode_markers": {
                "chat": ["OpenRouter", "Chat"],
                "models": ["Models", "OpenRouter"],
                "credits": ["Credits", "Activity", "Usage"],
            },
        },
    }


def model_catalog() -> dict[str, dict[str, Any]]:
    return {
        provider_id: {
            "models": [str(model) for model in provider.get("models", [])],
            "tools": [str(tool) for tool in provider.get("tools", [])],
            "modes": [str(mode) for mode in provider.get("modes", [])],
            "url": str(provider.get("url", "")),
            "source_urls": [str(url) for url in provider.get("source_urls", [])],
        }
        for provider_id, provider in provider_registry().items()
    }


def backend_registry() -> dict[str, dict[str, Any]]:
    return {
        "playwright-cdp": {
            "scope": "local",
            "aliases": ["Playwright", "CDP", "persistent profile"],
            "description": "Deterministic local browser control through Chrome DevTools Protocol.",
        },
        "computer-use": {
            "scope": "local",
            "aliases": ["Codex Computer Use", "macOS UI automation"],
            "description": "Real visible UI control and screenshot evidence against installed apps.",
        },
        "peekaboo": {
            "scope": "local",
            "aliases": ["Peter Steinberger Peekaboo", "macOS screenshots", "MCP"],
            "description": "Optional macOS screenshot and UI evidence backend when installed.",
        },
        "oracle": {
            "scope": "local-or-api",
            "aliases": ["Peter Steinberger Oracle", "@steipete/oracle", "multi-model consult"],
            "description": (
                "Consult GPT/Gemini/Claude through Oracle API or browser sessions; useful for code review, "
                "long-run reattach, and session artifacts, not a replacement for local provider account audits."
            ),
        },
        "openai-cua": {
            "scope": "managed",
            "aliases": ["OpenAI Operator", "ChatGPT agent", "Computer-Using Agent"],
            "description": "OpenAI browser-use agent backend; useful as a comparison target, not a local profile replacement.",
        },
        "claude-computer-use": {
            "scope": "managed",
            "aliases": ["Anthropic Computer Use", "Claude Computer Use"],
            "description": "Claude's computer-use style backend for web/UI task execution.",
        },
        "gemini-computer-use": {
            "scope": "managed",
            "aliases": ["Gemini Computer Use", "Google browser agent"],
            "description": "Gemini-style computer-use backend for agentic browser tasks.",
        },
        "browser-use": {
            "scope": "local-or-managed",
            "aliases": ["browser-use", "Playwright agent"],
            "description": "Open-source Playwright-based browser agent framework.",
        },
        "stagehand": {
            "scope": "local-or-managed",
            "aliases": ["Stagehand", "Browserbase Stagehand"],
            "description": "Playwright-oriented natural-language browser automation.",
        },
        "hyperbrowser": {
            "scope": "managed",
            "aliases": ["Hyperbrowser", "cloud browser sessions"],
            "description": "Cloud browser sessions with Playwright, Browser-Use, Claude Computer Use, OpenAI CUA, and Gemini Computer Use adapters.",
        },
    }


def provider_probe_specs() -> dict[str, dict[str, Any]]:
    return {
        "chatgpt": {
            "account_hints": ["Account", "Settings", "My plan", "Plan", "Upgrade plan"],
            "model_hints": ["GPT", "Auto", "More models"],
            "tool_hints": ["Tools", "Deep research", "Agent", "Codex"],
            "usage_hints": ["limits", "usage", "remaining", "resets", "messages"],
        },
        "gemini": {
            "account_hints": ["Google Account", "Google AI", "Gemini Advanced", "Google One"],
            "model_hints": ["Gemini", "Pro", "Flash", "Deep Think"],
            "tool_hints": ["Tools", "Deep Research", "Agent", "Canvas"],
            "usage_hints": ["limit", "usage", "remaining", "resets", "quota"],
        },
        "claude": {
            "account_hints": ["Account", "Settings", "Plan", "Max plan", "Pro plan"],
            "model_hints": ["Opus", "Sonnet", "Haiku"],
            "tool_hints": ["Search", "Research", "Artifacts", "Create"],
            "usage_hints": ["weekly limit", "used", "remaining", "resets", "Guest pass"],
        },
        "perplexity": {
            "account_hints": ["Account", "Settings", "Pro", "Max"],
            "model_hints": ["Auto", "Sonar", "GPT", "Claude", "Gemini"],
            "tool_hints": ["Search", "Pro Search", "Research", "Deep Research", "Spaces"],
            "usage_hints": ["queries", "usage", "remaining", "left", "reset"],
        },
        "grok": {
            "account_hints": ["Account", "Settings", "Premium", "SuperGrok"],
            "model_hints": ["Grok", "Fast", "Think", "Reasoning"],
            "tool_hints": ["DeepSearch", "Think", "Search", "X"],
            "usage_hints": ["limit", "usage", "remaining", "resets", "quota"],
        },
        "openrouter": {
            "account_hints": ["Account", "Credits", "API Keys", "Activity"],
            "model_hints": ["Claude", "GPT", "Gemini", "Grok", "DeepSeek", "Qwen"],
            "tool_hints": ["Chat", "Models", "Credits", "Activity"],
            "usage_hints": ["credits", "usage", "spent", "remaining", "balance"],
        },
    }


def primary_feature_targets() -> list[dict[str, Any]]:
    return [
        {
            "provider": "chatgpt",
            "mode": "chat",
            "model": "GPT-5.5",
            "must_verify": ["login", "model-selector"],
            "notes": "Normal ChatGPT model picker and composer readiness.",
        },
        {
            "provider": "chatgpt",
            "mode": "deep-research",
            "model": "GPT-5.5 Pro",
            "must_verify": ["login", "deep-research-tool", "review-plan-or-start-research"],
            "notes": "Select Deep Research; do not spend quota unless explicitly confirmed.",
        },
        {
            "provider": "chatgpt",
            "mode": "agent",
            "model": "GPT-5.5 Pro",
            "must_verify": ["login", "agent-tool", "agent-review-or-take-control"],
            "notes": "Select ChatGPT Agent/Agent tool; verify availability before execution.",
        },
        {
            "provider": "gemini",
            "mode": "deep-research",
            "model": "Pro",
            "must_verify": ["login", "tools-menu", "deep-research-tool", "source-settings"],
            "notes": "Gemini Deep Research through Tools with Pro/Thinking mode when available.",
        },
        {
            "provider": "claude",
            "mode": "chat",
            "model": "Opus 4.7",
            "must_verify": ["login", "model-selector", "opus-selected", "usage-limit"],
            "notes": "Claude Opus availability and plan/usage banner.",
        },
    ]


def build_oracle_plan(
    *,
    prompt: str,
    files: list[str] | None = None,
    cdp_port: int | None = None,
    deep_research: bool = False,
    model_strategy: str = "current",
) -> dict[str, Any]:
    base = ["npx", "-y", "@steipete/oracle"]
    consult = [*base, "--dry-run", "summary", "--engine", "browser", "--browser-model-strategy", model_strategy]
    if cdp_port:
        consult.extend(["--browser-attach-running", "--remote-chrome", f"127.0.0.1:{cdp_port}"])
    if deep_research:
        consult.extend(["--browser-research", "deep"])
    consult.extend(["-p", prompt])
    for file_pattern in files or []:
        consult.extend(["--file", file_pattern])
    return {
        "purpose": "Use Oracle for multi-model/code consults and ChatGPT browser-session artifacts; keep account audits in ai_research_browser.",
        "consult_dry_run": consult,
        "status": [*base, "status", "--hours", "72", "--browser-tabs"],
        "show_session": [*base, "session", "<session-id>", "--render"],
        "notes": [
            "Use --dry-run summary first on shared desktops.",
            "Use --browser-attach-running with a real CDP-enabled signed-in browser.",
            "Use session/status to fetch/show long-running Oracle browser results instead of starting duplicates.",
        ],
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def profile_account_state(browser_id: str, prefs: dict[str, Any], data: dict[str, Any]) -> str:
    if data.get("user_name") or data.get("gaia_name"):
        return "visible"
    account_info = prefs.get("account_info")
    if isinstance(account_info, list) and any(account.get("email") for account in account_info if isinstance(account, dict)):
        return "visible"
    sync = prefs.get("sync", {})
    if isinstance(sync, dict) and (sync.get("gaia_id") or sync.get("transport_data_per_account")):
        return "signed-in-hidden"
    if browser_id == "opera":
        serialized = json.dumps(prefs, ensure_ascii=False)
        if "anonymous_hidden_account" in serialized or "opera_account" in serialized:
            return "signed-in-hidden"
    return "unknown"


def profile_display_name(browser_id: str, directory: str, data: dict[str, Any], prefs: dict[str, Any]) -> str:
    display_name = data.get("name") or prefs.get("profile", {}).get("name") or directory
    if browser_id == "opera" and display_name == "Default":
        return "Opera Default"
    return str(display_name)


def discover_profiles(user_data_dir: str | Path, *, browser_id: str = "") -> list[dict[str, str]]:
    root = Path(user_data_dir).expanduser()
    local_state = read_json(root / "Local State")
    info_cache = local_state.get("profile", {}).get("info_cache", {})
    profiles: list[dict[str, str]] = []
    for directory in sorted(info_cache.keys(), key=lambda d: (d != "Default", d)):
        data = info_cache.get(directory, {}) or {}
        profile_dir = root / directory
        prefs = read_json(profile_dir / "Preferences")
        account = (
            data.get("user_name")
            or data.get("gaia_name")
            or ((prefs.get("account_info") or [{}])[0].get("email") if isinstance(prefs.get("account_info"), list) else "")
            or ""
        )
        display_name = profile_display_name(browser_id, directory, data, prefs)
        profiles.append(
            {
                "directory": directory,
                "name": display_name,
                "account": str(account),
                "account_state": profile_account_state(browser_id, prefs, data),
                "path": str(profile_dir),
            }
        )
    if not profiles:
        for child in sorted(root.iterdir() if root.exists() else []):
            if child.is_dir() and (child / "Preferences").exists():
                prefs = read_json(child / "Preferences")
                profiles.append(
                    {
                        "directory": child.name,
                        "name": profile_display_name(browser_id, child.name, {}, prefs),
                        "account": str(((prefs.get("account_info") or [{}])[0].get("email") if isinstance(prefs.get("account_info"), list) else "") or ""),
                        "account_state": profile_account_state(browser_id, prefs, {}),
                        "path": str(child),
                    }
                )
    return profiles


def resolve_profile(profiles: list[dict[str, str]], requested: str) -> dict[str, str]:
    needle = requested.strip().lower()
    for profile in profiles:
        candidates = [
            profile.get("directory", ""),
            profile.get("name", ""),
            profile.get("account", ""),
        ]
        if any(needle == c.lower() for c in candidates if c):
            return profile
    if needle == "work":
        for profile in profiles:
            haystack = " ".join([profile.get("directory", ""), profile.get("name", ""), profile.get("account", "")]).lower()
            if "work" in haystack or "arbeit" in haystack:
                return profile
    raise ValueError(f"profile not found: {requested}")


def normalize_browser_name(name: str) -> str:
    lowered = name.lower()
    for key, cfg in BROWSER_CANDIDATES.items():
        if lowered == key or lowered in cfg.get("aliases", []):
            return key
    return lowered


def browser_install_state(cfg: dict[str, Any]) -> dict[str, bool]:
    app_path = Path(str(cfg["app_path"])).expanduser()
    user_data_dir = Path(str(cfg["user_data_dir"])).expanduser()
    binary_path = app_path / str(cfg["binary_rel"])
    return {
        "app_exists": app_path.exists(),
        "binary_exists": binary_path.exists(),
        "user_data_exists": user_data_dir.exists(),
    }


def discover_browsers() -> list[dict[str, Any]]:
    out = []
    for key, cfg in BROWSER_CANDIDATES.items():
        app_path = Path(str(cfg["app_path"])).expanduser()
        user_data_dir = Path(str(cfg["user_data_dir"])).expanduser()
        install_state = browser_install_state(cfg)
        if not install_state["app_exists"] and not install_state["user_data_exists"]:
            continue
        profiles = discover_profiles(user_data_dir, browser_id=key)
        out.append(
            {
                "id": key,
                "display_name": cfg["display_name"],
                "app_path": str(app_path),
                "binary_path": str(app_path / str(cfg["binary_rel"])),
                "user_data_dir": str(user_data_dir),
                "default_port": cfg["default_port"],
                "profiles": profiles,
                **install_state,
            }
        )
    return out


def provider_url(provider: str) -> str:
    providers = provider_registry()
    provider = normalize_provider_name(provider)
    if provider not in providers:
        raise ValueError(f"unknown provider: {provider}")
    return str(providers[provider]["url"])


def normalize_provider_name(name: str) -> str:
    lowered = name.lower()
    for key, cfg in provider_registry().items():
        if lowered == key or lowered in cfg.get("aliases", []):
            return key
    return lowered


def provider_cli_choices() -> list[str]:
    choices: list[str] = []
    for key, cfg in provider_registry().items():
        choices.append(key)
        choices.extend(str(alias) for alias in cfg.get("aliases", []))
    return sorted(set(choices))


def build_launch_args(
    browser: dict[str, Any],
    *,
    profile_directory: str,
    port: int,
    provider: str,
    mode: str,
    headless: bool,
) -> list[str]:
    binary = browser.get("binary_path") or str(Path(browser["app_path"]) / "Contents/MacOS" / browser.get("display_name", ""))
    args = [
        str(binary),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={browser['user_data_dir']}",
        f"--profile-directory={profile_directory}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
    ]
    if headless:
        args.append("--headless=new")
    args.append(provider_url(provider))
    return args


def build_launch_plan(
    browser: dict[str, Any],
    *,
    profile_directory: str,
    port: int,
    provider: str,
    mode: str,
    model: str,
    headless: bool,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    return {
        "browser": browser.get("id", ""),
        "profile_directory": profile_directory,
        "provider": provider_id,
        "mode": mode,
        "model": model or "Auto",
        "model_selection": "select-in-provider-ui",
        "launch_args": build_launch_args(
            browser,
            profile_directory=profile_directory,
            port=port,
            provider=provider_id,
            mode=mode,
            headless=headless,
        ),
    }


def build_background_launch_plan(
    browser: dict[str, Any],
    *,
    profile_directory: str,
    port: int,
    provider: str,
    mode: str,
    model: str,
    headless: bool,
) -> dict[str, Any]:
    base_plan = build_launch_plan(
        browser,
        profile_directory=profile_directory,
        port=port,
        provider=provider,
        mode=mode,
        model=model,
        headless=headless,
    )
    app_path = str(browser.get("app_path", ""))
    display_name = str(browser.get("display_name") or browser.get("id") or "")
    launch_args = list(base_plan["launch_args"])
    browser_args = launch_args[1:] if launch_args else []
    launch_command = ["/usr/bin/open", "-g", "-j", "-n", "-a", app_path, "--args", *browser_args]
    return {
        **base_plan,
        "strategy": "macos-open-hidden",
        "visibility": "headless" if headless else "hidden",
        "port": port,
        "browser_display_name": display_name,
        "launch_command": launch_command,
        "post_launch_hide_command": ["osascript", "-e", f'tell application "{display_name}" to set visible to false'],
        "notes": [
            "Uses macOS open -g -j to avoid activation and launch hidden.",
            "Keeps model selection as a UI-verification step because providers do not expose stable model URL parameters.",
        ],
    }


def launchable_browser(browser: dict[str, Any]) -> tuple[bool, str]:
    if browser.get("binary_exists") is False:
        return False, "browser binary is not installed"
    if browser.get("app_exists") is False:
        return False, "browser app is not installed"
    if not browser.get("profiles"):
        return False, "no profiles discovered"
    return True, ""


def build_background_all_plan(
    browsers: list[dict[str, Any]],
    *,
    provider: str,
    mode: str,
    model: str,
    headless: bool,
    port_offset: int = 100,
    all_profiles: bool = False,
) -> dict[str, Any]:
    launches: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for browser in browsers:
        can_launch, reason = launchable_browser(browser)
        if not can_launch:
            skipped.append({"browser": str(browser.get("id", "")), "reason": reason})
            continue
        profiles = browser.get("profiles", [])
        selected_profiles = profiles if all_profiles else profiles[:1]
        for profile in selected_profiles:
            port = int(browser.get("default_port", 0)) + port_offset + len(launches)
            plan = build_background_launch_plan(
                browser,
                profile_directory=str(profile.get("directory", "Default")),
                port=port,
                provider=provider,
                mode=mode,
                model=model,
                headless=headless,
            )
            launches.append({**plan, "profile": profile})
    return {
        "provider": normalize_provider_name(provider),
        "mode": mode,
        "model": model or "Auto",
        "visibility": "headless" if headless else "hidden",
        "launches": launches,
        "skipped": skipped,
    }


def execute_background_launch(plan: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"started": False, "dry_run": True, "pid": None}
    command = [str(part) for part in plan["launch_command"]]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    hide_command = plan.get("post_launch_hide_command") or []
    if hide_command:
        subprocess.run([str(part) for part in hide_command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"started": True, "dry_run": False, "pid": process.pid}


def parse_visible_status(text: str) -> dict[str, Any]:
    text = text or ""
    account_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    model_match = re.search(r"Model:\s*([^\n]+)", text, flags=re.I)
    if not model_match:
        model_match = re.search(
            r"\b((?:GPT[- ][^\n]+|Claude[ \t]+[^\n]+|Opus[ \t]+[^\n]+|Sonnet[ \t]+[^\n]+|Gemini[ \t]+[^\n]+|Grok[ \t]+[^\n]+))",
            text,
            flags=re.I,
        )
    plan_match = re.search(
        r"\b(ChatGPT\s+|Claude\s+|Google\s+AI\s+|Google\s+One\s+AI\s+|Gemini\s+|Perplexity\s+|X\s+)?"
        r"(Free|Plus|Pro|Team|Enterprise|Max|Advanced|Ultra|SuperGrok|Premium\+?|Premium)\s+"
        r"(?:plan|subscription|abo|tier)\b",
        text,
        flags=re.I,
    )
    if not plan_match:
        plan_match = re.search(
            r"\b(Gemini Advanced|Google AI Pro|Google AI Ultra|Google One AI Pro|Google One AI Ultra|"
            r"Perplexity Pro|Perplexity Max|ChatGPT Pro|ChatGPT Plus|Claude Pro|Claude Max|"
            r"SuperGrok|X Premium\+?|Premium\+)\b",
            text,
            flags=re.I,
        )
    used_percent_match = re.search(r"(?:used|verwendet|genutzt)\D{0,20}(\d{1,3})\s*%", text, flags=re.I)
    if not used_percent_match:
        used_percent_match = re.search(r"(\d{1,3})\s*%\s*(?:used|verwendet|genutzt)", text, flags=re.I)
    remaining_percent_match = re.search(r"(\d{1,3})\s*%\s*(?:remaining|left|übrig|verbleibend)", text, flags=re.I)
    count_match = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:left|remaining|übrig|verbleibend)", text, flags=re.I)
    reset_match = re.search(r"(?:resets?|reset|erneuert|setzt zurück)\s+([^\n.]+)", text, flags=re.I)
    deep_match = re.search(r"(?:Deep research|Rechercheberichte?|Research)\D{0,40}(\d+)\s*(?:remaining|left|übrig|verbleibend)?", text, flags=re.I)
    agent_match = re.search(r"(?:Agent tasks?|Agent)\D{0,40}(\d+)\s*(?:remaining|left|übrig|verbleibend)?", text, flags=re.I)
    raw_plan = plan_match.group(2 if plan_match.lastindex and plan_match.lastindex >= 2 else 1).strip() if plan_match else ""
    plan = raw_plan
    for prefix in ["ChatGPT ", "Gemini ", "Perplexity ", "Claude ", "Google AI ", "Google One AI ", "X "]:
        plan = plan.replace(prefix, "")
    return {
        "account": account_match.group(0) if account_match else "",
        "model": model_match.group(1).strip() if model_match else "",
        "plan": plan,
        "quotas": {
            "deep_research_remaining": int(deep_match.group(1)) if deep_match else None,
            "agent_remaining": int(agent_match.group(1)) if agent_match else None,
        },
        "usage": {
            "used_percent": int(used_percent_match.group(1)) if used_percent_match else None,
            "remaining_percent": int(remaining_percent_match.group(1)) if remaining_percent_match else None,
            "remaining_count": int(count_match.group(1)) if count_match else None,
            "remaining_total": int(count_match.group(2)) if count_match else None,
            "reset": reset_match.group(1).strip() if reset_match else "",
        },
    }


def expected_markers(provider: str, mode: str) -> list[str]:
    providers = provider_registry()
    provider = normalize_provider_name(provider)
    if provider not in providers:
        raise ValueError(f"unknown provider: {provider}")
    markers = providers[provider].get("mode_markers", {}).get(mode)
    if not markers:
        raise ValueError(f"unknown mode for {provider}: {mode}")
    return [str(marker) for marker in markers]


def verify_visible_text(text: str, *, provider: str, mode: str) -> dict[str, Any]:
    haystack = (text or "").casefold()
    markers = expected_markers(provider, mode)
    matched = [marker for marker in markers if marker.casefold() in haystack]
    return {
        "provider": provider,
        "mode": mode,
        "detected": bool(matched),
        "matched_markers": matched,
        "expected_markers": markers,
        "visible_status": parse_visible_status(text or ""),
    }


def normalized_contains(text: str, needle: str) -> bool:
    return re.sub(r"\s+", " ", needle.casefold()).strip() in re.sub(r"\s+", " ", text.casefold())


def extract_usage_lines(text: str) -> list[str]:
    patterns = re.compile(
        r"(plan|subscription|abo|tier|limit|quota|usage|remaining|left|used|reset|resets|"
        r"verbleibend|übrig|genutzt|erneuert|weekly|daily|messages|queries|research|agent)",
        flags=re.I,
    )
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line and patterns.search(line):
            lines.append(line)
    return lines[:80]


def infer_login_state(text: str, provider: str) -> str:
    lowered = (text or "").casefold()
    signed_out = [
        "sign in",
        "log in",
        "login",
        "anmelden",
        "registrieren",
        "create account",
        "just a moment",
        "checking if the site connection is secure",
        "verify you are human",
        "enable javascript and cookies",
        "cloudflare",
    ]
    if any(marker in lowered for marker in signed_out):
        return "signed-out-or-wall"
    provider_markers = provider_registry().get(normalize_provider_name(provider), {}).get("mode_markers", {})
    flattened = [marker for markers in provider_markers.values() for marker in markers]
    if any(str(marker).casefold() in lowered for marker in flattened):
        return "signed-in-or-ready"
    if parse_visible_status(text).get("account") or parse_visible_status(text).get("plan"):
        return "signed-in-or-ready"
    return "unknown"


def extract_provider_inventory(provider: str, text: str) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    catalog = model_catalog().get(provider_id, {"models": [], "tools": [], "modes": []})
    specs = provider_probe_specs().get(provider_id, {})
    visible_status = parse_visible_status(text or "")
    models = [
        model
        for model in catalog.get("models", [])
        if model != "Auto" and normalized_contains(text or "", str(model))
    ]
    tools = [
        tool
        for tool in catalog.get("tools", [])
        if normalized_contains(text or "", str(tool))
    ]
    modes = {}
    for mode in provider_registry().get(provider_id, {}).get("modes", []):
        try:
            modes[mode] = verify_visible_text(text or "", provider=provider_id, mode=str(mode))["detected"]
        except ValueError:
            modes[mode] = False
    matched_hints = {
        key: [hint for hint in values if normalized_contains(text or "", str(hint))]
        for key, values in specs.items()
    }
    return {
        "provider": provider_id,
        "login_state": infer_login_state(text or "", provider_id),
        "visible_status": visible_status,
        "available_models": models,
        "available_tools": tools,
        "available_modes": modes,
        "matched_hints": matched_hints,
        "usage_lines": extract_usage_lines(text or ""),
    }


def run_agent_browser(args: list[str], *, session: str = "", timeout: float = 45.0) -> subprocess.CompletedProcess[str]:
    command = ["agent-browser"]
    if session:
        command.extend(["--session", session])
    command.extend(args)
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")) + f"\nTimed out after {timeout:.0f}s",
        )


def agent_browser_probe(
    *,
    cdp_port: int,
    provider: str,
    mode: str,
    artifact_root: Path,
    browser: str,
    profile: str,
    session: str = "",
    open_controls: bool = False,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    paths = build_artifact_paths(artifact_root, provider=provider_id, mode=mode, browser=browser, profile=profile)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    screenshot = paths["screenshot_png"]
    commands: list[dict[str, Any]] = []

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session)
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--cdp", str(cdp_port), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    invoke("open", ["open", provider_url(provider_id)])
    invoke("wait", ["wait", "3000"])
    snapshot = invoke("snapshot-interactive", ["snapshot", "-i", "-c"])
    visible_text = snapshot.stdout
    if open_controls:
        for label in provider_probe_specs().get(provider_id, {}).get("model_hints", [])[:3]:
            invoke(f"try-open-control:{label}", ["find", "text", str(label), "click"])
            control_snapshot = invoke(f"snapshot-after:{label}", ["snapshot", "-i", "-c"])
            if control_snapshot.stdout:
                visible_text += "\n" + control_snapshot.stdout
    screenshot_result = invoke("screenshot", ["screenshot", str(screenshot)])

    inventory = extract_provider_inventory(provider_id, visible_text)
    evidence_status = "captured" if visible_text else "failed"
    if visible_text and screenshot_result.returncode != 0:
        evidence_status = "captured-without-screenshot"
    payload = {
        "provider": provider_id,
        "mode": mode,
        "browser": normalize_browser_name(browser),
        "profile": profile,
        "status": evidence_status,
        "cdp_port": cdp_port,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "inventory": inventory,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    return {**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, int(port))) == 0


def endpoint_version(port: int, host: str = "127.0.0.1") -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=1.5) as response:
            return json.load(response)
    except Exception:
        return None


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def port_owner(port: int) -> str:
    result = run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    if result.returncode != 0:
        return ""
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[1].split()[0] if len(lines) > 1 else ""


def process_args_for_browser(display_name: str) -> str:
    result = run(["ps", "-ww", "-axo", "args="])
    if result.returncode != 0:
        return ""
    app_fragment = f"/Applications/{display_name}.app/"
    return "\n".join(
        line
        for line in result.stdout.splitlines()
        if app_fragment in line and "Contents/MacOS" in line and " Helper" not in line
    )


def detect_launch_blockers(
    *,
    browser_name: str,
    port: int,
    port_owner: str,
    process_args: str,
) -> list[str]:
    blockers = []
    if port_owner:
        blockers.append(f"port {port} is already used by {port_owner}")
    non_cdp_processes = [line for line in process_args.splitlines() if line.strip() and "--remote-debugging-port" not in line]
    if non_cdp_processes:
        blockers.append(f"{browser_name} is already running without --remote-debugging-port")
    return blockers


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "run"


def default_chat_cache_root() -> Path:
    return Path(os.environ.get("AI_RESEARCH_BROWSER_CACHE", "~/.cache/ai-research-browser/chats")).expanduser()


def build_artifact_paths(root: Path, *, provider: str, mode: str, browser: str, profile: str) -> dict[str, Path]:
    run_dir = root / f"{slug(provider)}-{slug(mode)}-{slug(browser)}-{slug(profile)}"
    return {
        "run_dir": run_dir,
        "status_json": run_dir / "status.json",
        "screenshot_png": run_dir / "screenshot.png",
    }


def chat_cache_key(*, browser: str, profile: str, provider: str, chat_url: str) -> str:
    browser_id = normalize_browser_name(browser)
    provider_id = normalize_provider_name(provider)
    digest = hashlib.sha256(f"{browser_id}\0{profile}\0{provider_id}\0{chat_url}".encode("utf-8")).hexdigest()[:16]
    return f"{slug(browser_id)}-{slug(profile)}-{slug(provider_id)}-{digest}"


def chat_record_paths(cache_root: Path, key: str) -> dict[str, Path]:
    record_dir = cache_root.expanduser() / key
    return {
        "record_dir": record_dir,
        "metadata_path": record_dir / "metadata.json",
        "text_path": record_dir / "chat.txt",
        "index_path": cache_root.expanduser() / "index.json",
    }


def read_chat_index(cache_root: Path) -> dict[str, Any]:
    index_path = cache_root.expanduser() / "index.json"
    if not index_path.exists():
        return {"chats": []}
    data = read_json(index_path)
    if not isinstance(data.get("chats"), list):
        return {"chats": []}
    return data


def write_chat_index(cache_root: Path, record: dict[str, Any]) -> None:
    index = read_chat_index(cache_root)
    chats = [chat for chat in index["chats"] if chat.get("key") != record.get("key")]
    chats.append(record)
    chats.sort(key=lambda chat: str(chat.get("updated_at", "")), reverse=True)
    write_json(cache_root.expanduser() / "index.json", {"chats": chats})


def save_chat_record(
    *,
    cache_root: Path,
    browser: str,
    profile: str,
    provider: str,
    chat_url: str,
    title: str,
    text: str,
    source: str,
    refresh: bool,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    browser_id = normalize_browser_name(browser)
    key = chat_cache_key(browser=browser_id, profile=profile, provider=provider_id, chat_url=chat_url)
    paths = chat_record_paths(cache_root, key)
    cache_hit = paths["metadata_path"].exists() and not refresh
    if cache_hit:
        metadata = read_json(paths["metadata_path"])
        return {**paths, "key": key, "metadata": metadata, "cache_hit": True}

    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    paths["record_dir"].mkdir(parents=True, exist_ok=True)
    paths["text_path"].write_text(text, encoding="utf-8")
    metadata = {
        "key": key,
        "browser": browser_id,
        "profile": profile,
        "provider": provider_id,
        "chat_url": chat_url,
        "title": title or chat_url,
        "source": source,
        "text_path": str(paths["text_path"]),
        "created_at": now,
        "updated_at": now,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_bytes": len(text.encode("utf-8")),
    }
    write_json(paths["metadata_path"], metadata)
    write_chat_index(cache_root, metadata)
    return {**paths, "key": key, "metadata": metadata, "cache_hit": False}


def list_chat_records(cache_root: Path, *, provider: str = "", browser: str = "", profile: str = "") -> list[dict[str, Any]]:
    records = read_chat_index(cache_root)["chats"]
    provider_id = normalize_provider_name(provider) if provider else ""
    browser_id = normalize_browser_name(browser) if browser else ""
    out = []
    for record in records:
        if provider_id and record.get("provider") != provider_id:
            continue
        if browser_id and record.get("browser") != browser_id:
            continue
        if profile and record.get("profile") != profile:
            continue
        out.append(record)
    return out


def parse_chat_listing(text: str, *, provider: str) -> list[dict[str, str]]:
    skip = {
        "recents",
        "chats",
        "projects",
        "more",
        "new chat",
        "search chats",
        "chat history",
        "gemini",
    }
    chats: list[dict[str, str]] = []
    for line in (text or "").splitlines():
        title = line.strip()
        if not title or title.lower() in skip:
            continue
        chats.append({"provider": normalize_provider_name(provider), "title": title})
    return chats


def build_test_matrix(
    browsers: list[dict[str, Any]],
    providers: dict[str, dict[str, Any]] | None = None,
    *,
    account_status: dict[tuple[str, str, str], dict[str, Any]] | None = None,
    backend: str = "manual",
) -> list[dict[str, Any]]:
    provider_map = providers or provider_registry()
    account_status = account_status or {}
    rows: list[dict[str, Any]] = []
    for browser in browsers:
        profiles = browser.get("profiles") or [{"directory": "", "name": "", "account": ""}]
        for profile in profiles:
            for provider_id, provider in provider_map.items():
                status_key = (str(browser.get("id", "")), str(profile.get("directory", "")), provider_id)
                for mode in provider.get("modes", []):
                    rows.append(
                        {
                            "browser": browser.get("id", ""),
                            "browser_name": browser.get("display_name", ""),
                            "profile_directory": profile.get("directory", ""),
                            "profile_name": profile.get("name", ""),
                            "profile_account": profile.get("account", ""),
                            "provider": provider_id,
                            "feature": mode,
                            "provider_url": provider.get("url", ""),
                            "backend": backend,
                            "account_status": account_status.get(status_key, {}),
                            "status": "untested",
                        }
                    )
    return rows


def build_primary_feature_suite(
    browsers: list[dict[str, Any]],
    *,
    providers: list[str] | None = None,
    include_all_features: bool = False,
    backend: str = "agent-browser",
) -> list[dict[str, Any]]:
    provider_filter = {normalize_provider_name(provider) for provider in providers or []}
    targets: list[dict[str, Any]] = []
    if include_all_features:
        for provider_id, provider in provider_registry().items():
            if provider_filter and provider_id not in provider_filter:
                continue
            for mode in provider.get("modes", []):
                targets.append(
                    {
                        "provider": provider_id,
                        "mode": str(mode),
                        "model": str((provider.get("models") or ["Auto"])[0]),
                        "must_verify": ["login", "mode-marker"],
                        "notes": "Full provider registry feature target.",
                    }
                )
    else:
        targets = [
            target
            for target in primary_feature_targets()
            if not provider_filter or target["provider"] in provider_filter
        ]

    rows: list[dict[str, Any]] = []
    for browser in browsers:
        profiles = browser.get("profiles") or []
        for profile in profiles:
            for target in targets:
                session_evidence = provider_session_evidence(profile, str(target["provider"]))
                rows.append(
                    {
                        "browser": browser.get("id", ""),
                        "browser_name": browser.get("display_name", ""),
                        "profile_directory": profile.get("directory", ""),
                        "profile_name": profile.get("name", ""),
                        "profile_account": profile.get("account", ""),
                        "profile_account_state": profile.get("account_state", ""),
                        "provider": target["provider"],
                        "feature": target["mode"],
                        "model": target["model"],
                        "provider_url": provider_url(str(target["provider"])),
                        "backend": backend,
                        "must_verify": target["must_verify"],
                        "notes": target["notes"],
                        "session_evidence": session_evidence,
                        "status": "queued" if session_evidence.get("confidence") != "none" else "needs-login",
                    }
                )
    return rows


PROFILE_CLONE_EXCLUDES = {
    "Singleton*",
    "Lock",
    "lockfile",
    "Crashpad",
    "Code Cache",
    "DawnCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "GPUCache",
    "ShaderCache",
    "Cache",
    "Media Cache",
    "Service Worker/CacheStorage",
    "IndexedDB/*.blob",
}


def should_exclude_profile_path(path: Path) -> bool:
    parts = set(path.parts)
    name = path.name
    if name.startswith("Singleton"):
        return True
    if name in {"Lock", "lockfile"}:
        return True
    if any(part in {"Crashpad", "Code Cache", "DawnCache", "GrShaderCache", "GraphiteDawnCache", "GPUCache", "ShaderCache", "Cache", "Media Cache"} for part in parts):
        return True
    if "Service Worker" in parts and "CacheStorage" in parts:
        return True
    if path.suffix == ".blob" and "IndexedDB" in parts:
        return True
    return False


def copy_profile_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        relative = item.relative_to(src)
        target = dst / relative
        if should_exclude_profile_path(relative):
            continue
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, target)
        except OSError:
            continue


def clone_browser_profile_for_agent_browser(
    browser: dict[str, Any],
    profile: dict[str, str],
    clone_root: Path,
    *,
    run_slug: str,
) -> dict[str, Any]:
    source_user_data = Path(str(browser.get("user_data_dir", ""))).expanduser()
    profile_directory = str(profile.get("directory", "Default"))
    source_profile = source_user_data / profile_directory
    clone_user_data = clone_root.expanduser() / run_slug / "user-data"
    clone_profile = clone_user_data / profile_directory
    if not source_profile.exists():
        return {
            "ok": False,
            "error": f"profile source does not exist: {source_profile}",
            "clone_user_data": str(clone_user_data),
            "clone_profile": str(clone_profile),
        }
    clone_user_data.mkdir(parents=True, exist_ok=True)
    copy_profile_tree(source_profile, clone_profile)
    for filename in ["Local State", "First Run"]:
        source_file = source_user_data / filename
        if source_file.exists():
            try:
                shutil.copy2(source_file, clone_user_data / filename)
            except OSError:
                pass
    return {
        "ok": True,
        "source_profile": str(source_profile),
        "clone_user_data": str(clone_user_data),
        "clone_profile": str(clone_profile),
        "profile_directory": profile_directory,
    }


def agent_browser_profile_global_args(browser: dict[str, Any], clone_user_data: str, profile_directory: str) -> list[str]:
    return [
        "--profile",
        clone_user_data,
        "--executable-path",
        str(browser.get("binary_path", "")),
        "--args",
        f"--profile-directory={profile_directory},--no-first-run,--no-default-browser-check",
    ]


def agent_browser_profile_probe(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    mode: str,
    model: str,
    artifact_root: Path,
    clone_root: Path,
    open_controls: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    profile_directory = str(profile.get("directory", "Default"))
    run_name = f"{browser_id}-{slug(profile_directory)}-{provider_id}-{slug(mode)}"
    paths = build_artifact_paths(artifact_root.expanduser(), provider=provider_id, mode=mode, browser=browser_id, profile=profile_directory)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    clone = clone_browser_profile_for_agent_browser(browser, profile, clone_root, run_slug=run_name)
    if not clone.get("ok"):
        payload = {
            "provider": provider_id,
            "mode": mode,
            "model": model,
            "browser": browser_id,
            "profile": profile_directory,
            "status": "blocked",
            "blocker": clone.get("error", "profile clone failed"),
            "clone": clone,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    session = f"ai-{run_name}"
    global_args = agent_browser_profile_global_args(browser, str(clone["clone_user_data"]), profile_directory)

    def invoke(label: str, extra_args: list[str], *, use_globals: bool = False) -> subprocess.CompletedProcess[str]:
        result = run_agent_browser([*(global_args if use_globals else []), *extra_args], session=session, timeout=timeout)
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--session", session, *(global_args if use_globals else []), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    visible_text = ""
    open_result = invoke("open", ["open", provider_url(provider_id)], use_globals=True)
    if open_result.stdout:
        visible_text += open_result.stdout
    invoke("wait", ["wait", "3000"])
    snapshot = invoke("snapshot-interactive", ["snapshot", "-i", "-c"])
    visible_text += "\n" + snapshot.stdout
    if open_controls:
        hints = provider_probe_specs().get(provider_id, {})
        for label in [*hints.get("model_hints", [])[:2], *hints.get("tool_hints", [])[:2]]:
            invoke(f"try-open-control:{label}", ["find", "text", str(label), "click"])
            control_snapshot = invoke(f"snapshot-after:{label}", ["snapshot", "-i", "-c"])
            visible_text += "\n" + control_snapshot.stdout
    screenshot = paths["screenshot_png"]
    screenshot_result = invoke("screenshot", ["screenshot", str(screenshot)])
    invoke("close", ["close"])

    inventory = extract_provider_inventory(provider_id, visible_text)
    login_state = inventory.get("login_state", "unknown")
    status = "captured"
    if any(command.get("returncode") == 124 for command in commands):
        status = "timeout"
    elif open_result.returncode != 0 or snapshot.returncode != 0:
        status = "failed"
    elif login_state == "signed-out-or-wall":
        status = "signed-out-or-wall"
    payload = {
        "provider": provider_id,
        "mode": mode,
        "model": model,
        "browser": browser_id,
        "profile": profile_directory,
        "status": status,
        "session": session,
        "clone": clone,
        "screenshot": str(screenshot) if screenshot.exists() and screenshot_result.returncode == 0 else "",
        "inventory": inventory,
        "verification": verify_visible_text(visible_text, provider=provider_id, mode=mode) if visible_text else None,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    return {**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}


def requested_provider_ids(raw: str = "") -> list[str]:
    providers = provider_registry()
    if not raw:
        return list(providers.keys())
    ids = []
    for item in raw.split(","):
        provider_id = normalize_provider_name(item.strip())
        if provider_id and provider_id not in ids:
            if provider_id not in providers:
                raise ValueError(f"unknown provider: {item}")
            ids.append(provider_id)
    return ids


def account_audit_text_path(text_dir: Path, *, browser: str, profile: str, provider: str) -> Path:
    return text_dir.expanduser() / f"{slug(normalize_browser_name(browser))}-{slug(profile)}-{slug(normalize_provider_name(provider))}.txt"


def provider_session_domains(provider: str) -> list[str]:
    return {
        "chatgpt": ["chatgpt.com", "openai.com", "auth.openai.com"],
        "gemini": ["gemini.google.com", "google.com", "accounts.google.com"],
        "claude": ["claude.ai", "anthropic.com"],
        "perplexity": ["perplexity.ai"],
        "grok": ["grok.com", "x.com", "x.ai"],
        "openrouter": ["openrouter.ai", "clerk.openrouter.ai"],
    }.get(normalize_provider_name(provider), [])


def provider_session_cookie_names(provider: str) -> list[str]:
    return {
        "chatgpt": ["session", "__Secure-next-auth.session-token", "oai-client-auth-session", "unified_session_manifest", "_puid"],
        "gemini": ["SAPISID", "APISID", "HSID", "OSID", "__Secure-OSID", "COMPASS"],
        "claude": ["sessionKey", "lastActiveOrg", "intercom-session", "__ssid"],
        "perplexity": ["__Secure-next-auth.session-token", "pplx", "g_state", "intercom-session"],
        "grok": ["sso", "sso-rw", "x-userid", "auth_token", "twid"],
        "openrouter": ["__session", "__refresh", "__client", "__client_uat"],
    }.get(normalize_provider_name(provider), [])


def profile_storage_roots(profile: dict[str, str]) -> list[Path]:
    root = Path(profile.get("path", "")).expanduser()
    if not root:
        return []
    roots = [root]
    nested_default = root / "Default"
    if nested_default.exists():
        roots.append(nested_default)
    return roots


def cookie_db_paths(profile: dict[str, str]) -> list[Path]:
    paths: list[Path] = []
    for root in profile_storage_roots(profile):
        for candidate in [root / "Cookies", root / "Network" / "Cookies"]:
            if candidate.exists():
                paths.append(candidate)
    return paths


def indexeddb_origin_dirs(profile: dict[str, str], domains: list[str]) -> list[str]:
    origins: list[str] = []
    for root in profile_storage_roots(profile):
        indexeddb = root / "IndexedDB"
        if not indexeddb.exists():
            continue
        for child in indexeddb.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if any(domain in name for domain in domains):
                origins.append(name)
    return sorted(set(origins))


def provider_session_evidence(profile: dict[str, str], provider: str) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    domains = provider_session_domains(provider_id)
    interesting_cookie_names = provider_session_cookie_names(provider_id)
    matched_hosts: set[str] = set()
    matched_cookie_names: set[str] = set()
    session_cookie_names: set[str] = set()
    cookie_db_count = 0

    for source in cookie_db_paths(profile):
        cookie_db_count += 1
        try:
            tmpdir = Path(tempfile.mkdtemp(prefix="ai-research-cookie-scan-"))
            tmp = tmpdir / "Cookies"
            shutil.copy2(source, tmp)
            con = sqlite3.connect(tmp)
            try:
                rows = con.execute(
                    "select host_key, name from cookies where " + " or ".join(["host_key like ?" for _ in domains]),
                    [f"%{domain}%" for domain in domains],
                ).fetchall()
            finally:
                con.close()
        except Exception:
            continue
        for host, name in rows:
            matched_hosts.add(str(host))
            matched_cookie_names.add(str(name))
            if any(str(name).startswith(prefix) or prefix in str(name) for prefix in interesting_cookie_names):
                session_cookie_names.add(str(name))

    origins = indexeddb_origin_dirs(profile, domains)
    confidence = "none"
    if session_cookie_names:
        confidence = "likely-logged-in"
    elif matched_cookie_names or origins:
        confidence = "site-data-present"
    return {
        "provider": provider_id,
        "confidence": confidence,
        "cookie_db_count": cookie_db_count,
        "matched_hosts": sorted(matched_hosts),
        "matched_cookie_names": sorted(matched_cookie_names)[:40],
        "session_cookie_names": sorted(session_cookie_names)[:20],
        "indexeddb_origins": origins[:40],
        "note": "Cookie values are intentionally not read or emitted.",
    }


def build_account_audit_matrix(
    browsers: list[dict[str, Any]],
    providers: dict[str, dict[str, Any]] | None = None,
    *,
    text_dir: Path | None = None,
    headless: bool = False,
    port_offset: int = 200,
) -> dict[str, Any]:
    provider_map = providers or provider_registry()
    rows: list[dict[str, Any]] = []
    for browser in browsers:
        profiles = browser.get("profiles") or []
        if not profiles:
            rows.append(
                {
                    "browser": browser.get("id", ""),
                    "browser_name": browser.get("display_name", ""),
                    "provider": "",
                    "profile_directory": "",
                    "profile_name": "",
                    "profile_account": "",
                    "profile_account_state": "",
                    "status": "skipped",
                    "skip_reason": "no profiles discovered",
                    "account_status": {},
                    "background_plan": None,
                }
            )
            continue
        for profile in profiles:
            for provider_id, provider in provider_map.items():
                can_launch, skip_reason = launchable_browser(browser)
                session_evidence = provider_session_evidence(profile, provider_id)
                text_path = account_audit_text_path(
                    text_dir,
                    browser=str(browser.get("id", "")),
                    profile=str(profile.get("directory", "")),
                    provider=provider_id,
                ) if text_dir else None
                visible_text = text_path.read_text(encoding="utf-8") if text_path and text_path.exists() else ""
                account_status = account_status_record(
                    browser=str(browser.get("id", "")),
                    profile=profile,
                    provider=provider_id,
                    visible_text=visible_text,
                ) if visible_text else {}
                background_plan = None
                if can_launch:
                    background_plan = build_background_launch_plan(
                        browser,
                        profile_directory=str(profile.get("directory", "Default")),
                        port=int(browser.get("default_port", 0)) + port_offset + len(rows),
                        provider=provider_id,
                        mode="chat",
                        model="Auto",
                        headless=headless,
                    )
                rows.append(
                    {
                        "browser": browser.get("id", ""),
                        "browser_name": browser.get("display_name", ""),
                        "provider": provider_id,
                        "provider_url": provider.get("url", ""),
                        "profile_directory": profile.get("directory", ""),
                        "profile_name": profile.get("name", ""),
                        "profile_account": profile.get("account", ""),
                        "profile_account_state": profile.get("account_state", ""),
                        "status": "captured" if account_status else ("skipped" if not can_launch else "needs-ui-capture"),
                        "skip_reason": skip_reason,
                        "text_artifact": str(text_path) if text_path else "",
                        "account_status": account_status,
                        "session_evidence": session_evidence,
                        "background_plan": background_plan,
                    }
                )
    return {"rows": rows}


def render_choice_table(title: str, items: list[dict[str, str]]) -> str:
    lines = [title]
    for index, item in enumerate(items, start=1):
        detail = item.get("detail", "")
        suffix = f"  {detail}" if detail else ""
        lines.append(f"[{index}] {item.get('label', item.get('id', ''))}{suffix}")
    return "\n".join(lines)


def select_index(raw: str, count: int) -> int:
    value = raw.strip()
    if not value:
        return 0
    try:
        index = int(value) - 1
    except ValueError as exc:
        raise ValueError(f"not a number: {raw}") from exc
    if index < 0 or index >= count:
        raise ValueError(f"choice out of range: {raw}")
    return index


def account_status_record(
    *,
    browser: str,
    profile: dict[str, str],
    provider: str,
    visible_text: str = "",
) -> dict[str, Any]:
    visible_status = parse_visible_status(visible_text or "")
    return {
        "browser": normalize_browser_name(browser),
        "profile_directory": profile.get("directory", ""),
        "profile_name": profile.get("name", ""),
        "profile_account": profile.get("account", ""),
        "provider": normalize_provider_name(provider),
        "provider_account": visible_status.get("account", ""),
        "model": visible_status.get("model", ""),
        "plan": visible_status.get("plan", ""),
        "quotas": visible_status.get("quotas", {}),
        "usage": visible_status.get("usage", {}),
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_e2e_record(
    root: Path,
    *,
    provider: str,
    mode: str,
    browser: str,
    profile: str,
    status: str,
    screenshot: Path | None,
    visible_text: str,
    notes: list[str] | None = None,
) -> dict[str, Path]:
    paths = build_artifact_paths(root, provider=provider, mode=mode, browser=browser, profile=profile)
    payload = {
        "provider": provider,
        "mode": mode,
        "browser": browser,
        "profile": profile,
        "status": status,
        "screenshot": str(screenshot) if screenshot else "",
        "verification": verify_visible_text(visible_text, provider=provider, mode=mode) if visible_text else None,
        "notes": notes or [],
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    return paths


def cmd_discover(args: argparse.Namespace) -> int:
    browsers = discover_browsers()
    print(json.dumps({"browsers": browsers, "providers": provider_registry()}, ensure_ascii=False, indent=2))
    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    payload = {
        "browsers": discover_browsers(),
        "providers": provider_registry(),
        "backends": backend_registry(),
    }
    payload["matrix"] = build_test_matrix(payload["browsers"], payload["providers"], backend=args.backend)
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload if args.json else payload["matrix"], ensure_ascii=False, indent=2))
    return 0


def cmd_feature_suite(args: argparse.Namespace) -> int:
    providers = requested_provider_ids(args.providers) if args.providers else []
    payload = {
        "targets": primary_feature_targets(),
        "browsers": discover_browsers(),
        "suite": build_primary_feature_suite(
            discover_browsers(),
            providers=providers,
            include_all_features=args.all_features,
            backend=args.backend,
        ),
    }
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload if args.json else payload["suite"], ensure_ascii=False, indent=2))
    return 0


def cmd_backends(args: argparse.Namespace) -> int:
    print(json.dumps({"backends": backend_registry()}, ensure_ascii=False, indent=2))
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    provider_id = normalize_provider_name(args.provider) if args.provider else ""
    catalog = model_catalog()
    if provider_id:
        if provider_id not in catalog:
            raise SystemExit(f"unknown provider: {args.provider}")
        print(json.dumps({"provider": provider_id, **catalog[provider_id]}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"providers": catalog}, ensure_ascii=False, indent=2))
    return 0


def cmd_accounts(args: argparse.Namespace) -> int:
    browsers = {b["id"]: b for b in discover_browsers()}
    browser_id = normalize_browser_name(args.browser)
    if browser_id not in browsers:
        raise SystemExit(f"browser not discovered: {args.browser}")
    profile = resolve_profile(browsers[browser_id]["profiles"], args.profile)
    visible_text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else ""
    record = account_status_record(
        browser=browser_id,
        profile=profile,
        provider=args.provider,
        visible_text=visible_text,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def prompt_choice(title: str, items: list[dict[str, str]]) -> dict[str, str]:
    if not items:
        raise SystemExit(f"nothing to choose for {title}")
    print(render_choice_table(title, items), file=sys.stderr)
    print("Select [1]: ", end="", file=sys.stderr, flush=True)
    raw = sys.stdin.readline()
    return items[select_index(raw, len(items))]


def cmd_wizard(args: argparse.Namespace) -> int:
    browsers = discover_browsers()
    browser_choice = prompt_choice(
        "Browser",
        [
            {
                "id": browser["id"],
                "label": str(browser["display_name"]),
                "detail": f"{len(browser.get('profiles', []))} profiles",
            }
            for browser in browsers
        ],
    )
    browser = next(item for item in browsers if item["id"] == browser_choice["id"])
    profile_choice = prompt_choice(
        "Profiles",
        [
            {
                "id": profile["directory"],
                "label": f"{profile['name']} ({profile['directory']})",
                "detail": profile.get("account", "") or "account unknown",
            }
            for profile in browser.get("profiles", [])
        ],
    )
    providers = provider_registry()
    provider_choice = prompt_choice(
        "Providers",
        [
            {
                "id": provider_id,
                "label": provider_id,
                "detail": ", ".join(provider.get("modes", [])),
            }
            for provider_id, provider in providers.items()
        ],
    )
    provider_id = provider_choice["id"]
    feature_choice = prompt_choice(
        "Features",
        [
            {
                "id": mode,
                "label": mode,
                "detail": "testable UI marker",
            }
            for mode in providers[provider_id].get("modes", [])
        ],
    )
    model_choice = prompt_choice(
        "Models",
        [
            {
                "id": model,
                "label": model,
                "detail": "select in provider UI after launch",
            }
            for model in model_catalog()[provider_id].get("models", ["Auto"])
        ],
    )
    launch_plan = build_launch_plan(
        browser,
        profile_directory=profile_choice["id"],
        port=args.port or int(browser["default_port"]),
        provider=provider_id,
        mode=feature_choice["id"],
        model=model_choice["id"],
        headless=not args.headful,
    )
    payload = {
        "selection": {
            "browser": browser["id"],
            "profile": profile_choice["id"],
            "provider": provider_id,
            "feature": feature_choice["id"],
            "model": model_choice["id"],
        },
        "account_status": account_status_record(
            browser=browser["id"],
            profile=resolve_profile(browser.get("profiles", []), profile_choice["id"]),
            provider=provider_id,
        ),
        "launch_plan": launch_plan,
        "launch_args": launch_plan["launch_args"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    browsers = {b["id"]: b for b in discover_browsers()}
    browser_id = normalize_browser_name(args.browser)
    if browser_id not in browsers:
        raise SystemExit(f"browser not discovered: {args.browser}")
    browser = browsers[browser_id]
    blockers = []
    try:
        profile = resolve_profile(browser["profiles"], args.profile)
    except ValueError:
        profile = {"directory": args.profile, "name": "", "account": "", "path": ""}
        blockers.append(f"no profiles discovered for {browser['display_name']}")
    port = args.port or int(browser["default_port"])
    blockers.extend(
        detect_launch_blockers(
            browser_name=str(browser["display_name"]),
            port=port,
            port_owner=port_owner(port),
            process_args=process_args_for_browser(str(browser["display_name"])),
        )
    )
    print(json.dumps({"browser": browser, "profile": profile, "port": port, "blockers": blockers}, ensure_ascii=False, indent=2))
    return 2 if blockers else 0


def cmd_launch_background(args: argparse.Namespace) -> int:
    browsers = {b["id"]: b for b in discover_browsers()}
    browser_id = normalize_browser_name(args.browser)
    if browser_id not in browsers:
        raise SystemExit(f"browser not discovered: {args.browser}")
    browser = browsers[browser_id]
    can_launch, reason = launchable_browser(browser)
    if not can_launch:
        payload = {"plan": None, "execution": {"started": False, "dry_run": args.dry_run, "error": reason}}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    profile = resolve_profile(browser["profiles"], args.profile)
    plan = build_background_launch_plan(
        browser,
        profile_directory=profile["directory"],
        port=args.port or int(browser["default_port"]),
        provider=args.provider,
        mode=args.mode,
        model=args.model,
        headless=args.headless,
    )
    blockers = detect_launch_blockers(
        browser_name=str(browser["display_name"]),
        port=int(plan["port"]),
        port_owner=port_owner(int(plan["port"])),
        process_args=process_args_for_browser(str(browser["display_name"])),
    )
    if blockers and not args.force:
        payload = {"plan": plan, "execution": {"started": False, "dry_run": args.dry_run, "blockers": blockers}}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if args.dry_run else 2
    execution = execute_background_launch(plan, dry_run=args.dry_run)
    print(json.dumps({"plan": plan, "execution": execution}, ensure_ascii=False, indent=2))
    return 0


def cmd_launch_all_background(args: argparse.Namespace) -> int:
    plan = build_background_all_plan(
        discover_browsers(),
        provider=args.provider,
        mode=args.mode,
        model=args.model,
        headless=args.headless,
        port_offset=args.port_offset,
        all_profiles=args.all_profiles,
    )
    executions = []
    for launch_plan in plan["launches"]:
        blockers = detect_launch_blockers(
            browser_name=str(launch_plan.get("browser_display_name") or launch_plan.get("browser", "")),
            port=int(launch_plan["port"]),
            port_owner=port_owner(int(launch_plan["port"])),
            process_args=process_args_for_browser(str(launch_plan.get("browser_display_name") or launch_plan.get("browser", ""))),
        )
        if blockers and not args.force:
            executions.append({"started": False, "dry_run": args.dry_run, "blockers": blockers})
            continue
        executions.append(execute_background_launch(launch_plan, dry_run=args.dry_run))
    print(json.dumps({"plan": plan, "executions": executions}, ensure_ascii=False, indent=2))
    return 0 if all(execution.get("started") or execution.get("dry_run") for execution in executions) else 2


def cmd_account_audit(args: argparse.Namespace) -> int:
    provider_ids = requested_provider_ids(args.providers)
    providers = provider_registry()
    provider_map = {provider_id: providers[provider_id] for provider_id in provider_ids}
    payload = build_account_audit_matrix(
        discover_browsers(),
        provider_map,
        text_dir=Path(args.text_dir).expanduser() if args.text_dir else None,
        headless=args.headless,
        port_offset=args.port_offset,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_verify_text(args: argparse.Namespace) -> int:
    text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else sys.stdin.read()
    result = verify_visible_text(text, provider=args.provider, mode=args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["detected"] else 1


def cmd_record_e2e(args: argparse.Namespace) -> int:
    visible_text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else ""
    paths = write_e2e_record(
        Path(args.artifact_root).expanduser(),
        provider=normalize_provider_name(args.provider),
        mode=args.mode,
        browser=normalize_browser_name(args.browser),
        profile=args.profile,
        status=args.status,
        screenshot=Path(args.screenshot).expanduser() if args.screenshot else None,
        visible_text=visible_text,
        notes=args.note or [],
    )
    print(json.dumps({k: str(v) for k, v in paths.items()}, ensure_ascii=False, indent=2))
    return 0


def cmd_probe_specs(args: argparse.Namespace) -> int:
    provider_id = normalize_provider_name(args.provider) if args.provider else ""
    specs = provider_probe_specs()
    if provider_id:
        if provider_id not in specs:
            raise SystemExit(f"unknown provider: {args.provider}")
        print(json.dumps({"provider": provider_id, "probe_spec": specs[provider_id]}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"probe_specs": specs}, ensure_ascii=False, indent=2))
    return 0


def cmd_oracle_plan(args: argparse.Namespace) -> int:
    files = [item for item in args.file or [] if item]
    payload = build_oracle_plan(
        prompt=args.prompt,
        files=files,
        cdp_port=args.cdp_port,
        deep_research=args.deep_research,
        model_strategy=args.browser_model_strategy,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_e2e_probe(args: argparse.Namespace) -> int:
    provider_id = normalize_provider_name(args.provider)
    browser_id = normalize_browser_name(args.browser)
    artifact_root = Path(args.artifact_root).expanduser()
    if args.text_file:
        visible_text = Path(args.text_file).expanduser().read_text(encoding="utf-8")
        paths = build_artifact_paths(artifact_root, provider=provider_id, mode=args.mode, browser=browser_id, profile=args.profile)
        paths["run_dir"].mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": provider_id,
            "mode": args.mode,
            "browser": browser_id,
            "profile": args.profile,
            "status": "captured",
            "source": "text-file",
            "screenshot": args.screenshot,
            "inventory": extract_provider_inventory(provider_id, visible_text),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
        print(json.dumps({**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}, ensure_ascii=False, indent=2))
        return 0
    if not args.cdp_port:
        raise SystemExit("e2e-probe requires --cdp-port for live runs or --text-file for captured UI text")
    if not is_port_open(args.cdp_port):
        print(json.dumps({"status": "blocked", "blocker": f"CDP port {args.cdp_port} is not reachable"}, ensure_ascii=False, indent=2))
        return 2
    payload = agent_browser_probe(
        cdp_port=args.cdp_port,
        provider=provider_id,
        mode=args.mode,
        artifact_root=artifact_root,
        browser=browser_id,
        profile=args.profile,
        session=args.session,
        open_controls=args.open_controls,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "captured" else 1


def cmd_agent_browser_suite(args: argparse.Namespace) -> int:
    providers = requested_provider_ids(args.providers) if args.providers else ["chatgpt", "gemini", "claude"]
    browsers = discover_browsers()
    selected_browser_ids = {normalize_browser_name(item.strip()) for item in args.browsers.split(",") if item.strip()}
    if selected_browser_ids:
        browsers = [browser for browser in browsers if browser.get("id") in selected_browser_ids]
    rows = build_primary_feature_suite(
        browsers,
        providers=providers,
        include_all_features=args.all_features,
        backend="agent-browser-profile-clone",
    )
    if args.plan_only:
        payload = {
            "status": "planned",
            "artifact_root": str(Path(args.artifact_root).expanduser()),
            "clone_root": str(Path(args.clone_root).expanduser()),
            "suite": rows,
        }
        if args.output:
            write_json(Path(args.output).expanduser(), payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    browser_map = {browser["id"]: browser for browser in browsers}
    results = []
    for index, row in enumerate(rows, start=1):
        if args.max_runs and len(results) >= args.max_runs:
            break
        browser = browser_map.get(str(row["browser"]))
        if not browser:
            continue
        profile = resolve_profile(browser.get("profiles", []), str(row["profile_directory"]))
        result = agent_browser_profile_probe(
            browser=browser,
            profile=profile,
            provider=str(row["provider"]),
            mode=str(row["feature"]),
            model=str(row["model"]),
            artifact_root=Path(args.artifact_root).expanduser(),
            clone_root=Path(args.clone_root).expanduser(),
            open_controls=args.open_controls,
            timeout=args.timeout,
        )
        results.append({**row, "probe_result": result, "run_index": index})
    payload = {
        "status": "completed",
        "artifact_root": str(Path(args.artifact_root).expanduser()),
        "clone_root": str(Path(args.clone_root).expanduser()),
        "results": results,
    }
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all((result.get("probe_result") or {}).get("status") in {"captured", "signed-out-or-wall"} for result in results) else 1


def cmd_save_chat(args: argparse.Namespace) -> int:
    text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else sys.stdin.read()
    record = save_chat_record(
        cache_root=Path(args.cache_root).expanduser(),
        browser=args.browser,
        profile=args.profile,
        provider=args.provider,
        chat_url=args.chat_url,
        title=args.title,
        text=text,
        source=args.source,
        refresh=args.refresh,
    )
    payload = {
        "key": record["key"],
        "cache_hit": record["cache_hit"],
        "metadata": record["metadata"],
        "metadata_path": str(record["metadata_path"]),
        "text_path": str(record["text_path"]),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_chat_cache(args: argparse.Namespace) -> int:
    key = chat_cache_key(
        browser=args.browser,
        profile=args.profile,
        provider=args.provider,
        chat_url=args.chat_url,
    )
    paths = chat_record_paths(Path(args.cache_root).expanduser(), key)
    if paths["metadata_path"].exists() and not args.refresh:
        metadata = read_json(paths["metadata_path"])
        text = paths["text_path"].read_text(encoding="utf-8") if paths["text_path"].exists() and args.include_text else ""
        print(json.dumps({"key": key, "cache_hit": True, "metadata": metadata, "text": text}, ensure_ascii=False, indent=2))
        return 0
    if not args.text_file:
        print(json.dumps({"key": key, "cache_hit": False, "needs_scrape": True}, ensure_ascii=False, indent=2))
        return 2
    return cmd_save_chat(args)


def cmd_list_chats(args: argparse.Namespace) -> int:
    records = list_chat_records(
        Path(args.cache_root).expanduser(),
        provider=args.provider,
        browser=args.browser,
        profile=args.profile,
    )
    print(json.dumps({"cache_root": str(Path(args.cache_root).expanduser()), "chats": records}, ensure_ascii=False, indent=2))
    return 0


def cmd_parse_chats(args: argparse.Namespace) -> int:
    text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else sys.stdin.read()
    print(json.dumps({"chats": parse_chat_listing(text, provider=args.provider)}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover browser profiles and run AI research/agent workflows with E2E artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("backends")
    probe_specs = sub.add_parser("probe-specs")
    probe_specs.add_argument("--provider", choices=provider_cli_choices(), default="")
    oracle_plan = sub.add_parser("oracle-plan")
    oracle_plan.add_argument("-p", "--prompt", required=True)
    oracle_plan.add_argument("--file", action="append")
    oracle_plan.add_argument("--cdp-port", type=int)
    oracle_plan.add_argument("--deep-research", action="store_true")
    oracle_plan.add_argument("--browser-model-strategy", choices=["select", "current", "ignore"], default="current")
    models = sub.add_parser("models")
    models.add_argument("--provider", choices=provider_cli_choices(), default="")
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--json", action="store_true", help="Include discovered browsers and provider registry.")
    matrix.add_argument("--output", default="")
    matrix.add_argument("--backend", default="manual", choices=sorted(backend_registry().keys()))
    feature_suite = sub.add_parser("feature-suite")
    feature_suite.add_argument("--providers", default="chatgpt,gemini,claude", help="Comma-separated providers. Defaults to primary ChatGPT/Gemini/Claude targets.")
    feature_suite.add_argument("--all-features", action="store_true", help="Use every mode in the provider registry instead of the focused primary suite.")
    feature_suite.add_argument("--backend", default="agent-browser", choices=sorted([*backend_registry().keys(), "agent-browser", "agent-browser-profile-clone"]))
    feature_suite.add_argument("--json", action="store_true", help="Include discovered browsers and target definitions.")
    feature_suite.add_argument("--output", default="")
    accounts = sub.add_parser("accounts")
    accounts.add_argument("--browser", required=True)
    accounts.add_argument("--profile", default="Default")
    accounts.add_argument("--provider", choices=provider_cli_choices(), required=True)
    accounts.add_argument("--text-file", default="")
    wizard = sub.add_parser("wizard")
    wizard.add_argument("--port", type=int)
    wizard.add_argument("--headful", action="store_true")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--browser", required=True)
    preflight.add_argument("--profile", default="Default")
    preflight.add_argument("--port", type=int)
    launch = sub.add_parser("launch-args")
    launch.add_argument("--browser", required=True)
    launch.add_argument("--profile", default="Default")
    launch.add_argument("--provider", choices=provider_cli_choices(), required=True)
    launch.add_argument("--mode", default="chat")
    launch.add_argument("--model", default="Auto")
    launch.add_argument("--port", type=int)
    launch.add_argument("--headful", action="store_true")
    launch.add_argument("--artifact-root", default="")
    launch_background = sub.add_parser("launch-background")
    launch_background.add_argument("--browser", required=True)
    launch_background.add_argument("--profile", default="Default")
    launch_background.add_argument("--provider", choices=provider_cli_choices(), required=True)
    launch_background.add_argument("--mode", default="chat")
    launch_background.add_argument("--model", default="Auto")
    launch_background.add_argument("--port", type=int)
    launch_background.add_argument("--headless", action="store_true")
    launch_background.add_argument("--dry-run", action="store_true")
    launch_background.add_argument("--force", action="store_true", help="Launch even when preflight reports a running non-CDP browser.")
    launch_all_background = sub.add_parser("launch-all-background")
    launch_all_background.add_argument("--provider", choices=provider_cli_choices(), required=True)
    launch_all_background.add_argument("--mode", default="chat")
    launch_all_background.add_argument("--model", default="Auto")
    launch_all_background.add_argument("--headless", action="store_true")
    launch_all_background.add_argument("--dry-run", action="store_true")
    launch_all_background.add_argument("--force", action="store_true", help="Launch even when preflight reports running non-CDP browsers.")
    launch_all_background.add_argument("--all-profiles", action="store_true")
    launch_all_background.add_argument("--port-offset", type=int, default=100)
    account_audit = sub.add_parser("account-audit")
    account_audit.add_argument("--providers", default="", help="Comma-separated providers. Defaults to every provider.")
    account_audit.add_argument("--text-dir", default="", help="Directory containing <browser>-<profile>-<provider>.txt UI captures.")
    account_audit.add_argument("--output", default="")
    account_audit.add_argument("--headless", action="store_true")
    account_audit.add_argument("--port-offset", type=int, default=200)
    verify = sub.add_parser("verify-text")
    verify.add_argument("--provider", choices=provider_cli_choices(), required=True)
    verify.add_argument("--mode", required=True)
    verify.add_argument("--text-file", default="")
    record = sub.add_parser("record-e2e")
    record.add_argument("--artifact-root", required=True)
    record.add_argument("--provider", choices=provider_cli_choices(), required=True)
    record.add_argument("--mode", required=True)
    record.add_argument("--browser", required=True)
    record.add_argument("--profile", required=True)
    record.add_argument("--status", choices=["blocked", "selected", "started", "verified", "failed"], required=True)
    record.add_argument("--screenshot", default="")
    record.add_argument("--text-file", default="")
    record.add_argument("--note", action="append")
    e2e_probe = sub.add_parser("e2e-probe")
    e2e_probe.add_argument("--artifact-root", required=True)
    e2e_probe.add_argument("--browser", required=True)
    e2e_probe.add_argument("--profile", required=True)
    e2e_probe.add_argument("--provider", choices=provider_cli_choices(), required=True)
    e2e_probe.add_argument("--mode", default="chat")
    e2e_probe.add_argument("--cdp-port", type=int)
    e2e_probe.add_argument("--session", default="")
    e2e_probe.add_argument("--text-file", default="")
    e2e_probe.add_argument("--screenshot", default="")
    e2e_probe.add_argument("--open-controls", action="store_true", help="Best-effort click known model/tool controls and resnapshot.")
    agent_suite = sub.add_parser("agent-browser-suite")
    agent_suite.add_argument("--artifact-root", default="/tmp/hermes-ai-research-agent-browser-e2e")
    agent_suite.add_argument("--clone-root", default="/tmp/hermes-ai-research-agent-browser-clones")
    agent_suite.add_argument("--providers", default="chatgpt,gemini,claude")
    agent_suite.add_argument("--browsers", default="", help="Comma-separated browser ids. Defaults to every discovered browser.")
    agent_suite.add_argument("--all-features", action="store_true")
    agent_suite.add_argument("--open-controls", action="store_true")
    agent_suite.add_argument("--plan-only", action="store_true")
    agent_suite.add_argument("--max-runs", type=int, default=0, help="Limit probe count for smoke tests.")
    agent_suite.add_argument("--timeout", type=float, default=45.0, help="Per Agent Browser command timeout in seconds.")
    agent_suite.add_argument("--output", default="")
    save_chat = sub.add_parser("save-chat")
    save_chat.add_argument("--cache-root", default=str(default_chat_cache_root()))
    save_chat.add_argument("--browser", required=True)
    save_chat.add_argument("--profile", required=True)
    save_chat.add_argument("--provider", choices=provider_cli_choices(), required=True)
    save_chat.add_argument("--chat-url", required=True)
    save_chat.add_argument("--title", default="")
    save_chat.add_argument("--text-file", default="")
    save_chat.add_argument("--source", default="manual")
    save_chat.add_argument("--refresh", action="store_true")
    chat_cache = sub.add_parser("chat-cache")
    chat_cache.add_argument("--cache-root", default=str(default_chat_cache_root()))
    chat_cache.add_argument("--browser", required=True)
    chat_cache.add_argument("--profile", required=True)
    chat_cache.add_argument("--provider", choices=provider_cli_choices(), required=True)
    chat_cache.add_argument("--chat-url", required=True)
    chat_cache.add_argument("--title", default="")
    chat_cache.add_argument("--text-file", default="")
    chat_cache.add_argument("--source", default="manual")
    chat_cache.add_argument("--refresh", action="store_true")
    chat_cache.add_argument("--include-text", action="store_true")
    list_chats = sub.add_parser("list-chats")
    list_chats.add_argument("--cache-root", default=str(default_chat_cache_root()))
    list_chats.add_argument("--provider", default="")
    list_chats.add_argument("--browser", default="")
    list_chats.add_argument("--profile", default="")
    parse_chats = sub.add_parser("parse-chats")
    parse_chats.add_argument("--provider", choices=provider_cli_choices(), required=True)
    parse_chats.add_argument("--text-file", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "discover":
        return cmd_discover(args)
    if args.command == "backends":
        return cmd_backends(args)
    if args.command == "probe-specs":
        return cmd_probe_specs(args)
    if args.command == "oracle-plan":
        return cmd_oracle_plan(args)
    if args.command == "models":
        return cmd_models(args)
    if args.command == "matrix":
        return cmd_matrix(args)
    if args.command == "feature-suite":
        return cmd_feature_suite(args)
    if args.command == "accounts":
        return cmd_accounts(args)
    if args.command == "wizard":
        return cmd_wizard(args)
    if args.command == "preflight":
        return cmd_preflight(args)
    if args.command == "launch-background":
        return cmd_launch_background(args)
    if args.command == "launch-all-background":
        return cmd_launch_all_background(args)
    if args.command == "account-audit":
        return cmd_account_audit(args)
    if args.command == "launch-args":
        browsers = {b["id"]: b for b in discover_browsers()}
        browser_id = normalize_browser_name(args.browser)
        if browser_id not in browsers:
            raise SystemExit(f"browser not discovered: {args.browser}")
        browser = browsers[browser_id]
        profile = resolve_profile(browser["profiles"], args.profile)
        launch_plan = build_launch_plan(
            browser,
            profile_directory=profile["directory"],
            port=args.port or int(browser["default_port"]),
            provider=normalize_provider_name(args.provider),
            mode=args.mode,
            model=args.model,
            headless=not args.headful,
        )
        payload = {
            "browser": browser["id"],
            "profile": profile,
            "provider": normalize_provider_name(args.provider),
            "mode": args.mode,
            "model": launch_plan["model"],
            "model_selection": launch_plan["model_selection"],
            "launch_args": launch_plan["launch_args"],
        }
        if args.artifact_root:
            paths = build_artifact_paths(Path(args.artifact_root), provider=args.provider, mode=args.mode, browser=browser["id"], profile=args.profile)
            payload["artifacts"] = {k: str(v) for k, v in paths.items()}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "verify-text":
        return cmd_verify_text(args)
    if args.command == "record-e2e":
        return cmd_record_e2e(args)
    if args.command == "e2e-probe":
        return cmd_e2e_probe(args)
    if args.command == "agent-browser-suite":
        return cmd_agent_browser_suite(args)
    if args.command == "save-chat":
        return cmd_save_chat(args)
    if args.command == "chat-cache":
        return cmd_chat_cache(args)
    if args.command == "list-chats":
        return cmd_list_chats(args)
    if args.command == "parse-chats":
        return cmd_parse_chats(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
