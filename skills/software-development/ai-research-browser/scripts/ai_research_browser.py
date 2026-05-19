#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import tempfile
import urllib.parse
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

KNOWN_EXTENSION_IDS = {
    "ai-exporter": {
        "ids": ["kagjkiiecagemklhmhkabbalfpbianbe"],
        "aliases": ["saveai", "save-ai", "ai-exporter", "ai exporter"],
        "description": "SaveAI / AI Exporter browser extension for exporting AI chats, including Notion sync.",
    }
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
        "unbrowser-local": {
            "scope": "local",
            "aliases": ["Unbrowser Local", "@unbrowser/local", "npx @unbrowser/local"],
            "description": (
                "Local Playwright-based Unbrowser runner for page extraction and pattern learning. "
                "Use as an extraction/check backend around provider pages; keep profile mutation in the local CDP workflow."
            ),
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
        {
            "provider": "grok",
            "mode": "chat",
            "model": "Fast",
            "must_verify": ["login", "model-selector", "composer-ready"],
            "notes": "Grok normal chat and visible model selector.",
        },
        {
            "provider": "grok",
            "mode": "research",
            "model": "Grok 4.1 Fast Reasoning",
            "must_verify": ["login", "deepsearch-or-research-tool", "model-selector"],
            "notes": "Grok DeepSearch/Research availability and reasoning/search controls.",
        },
        {
            "provider": "perplexity",
            "mode": "chat",
            "model": "Best",
            "must_verify": ["login", "model-selector", "composer-ready"],
            "notes": "Perplexity normal search/chat and account readiness.",
        },
        {
            "provider": "perplexity",
            "mode": "research",
            "model": "Best",
            "must_verify": ["login", "research-mode", "model-selector"],
            "notes": "Perplexity Research/Advanced Research availability.",
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
        if len(profiles) == 1:
            return profiles[0]
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


def known_extension_ids(name_or_id: str) -> list[str]:
    value = name_or_id.strip().lower()
    if not value:
        return []
    for extension_name, spec in KNOWN_EXTENSION_IDS.items():
        aliases = [extension_name, *[str(alias) for alias in spec.get("aliases", [])]]
        if value in [alias.lower() for alias in aliases]:
            return [str(item) for item in spec.get("ids", [])]
    return [name_or_id.strip()]


def extension_manifest_name(extension_version_dir: Path, manifest: dict[str, Any]) -> str:
    raw_name = str(manifest.get("name") or "")
    match = re.fullmatch(r"__MSG_(.+)__", raw_name)
    if not match:
        return raw_name
    default_locale = str(manifest.get("default_locale") or "en")
    messages = read_json(extension_version_dir / "_locales" / default_locale / "messages.json")
    message = messages.get(match.group(1), {})
    if isinstance(message, dict) and message.get("message"):
        return str(message["message"])
    return raw_name


def discover_profile_extensions(
    profile: dict[str, str],
    *,
    extension_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    profile_root = Path(profile.get("path", "")).expanduser()
    extension_root = profile_root / "Extensions"
    wanted = {item.lower() for item in extension_ids or []}
    if not extension_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for extension_dir in sorted(child for child in extension_root.iterdir() if child.is_dir()):
        extension_id = extension_dir.name
        if wanted and extension_id.lower() not in wanted:
            continue
        version_dirs = sorted([child for child in extension_dir.iterdir() if child.is_dir()], key=lambda p: p.name, reverse=True)
        for version_dir in version_dirs:
            manifest_path = version_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            manifest = read_json(manifest_path)
            records.append(
                {
                    "id": extension_id,
                    "name": extension_manifest_name(version_dir, manifest),
                    "version": str(manifest.get("version") or version_dir.name),
                    "manifest_path": str(manifest_path),
                    "path": str(version_dir),
                    "default_popup": str((manifest.get("action") or {}).get("default_popup") or ""),
                    "permissions": [str(item) for item in manifest.get("permissions", []) if isinstance(item, str)],
                    "host_permissions": [str(item) for item in manifest.get("host_permissions", []) if isinstance(item, str)],
                }
            )
            break
    return records


def discover_extensions(
    browsers: list[dict[str, Any]] | None = None,
    *,
    extension_ids: list[str] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for browser in browsers or discover_browsers():
        for profile in browser.get("profiles") or []:
            for extension in discover_profile_extensions(profile, extension_ids=extension_ids):
                rows.append(
                    {
                        "browser": browser.get("id", ""),
                        "browser_name": browser.get("display_name", ""),
                        "profile_directory": profile.get("directory", ""),
                        "profile_name": profile.get("name", ""),
                        "profile_account_state": profile.get("account_state", ""),
                        "extension": extension,
                    }
                )
    return {"extensions": rows}


AI_EXPORTER_ACTIONS = [
    "copyFullMarkdown",
    "exportFullMarkdown",
    "exportFullText",
    "exportFullJSON",
    "exportFullWord",
    "exportFullPDF",
    "captureAllToImage",
    "openFullNotionExport",
    "saveFullChatsToNotion",
]


AI_EXPORTER_PROVIDER_HOSTS = {
    "chatgpt": ["chatgpt.com", "chat.openai.com"],
    "gemini": ["gemini.google.com"],
    "claude": ["claude.ai"],
    "grok": ["grok.com"],
    "perplexity": ["www.perplexity.ai", "perplexity.ai"],
    "googleaistudio": ["aistudio.google.com"],
    "notebooklm": ["notebooklm.google.com"],
    "deepseek": ["chat.deepseek.com"],
}


def manifest_supported_hosts(manifest: dict[str, Any]) -> list[str]:
    hosts: set[str] = set()
    for script in manifest.get("content_scripts", []):
        if not isinstance(script, dict):
            continue
        for match in script.get("matches", []):
            if not isinstance(match, str):
                continue
            try:
                hostname = urllib.parse.urlparse(match.replace("*://", "https://").replace("/*", "/")).hostname
            except Exception:
                hostname = ""
            if hostname:
                hosts.add(hostname)
    return sorted(hosts)


def ai_exporter_supported_providers(manifest: dict[str, Any]) -> list[str]:
    hosts = manifest_supported_hosts(manifest)
    providers: list[str] = []
    for provider, provider_hosts in AI_EXPORTER_PROVIDER_HOSTS.items():
        if any(any(host == target or host.endswith(f".{target}") for target in provider_hosts) for host in hosts):
            providers.append(provider)
    return providers


def build_ai_exporter_capabilities(browsers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    extension_ids = known_extension_ids("ai-exporter")
    for browser in browsers or discover_browsers():
        for profile in browser.get("profiles") or []:
            for extension in discover_profile_extensions(profile, extension_ids=extension_ids):
                manifest_path = Path(str(extension.get("manifest_path", ""))).expanduser()
                manifest = read_json(manifest_path)
                rows.append(
                    {
                        "browser": browser.get("id", ""),
                        "browser_name": browser.get("display_name", ""),
                        "profile_directory": profile.get("directory", ""),
                        "profile_name": profile.get("name", ""),
                        "profile_account_state": profile.get("account_state", ""),
                        "extension": extension,
                        "supported_hosts": manifest_supported_hosts(manifest),
                        "supported_providers": ai_exporter_supported_providers(manifest),
                        "actions": AI_EXPORTER_ACTIONS,
                        "notion": {
                            "requires_notion_login": True,
                            "session_evidence": provider_session_evidence(profile, "notion"),
                            "api_family": "notion-web-clipper-v3",
                            "writes_externally": True,
                        },
                        "automation_notes": [
                            "Content script listens for runtime actions such as exportFullMarkdown, copyFullMarkdown, openFullNotionExport, and saveFullChatsToNotion.",
                            "Notion sync depends on Notion cookies and a selected workspace/page/database from the extension UI.",
                            "For E2E proof, load the extension into the temporary profile, export Markdown locally first, then only perform Notion sync when explicitly requested.",
                        ],
                    }
                )
    return {
        "extension_alias": "ai-exporter",
        "extension_ids": extension_ids,
        "actions": AI_EXPORTER_ACTIONS,
        "rows": rows,
    }


def provider_url(provider: str) -> str:
    providers = provider_registry()
    provider = normalize_provider_name(provider)
    if provider not in providers:
        raise ValueError(f"unknown provider: {provider}")
    return str(providers[provider]["url"])


def provider_domain(provider: str) -> str:
    return urllib.parse.urlparse(provider_url(provider)).hostname or ""


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
        "--disable-remote-fonts",
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


def expand_agent_browser_eval_text(text: str) -> str:
    chunks = [text or ""]
    for line in (text or "").splitlines():
        stripped = line.strip()
        if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, str) and decoded not in chunks:
                chunks.append(decoded)
    return "\n".join(chunks)


def parse_visible_status(text: str, *, provider: str = "") -> dict[str, Any]:
    provider_id = normalize_provider_name(provider) if provider else ""
    text = expand_agent_browser_eval_text(text or "")
    account_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    lines = [line.strip().strip('"') for line in text.splitlines() if line.strip()]
    model_match = re.search(r"Model:\s*([^\n]+)", text, flags=re.I)
    if not model_match:
        model_pattern = r"\b((?:GPT[- ][^\n]+|Claude[ \t]+[^\n]+|Opus[ \t]+[^\n]+|Sonnet[ \t]+[^\n]+|Gemini[ \t]+[^\n]+|Grok[ \t]+[^\n]+))"
        provider_model_prefixes = {
            "chatgpt": ("gpt",),
            "gemini": ("gemini",),
            "claude": ("claude", "opus", "sonnet"),
            "grok": ("grok",),
            "perplexity": ("sonar", "gpt", "claude", "gemini"),
        }
        for candidate in re.finditer(model_pattern, text, flags=re.I):
            candidate_text = candidate.group(1).strip()
            if provider_id in provider_model_prefixes and not candidate_text.casefold().startswith(provider_model_prefixes[provider_id]):
                continue
            line_start = text.rfind("\n", 0, candidate.start()) + 1
            line_end = text.find("\n", candidate.end())
            if line_end == -1:
                line_end = len(text)
            line = text[line_start:line_end]
            if "[ref=" in line or re.search(r"\b(vs|versus)\b|vergleich|comparison", line, flags=re.I):
                continue
            model_match = candidate
            break
    def is_entitlement_upsell_match(match: re.Match[str]) -> bool:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].casefold()
        local_context = text[max(0, match.start() - 200) : min(len(text), match.end() + 40)].casefold()
        before_match = local_context[: local_context.find(match.group(0).casefold())]
        if re.search(r"\b(vs|versus)\b|vergleich|comparison", line):
            return True
        upsell_phrases = ("upgrade to", "try for", "unlock", "subscribe", "buy ", "purchase", "get supergrok", "get premium")
        return any(phrase in line for phrase in upsell_phrases) or any(phrase in before_match for phrase in upsell_phrases)

    def first_current_plan_match(pattern: str) -> re.Match[str] | None:
        for match in re.finditer(pattern, text, flags=re.I):
            if not is_entitlement_upsell_match(match):
                return match
        return None

    plan_match = first_current_plan_match(
        r"\b(ChatGPT\s+|Claude\s+|Google\s+AI\s+|Google\s+One\s+AI\s+|Gemini\s+|Perplexity\s+|X\s+)?"
        r"(Free|Plus|Pro|Team|Enterprise|Max|Advanced|Ultra|SuperGrok|Premium\+?|Premium)\s+"
        r"(?:plan|subscription|abo|tier)\b"
    )
    if not plan_match:
        plan_match = first_current_plan_match(
            r"\b(Gemini Advanced|Google AI Pro|Google AI Ultra|Google One AI Pro|Google One AI Ultra|"
            r"Perplexity Pro|Perplexity Max|ChatGPT Pro|ChatGPT Plus|Claude Pro|Claude Max|"
            r"SuperGrok|X Premium\+?|Premium\+)\b"
        )
    standalone_plan = ""
    account_name = account_match.group(0) if account_match else ""
    if not plan_match:
        plan_labels = {"free", "plus", "pro", "team", "enterprise", "max", "advanced", "ultra", "supergrok", "premium", "premium+"}
        generic_previous = {"chatgpt", "claude", "gemini", "grok", "perplexity", "recents", "more", "projects", "history"}
        for index, line in enumerate(lines):
            normalized = line.casefold()
            if normalized in plan_labels:
                standalone_plan = line
                if not account_name and index > 0:
                    previous = lines[index - 1].strip()
                    if previous.casefold() not in generic_previous and not re.search(r"^(new chat|search|home|skip to content)$", previous, flags=re.I):
                        account_name = previous
                break
    for index, line in enumerate(lines):
        if line.casefold() == "create team" and index + 1 < len(lines):
            candidate = lines[index + 1].strip()
            if re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", candidate):
                account_name = candidate
                break
    used_percent_match = re.search(r"(?:used|verwendet|genutzt)\D{0,20}(\d{1,3})\s*%", text, flags=re.I)
    if not used_percent_match:
        used_percent_match = re.search(r"(\d{1,3})\s*%\s*(?:used|verwendet|genutzt)", text, flags=re.I)
    remaining_percent_match = re.search(r"(\d{1,3})\s*%\s*(?:remaining|left|übrig|verbleibend)", text, flags=re.I)
    count_match = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:left|remaining|übrig|verbleibend)", text, flags=re.I)
    reset_match = re.search(r"(?:resets?|reset|erneuert|setzt zurück)\s+([^\n.]+)", text, flags=re.I)
    deep_match = re.search(r"(?:Deep research|Rechercheberichte?|Research)[^\n]{0,40}?(\d+)\s*(?:remaining|left|übrig|verbleibend)", text, flags=re.I)
    agent_match = re.search(r"(?:Agent tasks?|Agent)[^\n]{0,40}?(\d+)\s*(?:remaining|left|übrig|verbleibend)", text, flags=re.I)
    raw_plan = plan_match.group(2 if plan_match.lastindex and plan_match.lastindex >= 2 else 1).strip() if plan_match else standalone_plan
    plan = raw_plan
    for prefix in ["ChatGPT ", "Gemini ", "Perplexity ", "Claude ", "Google AI ", "Google One AI ", "X "]:
        plan = plan.replace(prefix, "")
    return {
        "account": account_name,
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
        "visible_status": parse_visible_status(text or "", provider=provider),
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
    expanded = expand_agent_browser_eval_text(text or "")
    lowered = expanded.casefold()
    wall_markers = [
        "just a moment",
        "checking if the site connection is secure",
        "verify you are human",
        "enable javascript and cookies",
        "cloudflare",
    ]
    if any(marker in lowered for marker in wall_markers):
        return "signed-out-or-wall"
    visible_status = parse_visible_status(expanded, provider=provider)
    if visible_status.get("account") or visible_status.get("plan"):
        return "signed-in-or-ready"
    signed_out_lines = {"sign in", "log in", "login", "sign up", "anmelden", "registrieren", "create account"}
    for raw in expanded.splitlines():
        line = raw.strip().strip('"')
        line = re.sub(r"^-?\s*(?:button|link)\s+", "", line, flags=re.I).strip()
        line = re.sub(r"\s+\[ref=.*$", "", line).strip()
        line = line.strip('"')
        if line.casefold() in signed_out_lines:
            return "signed-out-or-wall"
    provider_markers = provider_registry().get(normalize_provider_name(provider), {}).get("mode_markers", {})
    weak_brand_markers = {
        "chatgpt",
        "claude",
        "gemini",
        "grok",
        "perplexity",
    }
    flattened = [
        marker
        for markers in provider_markers.values()
        for marker in markers
        if str(marker).casefold() not in weak_brand_markers
    ]
    if any(str(marker).casefold() in lowered for marker in flattened):
        return "signed-in-or-ready"
    return "unknown"


def extract_provider_inventory(provider: str, text: str) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    text = expand_agent_browser_eval_text(text or "")
    catalog = model_catalog().get(provider_id, {"models": [], "tools": [], "modes": []})
    specs = provider_probe_specs().get(provider_id, {})
    visible_status = parse_visible_status(text, provider=provider_id)
    models = [
        model
        for model in catalog.get("models", [])
        if model != "Auto" and normalized_contains(text, str(model))
    ]
    tools = [
        tool
        for tool in catalog.get("tools", [])
        if normalized_contains(text, str(tool))
    ]
    modes = {}
    for mode in provider_registry().get(provider_id, {}).get("modes", []):
        try:
            modes[mode] = verify_visible_text(text, provider=provider_id, mode=str(mode))["detected"]
        except ValueError:
            modes[mode] = False
    matched_hints = {
        key: [hint for hint in values if normalized_contains(text, str(hint))]
        for key, values in specs.items()
    }
    return {
        "provider": provider_id,
        "login_state": infer_login_state(text, provider_id),
        "visible_status": visible_status,
        "available_models": models,
        "available_tools": tools,
        "available_modes": modes,
        "matched_hints": matched_hints,
        "usage_lines": extract_usage_lines(text),
    }


def agent_browser_command() -> str:
    configured = os.environ.get("HERMES_AGENT_BROWSER") or os.environ.get("AGENT_BROWSER")
    if configured:
        return configured
    resolved = shutil.which("agent-browser")
    if resolved:
        return resolved
    for candidate in [
        "/opt/homebrew/bin/agent-browser",
        "/usr/local/bin/agent-browser",
        str(Path.home() / ".local/bin/agent-browser"),
        str(Path.home() / ".hermes/hermes-agent/node_modules/agent-browser/bin/agent-browser-darwin-arm64"),
    ]:
        if Path(candidate).exists():
            return candidate
    return "agent-browser"


def run_agent_browser(args: list[str], *, session: str = "", timeout: float = 45.0) -> subprocess.CompletedProcess[str]:
    command = [agent_browser_command()]
    if session:
        command.extend(["--session", session])
    command.extend(args)
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")) + f"\nTimed out after {timeout:.0f}s",
        )


def cdp_http_base_for_port(port: int) -> str:
    endpoint = detect_cdp_endpoint(port)
    if endpoint.get("ok") and endpoint.get("base"):
        return str(endpoint["base"])
    return f"http://127.0.0.1:{int(port)}"


def run_cdp_javascript(port: int, javascript: str, *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    bridge = r"""
const [base, expression] = process.argv.slice(1);
const targets = await (await fetch(`${base}/json/list`)).json();
const target = targets.find((item) => item.type === 'page' && !String(item.url || '').startsWith('about:blank')) || targets.find((item) => item.type === 'page');
if (!target || !target.webSocketDebuggerUrl) throw new Error('No page target for CDP eval');
const ws = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
const timer = setTimeout(() => {
  console.error('Timed out waiting for CDP eval');
  process.exit(2);
}, Math.max(1000, Math.floor(Number(process.env.HERMES_CDP_TIMEOUT_MS || '15000'))));
ws.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  if (!payload.id || !pending.has(payload.id)) return;
  const {resolve, reject} = pending.get(payload.id);
  pending.delete(payload.id);
  if (payload.error) reject(new Error(JSON.stringify(payload.error)));
  else resolve(payload.result || {});
});
function send(method, params = {}) {
  const id = ++nextId;
  ws.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
await send('Runtime.enable');
const result = await send('Runtime.evaluate', {
  expression,
  awaitPromise: true,
  returnByValue: true,
  userGesture: true,
});
clearTimeout(timer);
ws.close();
const remote = result.result || {};
if (remote.subtype === 'error') {
  console.error(remote.description || remote.value || 'CDP evaluation error');
  process.exit(1);
}
const value = Object.prototype.hasOwnProperty.call(remote, 'value') ? remote.value : remote.description;
process.stdout.write(typeof value === 'string' ? value : JSON.stringify(value ?? null));
"""
    env = {**os.environ, "HERMES_CDP_TIMEOUT_MS": str(max(1000, int(timeout * 1000)))}
    command = ["node", "--input-type=module", "-e", bridge, cdp_http_base_for_port(port), javascript]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2, env=env)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")) + f"\nTimed out after {timeout:.0f}s",
        )


def run_cdp_keypress(port: int, key: str, *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    key_name = "Enter" if key.lower() in {"enter", "return"} else key
    bridge = r"""
const [base, key] = process.argv.slice(1);
const targets = await (await fetch(`${base}/json/list`)).json();
const target = targets.find((item) => item.type === 'page' && !String(item.url || '').startsWith('about:blank')) || targets.find((item) => item.type === 'page');
if (!target || !target.webSocketDebuggerUrl) throw new Error('No page target for CDP keypress');
const ws = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
const timer = setTimeout(() => {
  console.error('Timed out waiting for CDP keypress');
  process.exit(2);
}, Math.max(1000, Math.floor(Number(process.env.HERMES_CDP_TIMEOUT_MS || '10000'))));
ws.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  if (!payload.id || !pending.has(payload.id)) return;
  const {resolve, reject} = pending.get(payload.id);
  pending.delete(payload.id);
  if (payload.error) reject(new Error(JSON.stringify(payload.error)));
  else resolve(payload.result || {});
});
function send(method, params = {}) {
  const id = ++nextId;
  ws.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
const vk = key === 'Enter' ? 13 : 0;
await send('Input.dispatchKeyEvent', {type: 'rawKeyDown', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk});
await send('Input.dispatchKeyEvent', {type: 'keyUp', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk});
clearTimeout(timer);
ws.close();
process.stdout.write(JSON.stringify({ok: true, key}));
"""
    env = {**os.environ, "HERMES_CDP_TIMEOUT_MS": str(max(1000, int(timeout * 1000)))}
    command = ["node", "--input-type=module", "-e", bridge, cdp_http_base_for_port(port), key_name]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2, env=env)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")) + f"\nTimed out after {timeout:.0f}s",
        )


def run_cdp_navigate(port: int, url: str, *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    bridge = r"""
const [base, url] = process.argv.slice(1);
const targets = await (await fetch(`${base}/json/list`)).json();
const target = targets.find((item) => item.type === 'page') || targets[0];
if (!target || !target.webSocketDebuggerUrl) throw new Error('No page target for CDP navigation');
const ws = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
const timer = setTimeout(() => {
  console.error('Timed out waiting for CDP navigation');
  process.exit(2);
}, Math.max(1000, Math.floor(Number(process.env.HERMES_CDP_TIMEOUT_MS || '15000'))));
ws.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  if (!payload.id || !pending.has(payload.id)) return;
  const {resolve, reject} = pending.get(payload.id);
  pending.delete(payload.id);
  if (payload.error) reject(new Error(JSON.stringify(payload.error)));
  else resolve(payload.result || {});
});
function send(method, params = {}) {
  const id = ++nextId;
  ws.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
await send('Page.enable');
await send('Page.navigate', {url});
clearTimeout(timer);
ws.close();
process.stdout.write(url);
"""
    env = {**os.environ, "HERMES_CDP_TIMEOUT_MS": str(max(1000, int(timeout * 1000)))}
    command = ["node", "--input-type=module", "-e", bridge, cdp_http_base_for_port(port), url]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2, env=env)
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
    timeout: float = 45.0,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    paths = build_artifact_paths(artifact_root, provider=provider_id, mode=mode, browser=browser, profile=profile)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    screenshot = paths["screenshot_png"]
    commands: list[dict[str, Any]] = []

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=timeout)
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
    if any(command.get("returncode") == 124 for command in commands):
        evidence_status = "timeout"
    elif inventory.get("login_state") == "signed-out-or-wall":
        evidence_status = "signed-out-or-wall"
    elif visible_text and screenshot_result.returncode != 0:
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


def live_probe_ok(payload: dict[str, Any], *, assert_login: bool = False) -> bool:
    status = payload.get("status")
    if status not in {"captured", "captured-without-screenshot"}:
        return False
    if assert_login and payload.get("inventory", {}).get("login_state") != "signed-in-or-ready":
        return False
    return True


def provider_composer_selector(provider: str) -> str:
    provider_id = normalize_provider_name(provider)
    selectors = {
        "chatgpt": "textarea, [contenteditable='true'], [role='textbox']",
        "claude": "[contenteditable='true'], textarea, [role='textbox']",
        "grok": "[contenteditable='true'], textarea, [role='textbox']",
        "perplexity": "[contenteditable='true'], textarea, [role='textbox']",
        "gemini": "[contenteditable='true'], textarea, [role='textbox']",
        "openrouter": "textarea, [contenteditable='true'], [role='textbox']",
    }
    return selectors.get(provider_id, "textarea, [contenteditable='true'], [role='textbox']")


def provider_workflow_specs() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "chatgpt": {
            "chat": {
                "feature_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": [],
                "attachment_triggers": ["Add files and more", "Attach files", "Upload file"],
                "running_markers": ["Stop generating", "Regenerate", "Sources"],
                "completion_markers": ["Sources", "Final answer", "Done"],
                "output_selectors": ["main", "[data-testid='conversation-turn']"],
            },
            "deep-research": {
                "feature_triggers": ["Deep research", "Deep Research"],
                "menu_triggers": ["Add files and more", "Tools"],
                "attachment_triggers": ["Add files and more", "Attach files", "Upload file"],
                "pre_prompt_triggers": [],
                "slash_triggers": ["/Deepresearch", "/deep research"],
                "confirmation_triggers": ["Start research", "Create report", "Start", "Begin"],
                "pre_confirm_wait_seconds": 45,
                "running_markers": ["Researching", "Searching", "Creating report"],
                "completion_markers": ["Research complete", "Final answer", "Done"],
                "output_selectors": ["main", "[data-testid='conversation-turn']", "article"],
            },
            "agent": {
                "feature_triggers": ["Agent", "ChatGPT agent", "Use agent"],
                "menu_triggers": ["Add files and more", "Tools"],
                "attachment_triggers": ["Add files and more", "Attach files", "Upload file"],
                "pre_prompt_triggers": [],
                "slash_triggers": ["/agent"],
                "confirmation_triggers": ["Start", "Take control", "Allow", "Confirm"],
                "pre_confirm_wait_seconds": 12,
                "running_markers": ["Agent", "Taking action", "Working", "Running"],
                "completion_markers": ["Done", "Finished", "Completed", "Task complete"],
                "output_selectors": ["main", "[data-testid='conversation-turn']", "article"],
            },
        },
        "gemini": {
            "chat": {
                "feature_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": [],
                "attachment_triggers": ["Menü „Datei hochladen“ öffnen", "Datei hochladen", "Upload files", "Upload file"],
                "running_markers": ["Gemini", "Antwort wird"],
                "completion_markers": ["Sources", "Quellen", "Antwort"],
                "output_selectors": ["#extended-response-markdown-content", "message-content", "main"],
            },
            "deep-research": {
                "feature_triggers": ["Deep Research", "Deep research", "Recherche"],
                "menu_triggers": ["Tools", "Canvas"],
                "attachment_triggers": ["Menü „Datei hochladen“ öffnen", "Datei hochladen", "Upload files", "Upload file"],
                "pre_prompt_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": ["Start research", "Recherche starten", "Starten", "Create plan"],
                "pre_confirm_wait_seconds": 45,
                "running_markers": ["Creating plan", "Plan erstellen", "Researching", "Analysiere Ergebnisse", "Erstelle Bericht"],
                "completion_markers": ["Research complete", "Recherche fertig", "Ich bin mit deiner Recherche fertig", "Abgeschlossen"],
                "output_selectors": ["#extended-response-markdown-content", "message-content", "main"],
            },
            "agent": {
                "feature_triggers": ["Agent"],
                "menu_triggers": ["Tools", "Canvas"],
                "attachment_triggers": ["Menü „Datei hochladen“ öffnen", "Datei hochladen", "Upload files", "Upload file"],
                "pre_prompt_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": ["Confirm", "Bestätigen", "Start", "Allow"],
                "pre_confirm_wait_seconds": 20,
                "running_markers": ["Agent", "Plan", "Working"],
                "completion_markers": ["Done", "Fertig", "Completed"],
                "output_selectors": ["message-content", "main"],
            },
        },
        "perplexity": {
            "chat": {
                "feature_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": [],
                "attachment_triggers": ["Attach", "Upload", "Add file"],
                "running_markers": ["Searching", "Sources"],
                "completion_markers": ["Sources", "Answer"],
                "output_selectors": ["main", "article"],
            },
            "research": {
                "feature_triggers": ["Research", "Deep Research", "Pro Search"],
                "menu_triggers": ["Search", "Focus", "Sources"],
                "attachment_triggers": ["Attach", "Upload", "Add file"],
                "pre_prompt_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": ["Start", "Submit"],
                "pre_confirm_wait_seconds": 12,
                "running_markers": ["Researching", "Searching", "Sources"],
                "completion_markers": ["Sources", "Answer", "Completed"],
                "output_selectors": ["main", "article"],
            },
        },
        "grok": {
            "chat": {
                "feature_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": [],
                "attachment_triggers": ["Attach", "Upload", "Add file"],
                "running_markers": ["Generating", "Search"],
                "completion_markers": ["Sources", "Answer"],
                "output_selectors": ["main", "article"],
            },
            "research": {
                "feature_triggers": ["DeepSearch", "Deep Search", "Search", "Think"],
                "menu_triggers": [],
                "pre_prompt_triggers": ["New Chat"],
                "attachment_triggers": ["Attach", "Upload", "Add file"],
                "slash_triggers": [],
                "confirmation_triggers": ["Start", "Submit"],
                "pre_confirm_wait_seconds": 12,
                "running_markers": ["DeepSearch", "Searching", "Thinking"],
                "completion_markers": ["Sources", "Answer", "Completed"],
                "output_selectors": ["main", "article"],
            },
        },
        "claude": {
            "chat": {
                "feature_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": [],
                "attachment_triggers": ["Attach", "Upload", "Add file"],
                "running_markers": ["Claude", "Generating"],
                "completion_markers": ["Response", "Done"],
                "output_selectors": ["main", "article"],
            },
            "research": {
                "feature_triggers": ["Research", "Search"],
                "pre_prompt_triggers": [],
                "slash_triggers": [],
                "confirmation_triggers": ["Start", "Continue"],
                "pre_confirm_wait_seconds": 20,
                "running_markers": ["Research", "Searching", "Sources"],
                "completion_markers": ["Sources", "Done", "Completed"],
                "output_selectors": ["main", "article"],
            },
            "artifacts": {
                "feature_triggers": ["Artifacts", "Create"],
                "slash_triggers": [],
                "confirmation_triggers": ["Create", "Start"],
                "running_markers": ["Artifact", "Preview"],
                "completion_markers": ["Artifact", "Preview"],
                "output_selectors": ["main", "article"],
            },
        },
    }


def provider_workflow_spec(provider: str, mode: str) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    mode_id = "research" if provider_id in {"perplexity", "grok", "claude"} and mode == "deep-research" else mode
    specs = provider_workflow_specs()
    provider_specs = specs.get(provider_id, {})
    if mode_id not in provider_specs:
        raise ValueError(f"unsupported workflow mode for {provider_id}: {mode}")
    spec = dict(provider_specs[mode_id])
    spec["provider"] = provider_id
    spec["mode"] = mode_id
    spec.setdefault("menu_triggers", [])
    spec.setdefault("pre_prompt_triggers", [])
    spec.setdefault("attachment_triggers", [])
    spec.setdefault("pre_confirm_wait_seconds", 12)
    spec["composer_selector"] = provider_composer_selector(provider_id)
    spec["url"] = provider_url(provider_id)
    return spec


def build_ai_workflow_plan(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    mode: str,
    prompt: str,
    artifact_root: Path,
    clone_root: Path,
    submit: bool = False,
    confirm_start: bool = False,
    wait_seconds: int = 30,
    attachments: list[Path] | None = None,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    profile_directory = str(profile.get("directory", "Default"))
    spec = provider_workflow_spec(provider_id, mode)
    actions: list[dict[str, Any]] = [
        {"label": "open-provider", "target": spec["url"]},
        {"label": "capture-before", "tool": "snapshot+visible-text+screenshot"},
    ]
    if spec.get("feature_triggers"):
        if spec.get("pre_prompt_triggers"):
            actions.append({"label": "pre-prompt-trigger", "triggers": spec.get("pre_prompt_triggers", [])})
        if spec.get("menu_triggers"):
            actions.append({"label": "open-feature-menu", "triggers": spec.get("menu_triggers", [])})
        actions.append({"label": "select-feature", "triggers": spec["feature_triggers"], "slash_fallbacks": spec.get("slash_triggers", [])})
    actions.append({"label": "fill-prompt", "composer_selector": spec["composer_selector"], "prompt_preview": prompt[:160]})
    if attachments:
        actions.append(
            {
                "label": "attach-files",
                "method": "cdp-dom-set-file-input-files",
                "menu_triggers": spec.get("attachment_triggers", []),
                "files": [str(path.expanduser()) for path in attachments],
                "file_count": len(attachments),
            }
        )
    if submit:
        actions.append({"label": "submit-prompt", "key": "Enter"})
    if submit and confirm_start and spec.get("confirmation_triggers"):
        actions.append(
            {
                "label": "confirm-start",
                "triggers": spec["confirmation_triggers"],
                "poll_seconds": spec.get("pre_confirm_wait_seconds", 12),
                "exact_controls_only": True,
            }
        )
    actions.append({"label": "wait-for-run", "seconds": wait_seconds, "markers": spec.get("running_markers", [])})
    actions.append({"label": "extract-output", "selectors": spec.get("output_selectors", [])})
    return {
        "provider": provider_id,
        "mode": spec["mode"],
        "browser": browser_id,
        "browser_name": browser.get("display_name", ""),
        "profile": profile_directory,
        "profile_name": profile.get("name", ""),
        "submit": submit,
        "confirm_start": confirm_start,
        "wait_seconds": wait_seconds,
        "attachments": [str(path.expanduser()) for path in attachments or []],
        "artifact_root": str(artifact_root.expanduser()),
        "clone_root": str(clone_root.expanduser()),
        "isolation": "temporary-profile-clone-cdp",
        "safety": {
            "uses_profile_clone": True,
            "does_not_close_existing_browser_windows": True,
            "terminates_only_launched_clone_process": True,
            "does_not_read_cookie_values": True,
        },
        "workflow_spec": spec,
        "actions": actions,
    }


def build_live_ai_workflow_plan(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    mode: str,
    prompt: str,
    artifact_root: Path,
    cdp_port: int,
    submit: bool = False,
    confirm_start: bool = False,
    wait_seconds: int = 30,
    attachments: list[Path] | None = None,
) -> dict[str, Any]:
    plan = build_ai_workflow_plan(
        browser=browser,
        profile=profile,
        provider=provider,
        mode=mode,
        prompt=prompt,
        artifact_root=artifact_root,
        clone_root=Path(""),
        submit=submit,
        confirm_start=confirm_start,
        wait_seconds=wait_seconds,
        attachments=attachments,
    )
    live_plan = dict(plan)
    live_plan["clone_root"] = ""
    live_plan["cdp_port"] = int(cdp_port)
    live_plan["isolation"] = "live-cdp-background-tab"
    live_plan["safety"] = {
        "uses_profile_clone": False,
        "requires_existing_cdp_session": True,
        "opens_new_tab_only": True,
        "does_not_close_existing_browser_windows": True,
        "does_not_close_existing_tabs": True,
        "leaves_automation_tab_open": True,
        "does_not_read_cookie_values": True,
    }
    live_plan["actions"] = [
        {"label": "open-background-tab", "tool": "agent-browser tab new", "target": live_plan["workflow_spec"]["url"]},
        *[action for action in plan["actions"] if action["label"] != "open-provider"],
    ]
    return live_plan


def extract_workflow_output_from_text(text: str, *, provider: str, mode: str) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    spec = provider_workflow_spec(provider_id, mode)
    expanded = expand_agent_browser_eval_text(text or "")
    markers = [str(marker) for marker in spec.get("completion_markers", [])]
    running_markers = [str(marker) for marker in spec.get("running_markers", [])]
    status = "empty"
    if expanded.strip():
        status = "captured"
    if any(marker.lower() in expanded.lower() for marker in running_markers):
        status = "running"
    if any(marker.lower() in expanded.lower() for marker in markers):
        status = "complete"
    lines = [line.rstrip() for line in expanded.splitlines()]
    collapsed = "\n".join(line for line in lines if line.strip())
    return {
        "provider": provider_id,
        "mode": spec["mode"],
        "status": status,
        "completion_markers_found": [marker for marker in markers if marker.lower() in expanded.lower()],
        "running_markers_found": [marker for marker in running_markers if marker.lower() in expanded.lower()],
        "text": collapsed,
        "text_length": len(collapsed),
    }


def browser_eval_body_and_report_script(selectors: list[str]) -> str:
    selectors_json = json.dumps(selectors)
    return (
        "(() => {"
        f"const selectors = {selectors_json};"
        "const parts = [];"
        "const pushText = (text) => {"
        "  const clean = String(text || '').trim();"
        "  if (clean && !parts.includes(clean)) parts.push(clean.slice(0, 20000));"
        "};"
        "for (const selector of selectors) {"
        "  for (const el of Array.from(document.querySelectorAll(selector)).slice(-8)) {"
        "    pushText(el.innerText || el.textContent || '');"
        "  }"
        "}"
        "pushText(document.body && document.body.innerText || '');"
        "return parts.join('\\n\\n--- BODY ---\\n\\n').slice(0, 60000);"
        "})()"
    )


def browser_eval_visible_text_script(max_chars: int = 60000) -> str:
    return (
        "(() => {"
        "const root = document.querySelector('main') || document.body;"
        "const text = (root && (root.innerText || root.textContent) || '').trim();"
        f"return text.slice(0, {int(max_chars)});"
        "})()"
    )


def wait_milliseconds(seconds: float, *, minimum_ms: int = 1000, maximum_ms: int | None = None) -> str:
    milliseconds = int(round(seconds * 1000))
    if maximum_ms is not None:
        milliseconds = min(milliseconds, maximum_ms)
    return str(max(minimum_ms, milliseconds))


def composer_js_fill_script(text: str) -> str:
    text_json = json.dumps(text)
    return (
        "(() => {"
        f"const text = {text_json};"
        "const selectors = ['textarea', 'input[type=\"text\"]', '[contenteditable=\"true\"]', '[role=\"textbox\"]'];"
        "const seen = new Set();"
        "const candidates = [];"
        "for (const selector of selectors) {"
        "  for (const el of document.querySelectorAll(selector)) {"
        "    if (seen.has(el)) continue;"
        "    seen.add(el);"
        "    const rect = el.getBoundingClientRect();"
        "    const style = window.getComputedStyle(el);"
        "    const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';"
        "    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';"
        "    if (visible && !disabled) candidates.push({el, rect});"
        "  }"
        "}"
        "if (!candidates.length) return {ok:false, reason:'no-composer'};"
        "candidates.sort((a, b) => (b.rect.bottom - a.rect.bottom) || ((b.rect.width * b.rect.height) - (a.rect.width * a.rect.height)));"
        "const el = candidates[0].el;"
        "el.focus();"
        "if (el.isContentEditable) {"
        "  el.innerText = text;"
        "  const range = document.createRange();"
        "  range.selectNodeContents(el);"
        "  range.collapse(false);"
        "  const selection = window.getSelection();"
        "  selection.removeAllRanges();"
        "  selection.addRange(range);"
        "} else {"
        "  el.value = text;"
        "  if (typeof el.setSelectionRange === 'function') el.setSelectionRange(text.length, text.length);"
        "}"
        "el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}));"
        "el.dispatchEvent(new Event('change', {bubbles:true}));"
        "return {ok:true, tag:el.tagName, role:el.getAttribute('role') || '', textLength:text.length};"
        "})()"
    )


def find_snapshot_ref(
    snapshot: str,
    label: str,
    *,
    roles: tuple[str, ...] = ("button", "menuitem", "option", "textbox", "link"),
    exact_only: bool = False,
) -> str:
    escaped = re.escape(label)
    for role in roles:
        pattern = rf"- {re.escape(role)} \"{escaped}\"(?:\s|\[).*?\[ref=([^\]]+)\]"
        match = re.search(pattern, snapshot)
        if match:
            return match.group(1)
    if exact_only or label.lower() in {"start", "confirm", "allow", "begin"}:
        return ""
    for role in roles:
        pattern = rf"- {re.escape(role)} \"[^\"]*{escaped}[^\"]*\"(?:\s|\[).*?\[ref=([^\]]+)\]"
        match = re.search(pattern, snapshot, flags=re.I)
        if match:
            full_label_match = re.search(rf"- {re.escape(role)} \"([^\"]*{escaped}[^\"]*)\"", match.group(0), flags=re.I)
            full_label = full_label_match.group(1).lower() if full_label_match else ""
            if any(blocked in full_label for blocked in ["dictation", "voice"]):
                continue
            return match.group(1)
    return ""


def find_confirmation_ref(snapshot: str, labels: list[str]) -> str:
    for label in labels:
        ref = find_snapshot_ref(
            snapshot,
            str(label),
            roles=("button", "menuitem", "menuitemradio", "option"),
            exact_only=True,
        )
        if ref:
            return ref
    return ""


def click_text_js_script(label: str) -> str:
    label_json = json.dumps(label)
    return (
        "(() => {"
        f"const wanted = {label_json}.trim().toLowerCase();"
        "const blocked = ['dictation', 'voice'];"
        "const candidates = Array.from(document.querySelectorAll('button, [role=\"button\"], [role=\"menuitem\"], [role=\"menuitemradio\"], [role=\"option\"], a, [aria-label], [data-testid]'));"
        "for (const el of candidates) {"
        "  const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();"
        "  if (!text) continue;"
        "  const lower = text.toLowerCase();"
        "  if (blocked.some(item => lower.includes(item))) continue;"
        "  if (lower === wanted || lower.includes(wanted)) {"
        "    const rect = el.getBoundingClientRect();"
        "    const style = window.getComputedStyle(el);"
        "    if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden' || style.display === 'none') continue;"
        "    el.scrollIntoView({block:'center', inline:'center'});"
        "    for (const type of ['pointerdown','mousedown','pointerup','mouseup','click']) {"
        "      el.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window, clientX:rect.left + rect.width / 2, clientY:rect.top + rect.height / 2}));"
        "    }"
        "    if (typeof el.click === 'function') el.click();"
        "    return {ok:true, text, tag:el.tagName, role:el.getAttribute('role') || ''};"
        "  }"
        "}"
        "return {ok:false, reason:'not-found', label:wanted};"
        "})()"
    )


def find_composer_ref(snapshot: str) -> str:
    for label in ["Chat with ChatGPT", "Message ChatGPT", "Ask anything", "Ask Perplexity", "Prompt eingeben", "How can I help"]:
        ref = find_snapshot_ref(snapshot, label, roles=("textbox",))
        if ref:
            return ref
    match = re.search(r"- textbox \"[^\"]*\".*?\[ref=([^\]]+)\]", snapshot)
    return match.group(1) if match else ""


def agent_browser_ask_export(
    *,
    cdp_port: int,
    provider: str,
    prompt: str,
    artifact_root: Path,
    browser: str,
    profile: str,
    session: str = "",
    submit: bool = False,
    timeout: float = 90.0,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    paths = build_artifact_paths(artifact_root, provider=provider_id, mode="ask", browser=browser, profile=profile)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=timeout)
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
    before = invoke("snapshot-before", ["snapshot", "-i", "-c"])
    before_text = before.stdout
    inventory = extract_provider_inventory(provider_id, before_text)
    if inventory.get("login_state") == "signed-out-or-wall":
        payload = {
            "provider": provider_id,
            "browser": normalize_browser_name(browser),
            "profile": profile,
            "status": "signed-out-or-wall",
            "inventory": inventory,
            "commands": commands,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        (paths["run_dir"] / "visible-text.txt").write_text(before_text, encoding="utf-8")
        return {**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}

    selector = provider_composer_selector(provider_id)
    fill_result = invoke("fill-composer", ["fill", selector, prompt])
    if submit and fill_result.returncode == 0:
        invoke("submit", ["press", "Enter"])
        invoke("wait-after-submit", ["wait", "12000"])
    after = invoke("snapshot-after", ["snapshot", "-i", "-c"])
    text = "\n".join(part for part in [before_text, after.stdout] if part)
    screenshot = paths["screenshot_png"]
    invoke("screenshot", ["screenshot", str(screenshot)])
    (paths["run_dir"] / "visible-text.txt").write_text(text, encoding="utf-8")

    cache_payload = None
    current_url = invoke("get-url", ["get", "url"]).stdout.strip()
    if cache_root:
        record = save_chat_record(
            cache_root=cache_root,
            browser=browser,
            profile=profile,
            provider=provider_id,
            chat_url=current_url or provider_url(provider_id),
            title=f"{provider_id} ask export",
            text=text,
            source="agent-browser-cdp",
            refresh=True,
        )
        cache_payload = {
            "key": record["key"],
            "metadata_path": str(record["metadata_path"]),
            "text_path": str(record["text_path"]),
        }

    payload = {
        "provider": provider_id,
        "browser": normalize_browser_name(browser),
        "profile": profile,
        "status": "submitted" if submit and fill_result.returncode == 0 else "filled",
        "submit": submit,
        "composer_selector": selector,
        "chat_url": current_url,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "inventory": extract_provider_inventory(provider_id, text),
        "cache": cache_payload,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    return {**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, int(port))) == 0
    except OSError:
        return False


def endpoint_version(port: int, host: str = "127.0.0.1") -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=1.5) as response:
            return json.load(response)
    except Exception:
        return None


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except PermissionError as exc:
        return subprocess.CompletedProcess(cmd, 126, "", str(exc))


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


def default_sibling_user_data_dir(*, browser: str, profile: str) -> Path:
    return (
        Path(os.environ.get("AI_RESEARCH_BROWSER_SIBLING_ROOT", "~/.cache/ai-research-browser/sibling-profiles")).expanduser()
        / f"{slug(normalize_browser_name(browser))}-{slug(profile)}"
        / "user-data"
    )


def clean_sibling_profile_locks(sibling_user_data: Path, profile_directory: str) -> list[str]:
    root = sibling_user_data.expanduser()
    profile_root = root / profile_directory
    candidates = [
        root / "SingletonLock",
        root / "SingletonSocket",
        root / "SingletonCookie",
        root / "DevToolsActivePort",
        root / "Lock",
        root / "lockfile",
        profile_root / "SingletonLock",
        profile_root / "SingletonSocket",
        profile_root / "SingletonCookie",
        profile_root / "DevToolsActivePort",
        profile_root / "LOCK",
        profile_root / "Lock",
        profile_root / "lockfile",
    ]
    removed: list[str] = []
    for path in candidates:
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
                removed.append(str(path))
        except OSError:
            continue
    return removed


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


def default_workflow_prompt(provider: str, mode: str) -> str:
    provider_id = normalize_provider_name(provider)
    prompts = {
        ("chatgpt", "agent"): "E2E smoke test: confirm ChatGPT Agent mode is active and respond with one short sentence saying the workflow started.",
        ("chatgpt", "deep-research"): "Use ChatGPT Deep Research to research safe browser automation practices in 2026. Create a concise report with sources. If a plan appears, start the research.",
        ("chatgpt", "chat"): "E2E smoke test: answer one short sentence confirming ChatGPT chat is usable.",
        ("gemini", "deep-research"): "Use Gemini Deep Research to research safe browser automation practices in 2026. Create a concise report with sources. If a plan appears, start the research.",
        ("gemini", "agent"): "E2E smoke test: confirm whether Gemini Agent mode is available and respond with one short sentence.",
        ("gemini", "chat"): "E2E smoke test: answer one short sentence confirming Gemini chat is usable.",
        ("perplexity", "research"): "E2E smoke test: use research mode for one concise note on safe browser automation with sources.",
        ("perplexity", "chat"): "E2E smoke test: answer one short sentence confirming Perplexity chat is usable.",
        ("grok", "research"): "E2E smoke test: use the strongest available search or research mode and write one short sentence on safe browser automation.",
        ("grok", "chat"): "E2E smoke test: answer one short sentence confirming Grok chat is usable.",
        ("claude", "research"): "E2E smoke test: use Claude research or search mode and answer one sentence about safe browser automation.",
        ("claude", "artifacts"): "E2E smoke test: create a tiny artifact or explain in one sentence whether artifacts are available.",
        ("claude", "chat"): "E2E smoke test: answer one short sentence confirming Claude chat is usable.",
    }
    return prompts.get((provider_id, mode), f"E2E smoke test: confirm {provider_id} {mode} is usable in one short sentence.")


def workflow_suite_targets(
    *,
    providers: list[str] | None = None,
    features: str = "",
    include_all_features: bool = False,
) -> list[dict[str, Any]]:
    provider_filter = {normalize_provider_name(provider) for provider in providers or []}
    supported_specs = provider_workflow_specs()
    if features:
        targets = []
        for raw in features.split(","):
            item = raw.strip()
            if not item:
                continue
            if ":" in item:
                provider_id, mode = item.split(":", 1)
            else:
                provider_id, mode = "", item
            provider_id = normalize_provider_name(provider_id) if provider_id else ""
            for candidate_provider, modes in supported_specs.items():
                if provider_id and candidate_provider != provider_id:
                    continue
                if mode in modes:
                    targets.append({"provider": candidate_provider, "mode": mode})
        return [
            {
                **target,
                "prompt": default_workflow_prompt(str(target["provider"]), str(target["mode"])),
            }
            for target in targets
            if not provider_filter or target["provider"] in provider_filter
        ]

    if include_all_features:
        targets = [
            {"provider": provider_id, "mode": mode, "prompt": default_workflow_prompt(provider_id, mode)}
            for provider_id, modes in supported_specs.items()
            if not provider_filter or provider_id in provider_filter
            for mode in modes
        ]
        return targets

    preferred = [
        ("chatgpt", "agent"),
        ("chatgpt", "deep-research"),
        ("gemini", "deep-research"),
        ("perplexity", "research"),
        ("grok", "research"),
        ("claude", "research"),
    ]
    return [
        {"provider": provider_id, "mode": mode, "prompt": default_workflow_prompt(provider_id, mode)}
        for provider_id, mode in preferred
        if provider_id in supported_specs and mode in supported_specs[provider_id] and (not provider_filter or provider_id in provider_filter)
    ]


def build_workflow_suite_rows(
    browsers: list[dict[str, Any]],
    *,
    providers: list[str] | None = None,
    browser_ids: set[str] | None = None,
    profile_selector: str = "work",
    all_profiles: bool = False,
    features: str = "",
    include_all_features: bool = False,
) -> list[dict[str, Any]]:
    targets = workflow_suite_targets(providers=providers, features=features, include_all_features=include_all_features)
    rows: list[dict[str, Any]] = []
    for browser in browsers:
        browser_id = normalize_browser_name(str(browser.get("id", "")))
        if browser_ids and browser_id not in browser_ids:
            continue
        profiles = list(browser.get("profiles") or [])
        if not profiles:
            rows.append(
                {
                    "browser": browser_id,
                    "browser_name": browser.get("display_name", ""),
                    "profile_directory": "",
                    "profile_name": "",
                    "status": "skipped",
                    "skip_reason": "no profiles discovered",
                }
            )
            continue
        if not all_profiles:
            try:
                profiles = [resolve_profile(profiles, profile_selector)]
            except ValueError:
                rows.append(
                    {
                        "browser": browser_id,
                        "browser_name": browser.get("display_name", ""),
                        "profile_directory": profile_selector,
                        "profile_name": "",
                        "status": "skipped",
                        "skip_reason": f"profile not found: {profile_selector}",
                    }
                )
                continue
        for profile in profiles:
            for target in targets:
                session_evidence = provider_session_evidence(profile, str(target["provider"]))
                rows.append(
                    {
                        "browser": browser_id,
                        "browser_name": browser.get("display_name", ""),
                        "profile_directory": profile.get("directory", ""),
                        "profile_name": profile.get("name", ""),
                        "profile_account": profile.get("account", ""),
                        "profile_account_state": profile.get("account_state", ""),
                        "provider": target["provider"],
                        "mode": target["mode"],
                        "prompt": target["prompt"],
                        "session_evidence": session_evidence,
                        "status": "queued" if session_evidence.get("confidence") != "none" else "needs-login",
                    }
                )
    return rows


PROFILE_CLONE_EXCLUDES = {
    "Singleton*",
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    "DevToolsActivePort",
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
    "com.google.Chrome.code_sign_clone",
}


def is_allowed_extension_profile_path(path: Path, extension_ids: set[str]) -> bool:
    if not extension_ids:
        return False
    parts = list(path.parts)
    lower_ids = {item.lower() for item in extension_ids}
    for root_name in ["Extensions", "Local Extension Settings", "Sync Extension Settings", "Managed Extension Settings"]:
        if root_name in parts:
            index = parts.index(root_name)
            return len(parts) > index + 1 and parts[index + 1].lower() in lower_ids
    if parts and parts[0] == "Extension State":
        return True
    return False


def should_exclude_profile_path(path: Path, *, extension_ids: set[str] | None = None) -> bool:
    allowed_extension_ids = extension_ids or set()
    if is_allowed_extension_profile_path(path, allowed_extension_ids):
        return False
    parts = set(path.parts)
    name = path.name
    if name.startswith("Singleton"):
        return True
    if name == "DevToolsActivePort":
        return True
    if name == "com.google.Chrome.code_sign_clone":
        return True
    if name in {"Lock", "lockfile"}:
        return True
    if any(part in {"Crashpad", "Code Cache", "DawnCache", "GrShaderCache", "GraphiteDawnCache", "GPUCache", "ShaderCache", "Cache", "Media Cache", "Extensions", "Extension State"} for part in parts):
        return True
    if "Service Worker" in parts and "CacheStorage" in parts:
        return True
    if path.suffix == ".blob" and "IndexedDB" in parts:
        return True
    return False


def copy_profile_tree(src: Path, dst: Path, *, extension_ids: set[str] | None = None) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        relative = item.relative_to(src)
        target = dst / relative
        if should_exclude_profile_path(relative, extension_ids=extension_ids):
            continue
        if item.is_dir():
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
        except OSError:
            continue


def clone_browser_profile_for_agent_browser(
    browser: dict[str, Any],
    profile: dict[str, str],
    clone_root: Path,
    *,
    run_slug: str,
    include_extension_ids: list[str] | None = None,
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
    extension_ids = {item.lower() for item in include_extension_ids or []}
    copy_profile_tree(source_profile, clone_profile, extension_ids=extension_ids)
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
        "included_extension_ids": sorted(extension_ids),
    }


def prepare_sibling_profile(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    sibling_user_data: Path,
    refresh: bool = False,
    include_extension_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_user_data = Path(str(browser.get("user_data_dir", ""))).expanduser()
    profile_directory = str(profile.get("directory", "Default"))
    source_profile = Path(str(profile.get("path") or source_user_data / profile_directory)).expanduser()
    sibling_user_data = sibling_user_data.expanduser()
    sibling_profile = sibling_user_data / profile_directory
    if not source_profile.exists():
        return {
            "ok": False,
            "status": "blocked",
            "error": f"profile source does not exist: {source_profile}",
            "source_profile": str(source_profile),
            "sibling_user_data": str(sibling_user_data),
            "sibling_profile": str(sibling_profile),
        }
    status = "reused"
    if refresh and sibling_user_data.exists():
        shutil.rmtree(sibling_user_data, ignore_errors=True)
    if not sibling_profile.exists():
        sibling_user_data.mkdir(parents=True, exist_ok=True)
        extension_ids = {item.lower() for item in include_extension_ids or []}
        copy_profile_tree(source_profile, sibling_profile, extension_ids=extension_ids)
        for filename in ["Local State", "First Run"]:
            source_file = source_user_data / filename
            if source_file.exists():
                try:
                    shutil.copy2(source_file, sibling_user_data / filename)
                except OSError:
                    pass
        status = "refreshed" if refresh else "seeded"
    removed_locks = clean_sibling_profile_locks(sibling_user_data, profile_directory)
    return {
        "ok": True,
        "status": status,
        "source_user_data": str(source_user_data),
        "source_profile": str(source_profile),
        "sibling_user_data": str(sibling_user_data),
        "sibling_profile": str(sibling_profile),
        "profile_directory": profile_directory,
        "removed_locks": removed_locks,
        "included_extension_ids": sorted({item.lower() for item in include_extension_ids or []}),
        "safety": {
            "source_browser_left_running": True,
            "source_profile_not_used_for_launch": True,
            "cookie_values_not_read": True,
        },
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


def find_available_port() -> int:
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if not is_port_open(port, "127.0.0.1") and not is_port_open(port, "::1"):
            return port
    raise RuntimeError("Could not find a free loopback CDP port")


def build_clone_cdp_launch_args(
    browser: dict[str, Any],
    *,
    clone_user_data: str,
    profile_directory: str,
    port: int,
    headless: bool = True,
    initial_url: str = "about:blank",
    extension_paths: list[str] | None = None,
) -> list[str]:
    args = [
        str(browser.get("binary_path", "")),
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={int(port)}",
        f"--user-data-dir={clone_user_data}",
        f"--profile-directory={profile_directory}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--disable-remote-fonts",
    ]
    if headless:
        args.append("--headless=new")
    if extension_paths:
        extension_arg = ",".join(str(path) for path in extension_paths if path)
        if extension_arg:
            args.extend([f"--disable-extensions-except={extension_arg}", f"--load-extension={extension_arg}"])
    args.append(initial_url)
    return args


def build_sibling_cdp_launch_args(
    browser: dict[str, Any],
    *,
    sibling_user_data: str,
    profile_directory: str,
    port: int,
    provider: str,
    headless: bool = False,
    extension_paths: list[str] | None = None,
) -> list[str]:
    args = [
        str(browser.get("binary_path", "")),
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={int(port)}",
        f"--user-data-dir={sibling_user_data}",
        f"--profile-directory={profile_directory}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--disable-remote-fonts",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--restore-last-session=false",
    ]
    if headless:
        args.append("--headless=new")
    else:
        args.extend(["--window-position=-9999,0", "--window-size=1400,1000"])
    if extension_paths:
        extension_arg = ",".join(str(path) for path in extension_paths if path)
        if extension_arg:
            args.extend([f"--disable-extensions-except={extension_arg}", f"--load-extension={extension_arg}"])
    args.append(provider_url(provider))
    return args


def start_clone_cdp_browser(
    *,
    launch_args: list[str],
    port: int,
    log_path: Path,
    startup_timeout: float = 12.0,
) -> tuple[subprocess.Popen[str] | None, dict[str, Any]]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(launch_args, stdout=log_file, stderr=log_file, text=True, start_new_session=True)
    except OSError as exc:
        log_file.close()
        return None, {"ok": False, "error": str(exc), "launch_args": launch_args, "port": port}
    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if is_port_open(port):
            log_file.close()
            return process, {"ok": True, "pid": process.pid, "port": port, "launch_args": launch_args, "log_path": str(log_path)}
        if process.poll() is not None:
            break
        time.sleep(0.2)
    exit_code = process.poll()
    if exit_code is None:
        process.terminate()
    log_file.close()
    return process, {"ok": False, "pid": process.pid, "port": port, "exit_code": exit_code, "launch_args": launch_args, "log_path": str(log_path)}


def start_sibling_cdp_browser(
    *,
    launch_args: list[str],
    port: int,
    log_path: Path,
    startup_timeout: float = 12.0,
) -> tuple[subprocess.Popen[str] | None, dict[str, Any]]:
    return start_clone_cdp_browser(launch_args=launch_args, port=port, log_path=log_path, startup_timeout=startup_timeout)


def terminate_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def capture_cdp_screenshot(port: int, screenshot: Path, *, timeout: float = 20.0) -> bool:
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    script = r"""
const [base, out] = process.argv.slice(1);
const targets = await (await fetch(`${base}/json/list`)).json();
const target = targets.find((item) => item.type === 'page' && !String(item.url || '').startsWith('about:blank')) || targets.find((item) => item.type === 'page');
if (!target || !target.webSocketDebuggerUrl) throw new Error('No page target for CDP screenshot');
const ws = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
const timer = setTimeout(() => {
  console.error('Timed out waiting for CDP screenshot');
  process.exit(2);
}, 15000);
ws.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  if (!payload.id || !pending.has(payload.id)) return;
  const {resolve, reject} = pending.get(payload.id);
  pending.delete(payload.id);
  if (payload.error) reject(new Error(JSON.stringify(payload.error)));
  else resolve(payload.result || {});
});
function send(method, params = {}) {
  const id = ++nextId;
  ws.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
await send('Page.enable');
const result = await send('Page.captureScreenshot', {format: 'png', fromSurface: true, captureBeyondViewport: false});
const fs = await import('node:fs');
fs.writeFileSync(out, Buffer.from(result.data, 'base64'));
clearTimeout(timer);
ws.close();
"""
    result = subprocess.run(["node", "--input-type=module", "-e", script, cdp_http_base_for_port(port), str(screenshot)], capture_output=True, text=True, timeout=timeout)
    return result.returncode == 0 and screenshot.exists() and screenshot.stat().st_size > 0


def set_cdp_file_input_files(port: int, files: list[Path], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    expanded_files = [str(path.expanduser().resolve()) for path in files if path.expanduser().exists()]
    script = r"""
const [base, filesJson] = process.argv.slice(1);
const files = JSON.parse(filesJson);
const targets = await (await fetch(`${base}/json/list`)).json();
const target = targets.find((item) => item.type === 'page' && !String(item.url || '').startsWith('about:blank')) || targets.find((item) => item.type === 'page');
if (!target || !target.webSocketDebuggerUrl) throw new Error('No page target for CDP file upload');
const ws = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++nextId;
  pending.set(id, {resolve, reject});
  ws.send(JSON.stringify({id, method, params}));
});
const done = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('Timed out waiting for CDP file upload')), 15000);
  ws.addEventListener('message', (event) => {
    const payload = JSON.parse(event.data);
    if (!payload.id || !pending.has(payload.id)) return;
    const item = pending.get(payload.id);
    pending.delete(payload.id);
    if (payload.error) item.reject(new Error(payload.error.message || JSON.stringify(payload.error)));
    else item.resolve(payload.result || {});
  });
  ws.addEventListener('open', async () => {
    try {
      const documentResult = await send('DOM.getDocument', {depth: -1, pierce: true});
      const rootNodeId = documentResult.root && documentResult.root.nodeId;
      const inputResult = await send('DOM.querySelector', {nodeId: rootNodeId, selector: 'input[type=file]'});
      if (!inputResult.nodeId) {
        clearTimeout(timer);
        resolve({ok: false, reason: 'no-file-input'});
        ws.close();
        return;
      }
      await send('DOM.setFileInputFiles', {nodeId: inputResult.nodeId, files});
      clearTimeout(timer);
      resolve({ok: true, fileCount: files.length});
      ws.close();
    } catch (error) {
      clearTimeout(timer);
      reject(error);
      ws.close();
    }
  });
  ws.addEventListener('error', (error) => {
    clearTimeout(timer);
    reject(error);
  });
});
const result = await done;
console.log(JSON.stringify(result));
"""
    if not expanded_files:
        return subprocess.CompletedProcess(["cdp-file-upload", str(port)], 1, "", "No existing attachment files")
    try:
        return subprocess.run(["node", "--input-type=module", "-e", script, cdp_http_base_for_port(port), json.dumps(expanded_files)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            ["node", "cdp-file-upload", str(port)],
            124,
            stdout=(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")) + f"\nTimed out after {timeout:.0f}s",
        )


def upload_cdp_attachments(
    *,
    port: int,
    attachments: list[Path] | None,
    commands: list[dict[str, Any]],
    workflow_events: list[dict[str, Any]],
    timeout: float,
    label: str = "attach-files",
) -> subprocess.CompletedProcess[str] | None:
    if not attachments:
        return None
    result = set_cdp_file_input_files(port, attachments, timeout=min(timeout, 20.0))
    file_paths = [str(path.expanduser()) for path in attachments]
    commands.append(
        {
            "label": label,
            "args": ["cdp-file-upload", str(port), *file_paths],
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
    )
    upload_event: dict[str, Any] = {
        "event": label,
        "returncode": result.returncode,
        "files": file_paths,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }
    try:
        upload_event["result"] = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    workflow_events.append(upload_event)
    return result


def prepare_and_upload_attachments(
    *,
    port: int,
    attachments: list[Path] | None,
    commands: list[dict[str, Any]],
    workflow_events: list[dict[str, Any]],
    timeout: float,
    invoke: Any,
    snapshot: str,
    menu_triggers: list[str],
    label: str = "attach-files",
) -> subprocess.CompletedProcess[str] | None:
    if not attachments:
        return None
    menu_result = click_first_agent_browser_text(
        invoke,
        menu_triggers,
        command_log_label=f"{label}-open-menu",
        snapshot=snapshot,
    )
    if menu_result.get("attempts") or menu_result.get("clicked"):
        workflow_events.append({"event": f"{label}-open-menu", **menu_result})
    if menu_result.get("clicked"):
        invoke(f"wait-after-{label}-menu", ["wait", "1000"])
    return upload_cdp_attachments(
        port=port,
        attachments=attachments,
        commands=commands,
        workflow_events=workflow_events,
        timeout=timeout,
        label=label,
    )


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
    cdp_port = find_available_port()
    launch_args = build_clone_cdp_launch_args(
        browser,
        clone_user_data=str(clone["clone_user_data"]),
        profile_directory=profile_directory,
        port=cdp_port,
        headless=True,
        initial_url="about:blank",
    )
    browser_process, launch_status = start_clone_cdp_browser(
        launch_args=launch_args,
        port=cdp_port,
        log_path=paths["run_dir"] / "browser-cdp.log",
    )
    if not launch_status.get("ok"):
        terminate_process(browser_process)
        payload = {
            "provider": provider_id,
            "mode": mode,
            "model": model,
            "browser": browser_id,
            "profile": profile_directory,
            "status": "blocked",
            "blocker": "browser clone CDP launch failed",
            "clone": clone,
            "cdp_port": cdp_port,
            "launch": launch_status,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    def invoke(label: str, extra_args: list[str], *, use_globals: bool = False) -> subprocess.CompletedProcess[str]:
        result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=timeout)
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--session", session, "--cdp", str(cdp_port), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    visible_text = ""
    try:
        open_result = invoke("open", ["open", provider_url(provider_id)], use_globals=True)
        if open_result.stdout:
            visible_text += open_result.stdout
        invoke("wait", ["wait", "3000"])
        snapshot = invoke("snapshot-interactive", ["snapshot", "-i", "-c"])
        if snapshot.stdout:
            visible_text += "\n" + snapshot.stdout
        eval_text_result = invoke("eval-visible-text", ["eval", "document.body.innerText"])
        if eval_text_result.stdout:
            visible_text += "\n" + eval_text_result.stdout
        if open_controls:
            hints = provider_probe_specs().get(provider_id, {})
            for label in [*hints.get("model_hints", [])[:2], *hints.get("tool_hints", [])[:2]]:
                invoke(f"try-open-control:{label}", ["find", "text", str(label), "click"])
                control_snapshot = invoke(f"snapshot-after:{label}", ["snapshot", "-i", "-c"])
                visible_text += "\n" + control_snapshot.stdout
        screenshot = paths["screenshot_png"]
        screenshot_result = invoke("screenshot", ["screenshot", str(screenshot)])
        if screenshot_result.returncode != 0:
            cdp_screenshot_ok = capture_cdp_screenshot(cdp_port, screenshot)
            commands.append(
                {
                    "label": "cdp-screenshot-fallback",
                    "args": ["node", "Page.captureScreenshot", str(cdp_port), str(screenshot)],
                    "returncode": 0 if cdp_screenshot_ok else 1,
                    "stdout": str(screenshot) if cdp_screenshot_ok else "",
                    "stderr": "",
                }
            )
        invoke("close", ["close"])
    finally:
        terminate_process(browser_process)

    inventory = extract_provider_inventory(provider_id, visible_text)
    login_state = inventory.get("login_state", "unknown")
    status = "captured"
    if any(command.get("returncode") == 124 for command in commands):
        status = "timeout"
    elif open_result.returncode != 0 or (snapshot.returncode != 0 and not visible_text.strip()):
        status = "failed"
    elif login_state == "signed-out-or-wall":
        status = "signed-out-or-wall"
    elif not screenshot.exists():
        status = "captured-without-screenshot"
    payload = {
        "provider": provider_id,
        "mode": mode,
        "model": model,
        "browser": browser_id,
        "profile": profile_directory,
        "status": status,
        "session": session,
        "clone": clone,
        "cdp_port": cdp_port,
        "launch": launch_status,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "inventory": inventory,
        "verification": verify_visible_text(visible_text, provider=provider_id, mode=mode) if visible_text else None,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    return {**payload, "status_json": str(paths["status_json"]), "visible_text_path": str(paths["run_dir"] / "visible-text.txt")}


def click_first_agent_browser_text(
    invoke: Any,
    labels: list[str],
    *,
    command_log_label: str,
    snapshot: str = "",
    prefer_js: bool = False,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for label in labels:
        if prefer_js and str(label).lower() not in {"start", "confirm", "allow", "begin"}:
            result = invoke(f"{command_log_label}:{label}:js-click", ["eval", click_text_js_script(str(label))])
            attempts.append({"label": label, "returncode": result.returncode, "method": "js"})
            if result.returncode == 0 and '"ok":false' not in result.stdout and "not-found" not in result.stdout:
                return {"clicked": True, "label": label, "attempts": attempts}
        ref = find_snapshot_ref(snapshot, str(label), roles=("button", "menuitem", "option", "link")) if snapshot else ""
        if ref:
            result = invoke(f"{command_log_label}:{label}", ["click", f"@{ref}"])
            attempts.append({"label": label, "ref": ref, "returncode": result.returncode})
            if result.returncode == 0:
                return {"clicked": True, "label": label, "ref": ref, "attempts": attempts}
            continue
        if str(label).lower() in {"start", "confirm", "allow", "begin"}:
            attempts.append({"label": label, "returncode": 1, "skipped": "generic-label-without-exact-ref"})
            continue
        result = invoke(f"{command_log_label}:{label}:js-click", ["eval", click_text_js_script(str(label))])
        attempts.append({"label": label, "returncode": result.returncode})
        if result.returncode == 0 and '"ok":false' not in result.stdout and "not-found" not in result.stdout:
            return {"clicked": True, "label": label, "attempts": attempts}
    return {"clicked": False, "label": "", "attempts": attempts}


def fill_agent_browser_composer(
    invoke: Any,
    *,
    snapshot: str,
    selector: str,
    text: str,
    label: str,
) -> subprocess.CompletedProcess[str]:
    js_result = invoke(f"{label}-js", ["eval", composer_js_fill_script(text)])
    if js_result.returncode == 0:
        return js_result
    ref = find_composer_ref(snapshot)
    if ref:
        result = invoke(label, ["fill", f"@{ref}", text])
        if result.returncode == 0:
            return result
    result = invoke(label, ["fill", selector, text])
    if result.returncode == 0:
        return result
    return invoke(f"{label}-js-fallback", ["eval", composer_js_fill_script(text)])


def agent_browser_profile_workflow_run(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    mode: str,
    prompt: str,
    artifact_root: Path,
    clone_root: Path,
    submit: bool = False,
    confirm_start: bool = False,
    wait_seconds: int = 30,
    timeout: float = 90.0,
    cache_root: Path | None = None,
    refresh_cache: bool = True,
    include_extension_ids: list[str] | None = None,
    attachments: list[Path] | None = None,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    spec = provider_workflow_spec(provider_id, mode)
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    profile_directory = str(profile.get("directory", "Default"))
    run_name = f"{browser_id}-{slug(profile_directory)}-{provider_id}-{slug(spec['mode'])}-workflow"
    paths = build_artifact_paths(artifact_root.expanduser(), provider=provider_id, mode=f"{spec['mode']}-workflow", browser=browser_id, profile=profile_directory)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    workflow_events: list[dict[str, Any]] = []
    plan = build_ai_workflow_plan(
        browser=browser,
        profile=profile,
        provider=provider_id,
        mode=spec["mode"],
        prompt=prompt,
        artifact_root=artifact_root,
        clone_root=clone_root,
        submit=submit,
        confirm_start=confirm_start,
        wait_seconds=wait_seconds,
        attachments=attachments,
    )

    clone = clone_browser_profile_for_agent_browser(
        browser,
        profile,
        clone_root,
        run_slug=run_name,
        include_extension_ids=include_extension_ids,
    )
    if not clone.get("ok"):
        payload = {
            **plan,
            "status": "blocked",
            "blocker": clone.get("error", "profile clone failed"),
            "clone": clone,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    session = f"ai-workflow-{run_name}"
    cdp_port = find_available_port()
    launch_args = build_clone_cdp_launch_args(
        browser,
        clone_user_data=str(clone["clone_user_data"]),
        profile_directory=profile_directory,
        port=cdp_port,
        headless=True,
        initial_url="about:blank",
        extension_paths=[item["path"] for item in discover_profile_extensions(profile, extension_ids=include_extension_ids)] if include_extension_ids else None,
    )
    browser_process, launch_status = start_clone_cdp_browser(
        launch_args=launch_args,
        port=cdp_port,
        log_path=paths["run_dir"] / "browser-cdp.log",
    )
    if not launch_status.get("ok"):
        terminate_process(browser_process)
        payload = {
            **plan,
            "status": "blocked",
            "blocker": "browser clone CDP launch failed",
            "clone": clone,
            "launch": launch_status,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    snapshot_timeout = max(8.0, min(timeout, 18.0))

    def command_timeout(label: str, extra_args: list[str]) -> float:
        if extra_args[:1] == ["snapshot"]:
            return snapshot_timeout
        if extra_args[:1] == ["open"]:
            return min(timeout, 15.0)
        if extra_args[:1] == ["eval"]:
            return min(timeout, 15.0)
        if extra_args == ["get", "url"]:
            return min(timeout, 8.0)
        if extra_args[:1] == ["press"]:
            return min(timeout, 10.0)
        if extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                return max(8.0, (int(str(extra_args[1])) / 1000.0) + 5.0)
            except ValueError:
                return min(timeout, 15.0)
        return timeout

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        if extra_args[:1] == ["open"] and len(extra_args) > 1:
            result = run_cdp_navigate(cdp_port, str(extra_args[1]), timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                milliseconds = int(str(extra_args[1]))
            except ValueError:
                milliseconds = 1000
            time.sleep(max(0, milliseconds) / 1000.0)
            result = subprocess.CompletedProcess(["sleep", str(milliseconds)], 0, f"waited {milliseconds}ms", "")
        elif extra_args[:1] == ["eval"] and len(extra_args) > 1:
            result = run_cdp_javascript(cdp_port, extra_args[1], timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["press"] and len(extra_args) > 1 and str(extra_args[1]).lower() in {"enter", "return"}:
            result = run_cdp_keypress(cdp_port, str(extra_args[1]), timeout=command_timeout(label, extra_args))
        elif extra_args == ["get", "url"]:
            result = run_cdp_javascript(cdp_port, "location.href", timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["screenshot"] and len(extra_args) > 1:
            ok = capture_cdp_screenshot(cdp_port, Path(extra_args[1]), timeout=min(timeout, 20.0))
            result = subprocess.CompletedProcess(["cdp-screenshot", str(cdp_port), extra_args[1]], 0 if ok else 1, str(extra_args[1]) if ok else "", "")
        elif extra_args[:1] == ["close"]:
            result = subprocess.CompletedProcess(["skip-close-temp-page"], 0, "skipped: browser process terminates in finally", "")
        else:
            result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=command_timeout(label, extra_args))
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--session", session, "--cdp", str(cdp_port), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    visible_text_parts: list[str] = []
    screenshot = paths["screenshot_png"]
    current_url = ""
    try:
        invoke("open-provider", ["open", spec["url"]])
        invoke("wait-initial", ["wait", "4000"])
        first_url = invoke("get-url-after-open", ["get", "url"]).stdout.strip()
        if first_url and not url_matches_provider(first_url, provider_id):
            workflow_events.append({"event": "provider-url-retry", "from_url": first_url, "to_url": spec["url"]})
            invoke("open-provider-retry", ["open", spec["url"]])
            invoke("wait-initial-retry", ["wait", "4000"])
        before_eval = invoke("eval-before-text", ["eval", browser_eval_visible_text_script()])
        visible_text_parts.append(before_eval.stdout)
        before_snapshot = invoke("snapshot-before", ["snapshot", "-i", "-c"])
        current_snapshot_text = before_snapshot.stdout
        visible_text_parts.append(current_snapshot_text)
        consent_result = click_first_agent_browser_text(
            invoke,
            ["Alle akzeptieren", "Alle annehmen", "Accept all", "I agree", "Agree", "Zustimmen"],
            command_log_label="consent",
            snapshot=current_snapshot_text,
            prefer_js=True,
        )
        if consent_result.get("clicked"):
            workflow_events.append({"event": "consent", **consent_result})
            invoke("wait-after-consent", ["wait", "2500"])
            consent_eval = invoke("eval-after-consent", ["eval", browser_eval_visible_text_script()])
            visible_text_parts.append(consent_eval.stdout)
            consent_snapshot = invoke("snapshot-after-consent", ["snapshot", "-i", "-c"])
            current_snapshot_text = consent_snapshot.stdout or current_snapshot_text
            visible_text_parts.append(current_snapshot_text)

        inventory = extract_provider_inventory(provider_id, "\n".join(visible_text_parts))
        if inventory.get("login_state") == "signed-out-or-wall":
            status = "signed-out-or-wall"
        else:
            status = "opened"
            feature_result = {"clicked": False, "label": "", "attempts": []}
            if spec.get("pre_prompt_triggers"):
                pre_prompt_result = click_first_agent_browser_text(
                    invoke,
                    list(spec.get("pre_prompt_triggers", [])),
                    command_log_label="pre-prompt-trigger",
                    snapshot=current_snapshot_text,
                )
                workflow_events.append({"event": "pre-prompt-trigger", **pre_prompt_result})
                if pre_prompt_result.get("clicked"):
                    invoke("wait-after-pre-prompt-trigger", ["wait", "1000"])
                    pre_prompt_snapshot = invoke("snapshot-after-pre-prompt-trigger", ["snapshot", "-i", "-c"])
                    current_snapshot_text = pre_prompt_snapshot.stdout or current_snapshot_text
                    visible_text_parts.append(current_snapshot_text)
            if spec.get("feature_triggers"):
                menu_result = click_first_agent_browser_text(
                    invoke,
                    list(spec.get("menu_triggers", [])),
                    command_log_label="open-feature-menu",
                    snapshot=current_snapshot_text,
                )
                if menu_result.get("clicked"):
                    workflow_events.append({"event": "open-feature-menu", **menu_result})
                    invoke("wait-after-feature-menu", ["wait", "1000"])
                    menu_snapshot = invoke("snapshot-after-feature-menu", ["snapshot", "-i", "-c"])
                    current_snapshot_text = menu_snapshot.stdout or current_snapshot_text
                    visible_text_parts.append(current_snapshot_text)
                feature_result = click_first_agent_browser_text(
                    invoke,
                    list(spec["feature_triggers"]),
                    command_log_label="select-feature",
                    snapshot=current_snapshot_text,
                )
                workflow_events.append({"event": "select-feature", **feature_result})
            if not feature_result.get("clicked") and spec.get("slash_triggers"):
                slash = str(spec["slash_triggers"][0])
                slash_result = fill_agent_browser_composer(
                    invoke,
                    snapshot=current_snapshot_text,
                    selector=spec["composer_selector"],
                    text=slash,
                    label="slash-feature",
                )
                workflow_events.append({"event": "slash-feature", "trigger": slash, "returncode": slash_result.returncode})
                if slash_result.returncode == 0:
                    invoke("slash-enter", ["press", "Enter"])
                    invoke("wait-after-slash", ["wait", "1500"])
                    slash_snapshot = invoke("snapshot-after-slash", ["snapshot", "-i", "-c"])
                    current_snapshot_text = slash_snapshot.stdout or current_snapshot_text

            fill_result = fill_agent_browser_composer(
                invoke,
                snapshot=current_snapshot_text,
                selector=spec["composer_selector"],
                text=prompt,
                label="fill-prompt",
            )
            workflow_events.append({"event": "fill-prompt", "returncode": fill_result.returncode})
            if fill_result.returncode == 0:
                prepare_and_upload_attachments(
                    port=cdp_port,
                    attachments=attachments,
                    commands=commands,
                    workflow_events=workflow_events,
                    timeout=timeout,
                    invoke=invoke,
                    snapshot=current_snapshot_text,
                    menu_triggers=list(spec.get("attachment_triggers", [])),
                )
            if submit and fill_result.returncode == 0:
                invoke("submit-prompt", ["press", "Enter"])
                status = "submitted"
                pre_confirm_wait_seconds = int(spec.get("pre_confirm_wait_seconds", 12))
                invoke("wait-after-submit", ["wait", str(max(1000, min(wait_seconds, 8) * 1000))])
                if confirm_start and spec.get("confirmation_triggers"):
                    confirm_attempts: list[dict[str, Any]] = []
                    confirm_result: dict[str, Any] = {"clicked": False, "label": "", "ref": "", "attempts": confirm_attempts}
                    confirm_deadline = time.monotonic() + max(1, pre_confirm_wait_seconds)
                    confirm_index = 0
                    while True:
                        confirm_snapshot = invoke(f"snapshot-before-confirm-{confirm_index}", ["snapshot", "-i", "-c"])
                        current_snapshot_text = confirm_snapshot.stdout or current_snapshot_text
                        visible_text_parts.append(current_snapshot_text)
                        exact_ref = find_confirmation_ref(current_snapshot_text, list(spec["confirmation_triggers"]))
                        exact_label = ""
                        if exact_ref:
                            for trigger_label in spec["confirmation_triggers"]:
                                if find_snapshot_ref(
                                    current_snapshot_text,
                                    str(trigger_label),
                                    roles=("button", "menuitem", "menuitemradio", "option"),
                                    exact_only=True,
                                ) == exact_ref:
                                    exact_label = str(trigger_label)
                                    break
                            click_result = invoke(f"confirm-start:{exact_label or exact_ref}", ["click", f"@{exact_ref}"])
                            confirm_attempts.append({"label": exact_label, "ref": exact_ref, "returncode": click_result.returncode})
                            if click_result.returncode == 0:
                                confirm_result = {
                                    "clicked": True,
                                    "label": exact_label,
                                    "ref": exact_ref,
                                    "attempts": confirm_attempts,
                                }
                                break
                        else:
                            marker_probe = extract_workflow_output_from_text(
                                current_snapshot_text,
                                provider=provider_id,
                                mode=spec["mode"],
                            )
                            specific_confirmation_labels = [
                                str(label)
                                for label in spec["confirmation_triggers"]
                                if str(label).strip().lower() not in {"start", "confirm", "allow", "begin", "submit"}
                            ]
                            js_confirm = click_first_agent_browser_text(
                                invoke,
                                specific_confirmation_labels,
                                command_log_label=f"confirm-start-js-{confirm_index}",
                                snapshot="",
                            )
                            if js_confirm.get("clicked"):
                                confirm_attempts.append(
                                    {
                                        "label": js_confirm.get("label", ""),
                                        "returncode": 0,
                                        "method": "cdp-js",
                                    }
                                )
                                confirm_result = {
                                    "clicked": True,
                                    "label": js_confirm.get("label", ""),
                                    "ref": "",
                                    "attempts": confirm_attempts,
                                }
                                break
                            confirm_attempts.append(
                                {
                                    "label": "",
                                    "returncode": 1,
                                    "skipped": "no-exact-confirmation-control",
                                    "marker_status": marker_probe["status"],
                                    "running_markers_found": marker_probe.get("running_markers_found", []),
                                }
                            )
                            if marker_probe["status"] == "running" and marker_probe.get("running_markers_found"):
                                confirm_result = {
                                    "clicked": False,
                                    "label": "",
                                    "ref": "",
                                    "running_marker_seen": True,
                                    "attempts": confirm_attempts,
                                }
                                break
                        remaining = confirm_deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        confirm_index += 1
                        invoke(f"wait-before-confirm-{confirm_index}", ["wait", wait_milliseconds(remaining, maximum_ms=3000)])
                    workflow_events.append({"event": "confirm-start", **confirm_result})
                    if confirm_result.get("clicked") or confirm_result.get("running_marker_seen"):
                        status = "started"
                        invoke("wait-after-confirm", ["wait", str(max(1000, min(wait_seconds, 30) * 1000))])

        after_snapshot = invoke("snapshot-after", ["snapshot", "-i", "-c"])
        visible_text_parts.append(after_snapshot.stdout)
        output_eval = invoke("extract-output", ["eval", browser_eval_body_and_report_script(list(spec.get("output_selectors", [])))])
        visible_text_parts.append(output_eval.stdout)
        current_url = invoke("get-url", ["get", "url"]).stdout.strip()
        screenshot_result = invoke("screenshot", ["screenshot", str(screenshot)])
        if screenshot_result.returncode != 0:
            capture_cdp_screenshot(cdp_port, screenshot)
        invoke("close-temp-page", ["close"])
    finally:
        terminate_process(browser_process)

    visible_text = "\n".join(part for part in visible_text_parts if part)
    output = extract_workflow_output_from_text(visible_text, provider=provider_id, mode=spec["mode"])
    verification = verify_visible_text(visible_text, provider=provider_id, mode=spec["mode"]) if visible_text else None
    if output["status"] == "complete" and status in {"submitted", "started"}:
        status = "verified"
    elif output["status"] == "running" and status == "submitted":
        status = "started"

    cache_payload = None
    if cache_root and visible_text.strip():
        record = save_chat_record(
            cache_root=cache_root,
            browser=browser_id,
            profile=profile_directory,
            provider=provider_id,
            chat_url=current_url or spec["url"],
            title=f"{provider_id} {spec['mode']} workflow",
            text=visible_text,
            source="agent-browser-profile-clone-workflow",
            refresh=refresh_cache,
        )
        cache_payload = {
            "key": record["key"],
            "metadata_path": str(record["metadata_path"]),
            "text_path": str(record["text_path"]),
            "cache_hit": record["cache_hit"],
        }

    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    (paths["run_dir"] / "output.txt").write_text(output["text"], encoding="utf-8")
    final_inventory = extract_provider_inventory(provider_id, visible_text)
    real_session_preflight = build_real_session_preflight(browser=browser, profile=profile, provider=provider_id)
    status, final_inventory = apply_real_session_requirement(status, final_inventory, real_session_preflight)
    payload = {
        **plan,
        "status": status,
        "clone": clone,
        "cdp_port": cdp_port,
        "launch": launch_status,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "chat_url": current_url,
        "inventory": final_inventory,
        "real_session_preflight": real_session_preflight,
        "verification": verification,
        "workflow_events": workflow_events,
        "output": output,
        "cache": cache_payload,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    return {
        **payload,
        "status_json": str(paths["status_json"]),
        "visible_text_path": str(paths["run_dir"] / "visible-text.txt"),
        "output_text_path": str(paths["run_dir"] / "output.txt"),
    }


def agent_browser_live_workflow_run(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    mode: str,
    prompt: str,
    artifact_root: Path,
    cdp_port: int,
    submit: bool = False,
    confirm_start: bool = False,
    wait_seconds: int = 30,
    timeout: float = 90.0,
    cache_root: Path | None = None,
    refresh_cache: bool = True,
    attachments: list[Path] | None = None,
    ignore_existing_non_cdp: bool = False,
    allow_active_tab_navigation_fallback: bool = False,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    spec = provider_workflow_spec(provider_id, mode)
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    profile_directory = str(profile.get("directory", "Default"))
    run_name = f"{browser_id}-{slug(profile_directory)}-{provider_id}-{slug(spec['mode'])}-live"
    paths = build_artifact_paths(artifact_root.expanduser(), provider=provider_id, mode=f"{spec['mode']}-live", browser=browser_id, profile=profile_directory)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    workflow_events: list[dict[str, Any]] = []
    plan = build_live_ai_workflow_plan(
        browser=browser,
        profile=profile,
        provider=provider_id,
        mode=spec["mode"],
        prompt=prompt,
        artifact_root=artifact_root,
        cdp_port=cdp_port,
        submit=submit,
        confirm_start=confirm_start,
        wait_seconds=wait_seconds,
        attachments=attachments,
    )
    real_session_preflight = build_real_session_preflight(
        browser=browser,
        profile=profile,
        provider=provider_id,
        port=cdp_port,
        ignore_existing_non_cdp=ignore_existing_non_cdp,
    )
    if not real_session_preflight.get("can_attach"):
        payload = {
            **plan,
            "status": "blocked",
            "blocker": "real browser CDP session is not attachable",
            "real_session_preflight": real_session_preflight,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    session = f"ai-live-{run_name}-p{int(cdp_port)}"
    snapshot_timeout = max(8.0, min(timeout, 18.0))

    def command_timeout(label: str, extra_args: list[str]) -> float:
        if extra_args[:1] == ["snapshot"]:
            return snapshot_timeout
        if extra_args[:1] == ["tab"]:
            return min(timeout, 20.0)
        if extra_args[:1] == ["eval"]:
            return min(timeout, 15.0)
        if extra_args == ["get", "url"]:
            return min(timeout, 8.0)
        if extra_args[:1] == ["press"]:
            return min(timeout, 10.0)
        if extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                return max(8.0, (int(str(extra_args[1])) / 1000.0) + 5.0)
            except ValueError:
                return min(timeout, 15.0)
        return timeout

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        if extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                milliseconds = int(str(extra_args[1]))
            except ValueError:
                milliseconds = 1000
            time.sleep(max(0, milliseconds) / 1000.0)
            result = subprocess.CompletedProcess(["sleep", str(milliseconds)], 0, f"waited {milliseconds}ms", "")
        elif extra_args[:1] == ["eval"] and len(extra_args) > 1:
            result = run_cdp_javascript(cdp_port, extra_args[1], timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["press"] and len(extra_args) > 1 and str(extra_args[1]).lower() in {"enter", "return"}:
            result = run_cdp_keypress(cdp_port, str(extra_args[1]), timeout=command_timeout(label, extra_args))
        elif extra_args == ["get", "url"]:
            result = run_cdp_javascript(cdp_port, "location.href", timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["screenshot"] and len(extra_args) > 1:
            ok = capture_cdp_screenshot(cdp_port, Path(extra_args[1]), timeout=min(timeout, 20.0))
            result = subprocess.CompletedProcess(["cdp-screenshot", str(cdp_port), extra_args[1]], 0 if ok else 1, str(extra_args[1]) if ok else "", "")
        elif extra_args[:1] == ["close"]:
            result = subprocess.CompletedProcess(["skip-close-live-tab"], 0, "skipped: live automation tab is left open", "")
        else:
            result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=command_timeout(label, extra_args))
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--session", session, "--cdp", str(cdp_port), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    visible_text_parts: list[str] = []
    screenshot = paths["screenshot_png"]
    current_url = ""
    status = "blocked"

    tab_result = invoke("open-background-tab", ["tab", "new", spec["url"]])
    if tab_result.returncode != 0:
        if allow_active_tab_navigation_fallback:
            nav_result = run_cdp_navigate(cdp_port, spec["url"], timeout=min(timeout, 20.0))
            commands.append(
                {
                    "label": "open-background-tab-fallback-navigate",
                    "args": ["cdp-navigate", str(cdp_port), spec["url"]],
                    "returncode": nav_result.returncode,
                    "stdout": nav_result.stdout[-4000:],
                    "stderr": nav_result.stderr[-4000:],
                }
            )
            workflow_events.append(
                {
                    "event": "open-background-tab-fallback-navigate",
                    "tab_new_returncode": tab_result.returncode,
                    "navigate_returncode": nav_result.returncode,
                }
            )
            if nav_result.returncode != 0:
                payload = {
                    **plan,
                    "status": "blocked",
                    "blocker": "agent-browser tab new and CDP navigation fallback both failed",
                    "real_session_preflight": real_session_preflight,
                    "workflow_events": workflow_events,
                    "commands": commands,
                    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
                write_json(paths["status_json"], payload)
                return {**payload, "status_json": str(paths["status_json"])}
        else:
            payload = {
                **plan,
                "status": "blocked",
                "blocker": "agent-browser could not open a new live CDP tab",
                "real_session_preflight": real_session_preflight,
                "workflow_events": [{"event": "open-background-tab", "returncode": tab_result.returncode}],
                "commands": commands,
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            write_json(paths["status_json"], payload)
            return {**payload, "status_json": str(paths["status_json"])}

    invoke("wait-initial", ["wait", "4000"])
    before_eval = invoke("eval-before-text", ["eval", browser_eval_visible_text_script()])
    visible_text_parts.append(before_eval.stdout)
    before_snapshot = invoke("snapshot-before", ["snapshot", "-i", "-c"])
    current_snapshot_text = before_snapshot.stdout
    visible_text_parts.append(current_snapshot_text)
    consent_result = click_first_agent_browser_text(
        invoke,
        ["Alle akzeptieren", "Alle annehmen", "Accept all", "I agree", "Agree", "Zustimmen"],
        command_log_label="consent",
        snapshot=current_snapshot_text,
        prefer_js=True,
    )
    if consent_result.get("clicked"):
        workflow_events.append({"event": "consent", **consent_result})
        invoke("wait-after-consent", ["wait", "2500"])
        consent_eval = invoke("eval-after-consent", ["eval", browser_eval_visible_text_script()])
        visible_text_parts.append(consent_eval.stdout)
        consent_snapshot = invoke("snapshot-after-consent", ["snapshot", "-i", "-c"])
        current_snapshot_text = consent_snapshot.stdout or current_snapshot_text
        visible_text_parts.append(current_snapshot_text)

    inventory = extract_provider_inventory(provider_id, "\n".join(visible_text_parts))
    if inventory.get("login_state") == "signed-out-or-wall":
        status = "signed-out-or-wall"
    else:
        status = "opened"
        feature_result = {"clicked": False, "label": "", "attempts": []}
        if spec.get("pre_prompt_triggers"):
            pre_prompt_result = click_first_agent_browser_text(
                invoke,
                list(spec.get("pre_prompt_triggers", [])),
                command_log_label="pre-prompt-trigger",
                snapshot=current_snapshot_text,
            )
            workflow_events.append({"event": "pre-prompt-trigger", **pre_prompt_result})
            if pre_prompt_result.get("clicked"):
                invoke("wait-after-pre-prompt-trigger", ["wait", "1000"])
                pre_prompt_snapshot = invoke("snapshot-after-pre-prompt-trigger", ["snapshot", "-i", "-c"])
                current_snapshot_text = pre_prompt_snapshot.stdout or current_snapshot_text
                visible_text_parts.append(current_snapshot_text)
        if spec.get("feature_triggers"):
            menu_result = click_first_agent_browser_text(
                invoke,
                list(spec.get("menu_triggers", [])),
                command_log_label="open-feature-menu",
                snapshot=current_snapshot_text,
            )
            if menu_result.get("clicked"):
                workflow_events.append({"event": "open-feature-menu", **menu_result})
                invoke("wait-after-feature-menu", ["wait", "1000"])
                menu_snapshot = invoke("snapshot-after-feature-menu", ["snapshot", "-i", "-c"])
                current_snapshot_text = menu_snapshot.stdout or current_snapshot_text
                visible_text_parts.append(current_snapshot_text)
            feature_result = click_first_agent_browser_text(
                invoke,
                list(spec["feature_triggers"]),
                command_log_label="select-feature",
                snapshot=current_snapshot_text,
            )
            workflow_events.append({"event": "select-feature", **feature_result})
        if not feature_result.get("clicked") and spec.get("slash_triggers"):
            slash = str(spec["slash_triggers"][0])
            slash_result = fill_agent_browser_composer(
                invoke,
                snapshot=current_snapshot_text,
                selector=spec["composer_selector"],
                text=slash,
                label="slash-feature",
            )
            workflow_events.append({"event": "slash-feature", "trigger": slash, "returncode": slash_result.returncode})
            if slash_result.returncode == 0:
                invoke("slash-enter", ["press", "Enter"])
                invoke("wait-after-slash", ["wait", "1500"])
                slash_snapshot = invoke("snapshot-after-slash", ["snapshot", "-i", "-c"])
                current_snapshot_text = slash_snapshot.stdout or current_snapshot_text

        fill_result = fill_agent_browser_composer(
            invoke,
            snapshot=current_snapshot_text,
            selector=spec["composer_selector"],
            text=prompt,
            label="fill-prompt",
        )
        workflow_events.append({"event": "fill-prompt", "returncode": fill_result.returncode})
        if fill_result.returncode == 0:
            prepare_and_upload_attachments(
                port=cdp_port,
                attachments=attachments,
                commands=commands,
                workflow_events=workflow_events,
                timeout=timeout,
                invoke=invoke,
                snapshot=current_snapshot_text,
                menu_triggers=list(spec.get("attachment_triggers", [])),
            )
        if submit and fill_result.returncode == 0:
            invoke("submit-prompt", ["press", "Enter"])
            status = "submitted"
            pre_confirm_wait_seconds = int(spec.get("pre_confirm_wait_seconds", 12))
            invoke("wait-after-submit", ["wait", str(max(1000, min(wait_seconds, 8) * 1000))])
            if confirm_start and spec.get("confirmation_triggers"):
                confirm_attempts: list[dict[str, Any]] = []
                confirm_result: dict[str, Any] = {"clicked": False, "label": "", "ref": "", "attempts": confirm_attempts}
                confirm_deadline = time.monotonic() + max(1, pre_confirm_wait_seconds)
                confirm_index = 0
                while True:
                    confirm_snapshot = invoke(f"snapshot-before-confirm-{confirm_index}", ["snapshot", "-i", "-c"])
                    current_snapshot_text = confirm_snapshot.stdout or current_snapshot_text
                    visible_text_parts.append(current_snapshot_text)
                    exact_ref = find_confirmation_ref(current_snapshot_text, list(spec["confirmation_triggers"]))
                    exact_label = ""
                    if exact_ref:
                        for trigger_label in spec["confirmation_triggers"]:
                            if find_snapshot_ref(
                                current_snapshot_text,
                                str(trigger_label),
                                roles=("button", "menuitem", "menuitemradio", "option"),
                                exact_only=True,
                            ) == exact_ref:
                                exact_label = str(trigger_label)
                                break
                        click_result = invoke(f"confirm-start:{exact_label or exact_ref}", ["click", f"@{exact_ref}"])
                        confirm_attempts.append({"label": exact_label, "ref": exact_ref, "returncode": click_result.returncode})
                        if click_result.returncode == 0:
                            confirm_result = {"clicked": True, "label": exact_label, "ref": exact_ref, "attempts": confirm_attempts}
                            break
                    else:
                        marker_probe = extract_workflow_output_from_text(current_snapshot_text, provider=provider_id, mode=spec["mode"])
                        confirm_attempts.append(
                            {
                                "label": "",
                                "returncode": 1,
                                "skipped": "no-exact-confirmation-control",
                                "marker_status": marker_probe["status"],
                                "running_markers_found": marker_probe.get("running_markers_found", []),
                            }
                        )
                        if marker_probe["status"] == "running" and marker_probe.get("running_markers_found"):
                            confirm_result = {"clicked": False, "label": "", "ref": "", "running_marker_seen": True, "attempts": confirm_attempts}
                            break
                    remaining = confirm_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    confirm_index += 1
                    invoke(f"wait-before-confirm-{confirm_index}", ["wait", wait_milliseconds(remaining, maximum_ms=3000)])
                workflow_events.append({"event": "confirm-start", **confirm_result})
                if confirm_result.get("clicked") or confirm_result.get("running_marker_seen"):
                    status = "started"
                    invoke("wait-after-confirm", ["wait", str(max(1000, min(wait_seconds, 30) * 1000))])

    after_snapshot = invoke("snapshot-after", ["snapshot", "-i", "-c"])
    visible_text_parts.append(after_snapshot.stdout)
    output_eval = invoke("extract-output", ["eval", browser_eval_body_and_report_script(list(spec.get("output_selectors", [])))])
    visible_text_parts.append(output_eval.stdout)
    current_url = invoke("get-url", ["get", "url"]).stdout.strip()
    screenshot_result = invoke("screenshot", ["screenshot", str(screenshot)])
    if screenshot_result.returncode != 0:
        capture_cdp_screenshot(cdp_port, screenshot)

    visible_text = "\n".join(part for part in visible_text_parts if part)
    output = extract_workflow_output_from_text(visible_text, provider=provider_id, mode=spec["mode"])
    verification = verify_visible_text(visible_text, provider=provider_id, mode=spec["mode"]) if visible_text else None
    if output["status"] == "complete" and status in {"submitted", "started"}:
        status = "verified"
    elif output["status"] == "running" and status == "submitted":
        status = "started"

    cache_payload = None
    if cache_root and visible_text.strip():
        record = save_chat_record(
            cache_root=cache_root,
            browser=browser_id,
            profile=profile_directory,
            provider=provider_id,
            chat_url=current_url or spec["url"],
            title=f"{provider_id} {spec['mode']} live workflow",
            text=visible_text,
            source="agent-browser-live-workflow",
            refresh=refresh_cache,
        )
        cache_payload = {
            "key": record["key"],
            "metadata_path": str(record["metadata_path"]),
            "text_path": str(record["text_path"]),
            "cache_hit": record["cache_hit"],
        }

    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    (paths["run_dir"] / "output.txt").write_text(output["text"], encoding="utf-8")
    final_inventory = extract_provider_inventory(provider_id, visible_text)
    payload = {
        **plan,
        "status": status,
        "chat_url": current_url,
        "inventory": final_inventory,
        "real_session_preflight": real_session_preflight,
        "verification": verification,
        "workflow_events": workflow_events,
        "output": output,
        "cache": cache_payload,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    return {
        **payload,
        "status_json": str(paths["status_json"]),
        "visible_text_path": str(paths["run_dir"] / "visible-text.txt"),
        "output_text_path": str(paths["run_dir"] / "output.txt"),
    }


def agent_browser_profile_followup_run(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str,
    chat_url: str,
    prompt: str,
    artifact_root: Path,
    clone_root: Path,
    submit: bool = True,
    wait_seconds: int = 30,
    timeout: float = 90.0,
    cache_root: Path | None = None,
    refresh_cache: bool = True,
    include_extension_ids: list[str] | None = None,
    export_markdown: Path | None = None,
    attachments: list[Path] | None = None,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    spec = provider_workflow_spec(provider_id, "chat")
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    profile_directory = str(profile.get("directory", "Default"))
    run_name = f"{browser_id}-{slug(profile_directory)}-{provider_id}-followup"
    paths = build_artifact_paths(artifact_root.expanduser(), provider=provider_id, mode="followup", browser=browser_id, profile=profile_directory)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    workflow_events: list[dict[str, Any]] = []
    extension_ids = include_extension_ids or []
    clone = clone_browser_profile_for_agent_browser(
        browser,
        profile,
        clone_root,
        run_slug=run_name,
        include_extension_ids=extension_ids,
    )
    if not clone.get("ok"):
        payload = {
            "provider": provider_id,
            "browser": browser_id,
            "profile": profile_directory,
            "chat_url": chat_url,
            "status": "blocked",
            "blocker": clone.get("error", "profile clone failed"),
            "clone": clone,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    session = f"ai-followup-{run_name}"
    cdp_port = find_available_port()
    launch_args = build_clone_cdp_launch_args(
        browser,
        clone_user_data=str(clone["clone_user_data"]),
        profile_directory=profile_directory,
        port=cdp_port,
        headless=True,
        initial_url="about:blank",
        extension_paths=[item["path"] for item in discover_profile_extensions(profile, extension_ids=extension_ids)] if extension_ids else None,
    )
    browser_process, launch_status = start_clone_cdp_browser(
        launch_args=launch_args,
        port=cdp_port,
        log_path=paths["run_dir"] / "browser-cdp.log",
    )
    if not launch_status.get("ok"):
        terminate_process(browser_process)
        payload = {
            "provider": provider_id,
            "browser": browser_id,
            "profile": profile_directory,
            "chat_url": chat_url,
            "status": "blocked",
            "blocker": "browser clone CDP launch failed",
            "clone": clone,
            "launch": launch_status,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        write_json(paths["status_json"], payload)
        return {**payload, "status_json": str(paths["status_json"])}

    def command_timeout(label: str, extra_args: list[str]) -> float:
        if extra_args[:1] == ["open"]:
            return min(timeout, 20.0)
        if extra_args[:1] == ["eval"]:
            return min(timeout, 15.0)
        if extra_args[:1] == ["snapshot"]:
            return min(timeout, 18.0)
        if extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                return max(8.0, (int(str(extra_args[1])) / 1000.0) + 5.0)
            except ValueError:
                return min(timeout, 15.0)
        return timeout

    def invoke(label: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        if extra_args[:1] == ["open"] and len(extra_args) > 1:
            result = run_cdp_navigate(cdp_port, str(extra_args[1]), timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["wait"] and len(extra_args) > 1:
            try:
                milliseconds = int(str(extra_args[1]))
            except ValueError:
                milliseconds = 1000
            time.sleep(max(0, milliseconds) / 1000.0)
            result = subprocess.CompletedProcess(["sleep", str(milliseconds)], 0, f"waited {milliseconds}ms", "")
        elif extra_args[:1] == ["eval"] and len(extra_args) > 1:
            result = run_cdp_javascript(cdp_port, extra_args[1], timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["press"] and len(extra_args) > 1 and str(extra_args[1]).lower() in {"enter", "return"}:
            result = run_cdp_keypress(cdp_port, str(extra_args[1]), timeout=command_timeout(label, extra_args))
        elif extra_args == ["get", "url"]:
            result = run_cdp_javascript(cdp_port, "location.href", timeout=command_timeout(label, extra_args))
        elif extra_args[:1] == ["screenshot"] and len(extra_args) > 1:
            ok = capture_cdp_screenshot(cdp_port, Path(extra_args[1]), timeout=min(timeout, 20.0))
            result = subprocess.CompletedProcess(["cdp-screenshot", str(cdp_port), extra_args[1]], 0 if ok else 1, str(extra_args[1]) if ok else "", "")
        elif extra_args[:1] == ["close"]:
            result = subprocess.CompletedProcess(["skip-close-temp-page"], 0, "skipped: browser process terminates in finally", "")
        else:
            result = run_agent_browser(["--cdp", str(cdp_port), *extra_args], session=session, timeout=command_timeout(label, extra_args))
        commands.append(
            {
                "label": label,
                "args": ["agent-browser", "--session", session, "--cdp", str(cdp_port), *extra_args],
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        return result

    visible_text_parts: list[str] = []
    screenshot = paths["screenshot_png"]
    current_url = ""
    status = "opened"
    try:
        invoke("open-chat", ["open", chat_url])
        invoke("wait-chat", ["wait", "5000"])
        first_url = invoke("get-url-after-open", ["get", "url"]).stdout.strip()
        if first_url and not url_matches_provider(first_url, provider_id):
            workflow_events.append({"event": "provider-url-retry", "from_url": first_url, "to_url": chat_url})
            invoke("open-chat-retry", ["open", chat_url])
            invoke("wait-chat-retry", ["wait", "5000"])
        before_eval = invoke("eval-before-text", ["eval", browser_eval_visible_text_script()])
        visible_text_parts.append(before_eval.stdout)
        before_snapshot = invoke("snapshot-before", ["snapshot", "-i", "-c"])
        current_snapshot_text = before_snapshot.stdout
        visible_text_parts.append(current_snapshot_text)
        inventory = extract_provider_inventory(provider_id, "\n".join(visible_text_parts))
        if inventory.get("login_state") == "signed-out-or-wall":
            status = "signed-out-or-wall"
        else:
            fill_result = fill_agent_browser_composer(
                invoke,
                snapshot=current_snapshot_text,
                selector=spec["composer_selector"],
                text=prompt,
                label="fill-followup",
            )
            workflow_events.append({"event": "fill-followup", "returncode": fill_result.returncode})
            if fill_result.returncode == 0:
                prepare_and_upload_attachments(
                    port=cdp_port,
                    attachments=attachments,
                    commands=commands,
                    workflow_events=workflow_events,
                    timeout=timeout,
                    invoke=invoke,
                    snapshot=current_snapshot_text,
                    menu_triggers=list(spec.get("attachment_triggers", [])),
                    label="attach-followup-files",
                )
            if submit and fill_result.returncode == 0:
                invoke("submit-followup", ["press", "Enter"])
                status = "submitted"
                invoke("wait-after-followup", ["wait", str(max(1000, wait_seconds * 1000))])
        after_snapshot = invoke("snapshot-after", ["snapshot", "-i", "-c"])
        visible_text_parts.append(after_snapshot.stdout)
        output_eval = invoke("extract-output", ["eval", browser_eval_body_and_report_script(list(spec.get("output_selectors", [])))])
        visible_text_parts.append(output_eval.stdout)
        current_url = invoke("get-url", ["get", "url"]).stdout.strip()
        invoke("screenshot", ["screenshot", str(screenshot)])
        invoke("close-temp-page", ["close"])
    finally:
        terminate_process(browser_process)

    visible_text = "\n".join(part for part in visible_text_parts if part)
    output = extract_workflow_output_from_text(visible_text, provider=provider_id, mode="chat")
    if output["status"] in {"running", "complete"} and status == "submitted":
        status = "verified" if output["status"] == "complete" else "started"
    final_inventory = extract_provider_inventory(provider_id, visible_text)
    real_session_preflight = build_real_session_preflight(browser=browser, profile=profile, provider=provider_id)
    status, final_inventory = apply_real_session_requirement(status, final_inventory, real_session_preflight)
    cache_payload = None
    if cache_root and visible_text.strip():
        record = save_chat_record(
            cache_root=cache_root,
            browser=browser_id,
            profile=profile_directory,
            provider=provider_id,
            chat_url=current_url or chat_url,
            title=f"{provider_id} follow-up",
            text=visible_text,
            source="agent-browser-profile-clone-followup",
            refresh=refresh_cache,
        )
        cache_payload = {
            "key": record["key"],
            "metadata_path": str(record["metadata_path"]),
            "text_path": str(record["text_path"]),
            "cache_hit": record["cache_hit"],
        }
    (paths["run_dir"] / "visible-text.txt").write_text(visible_text, encoding="utf-8")
    (paths["run_dir"] / "output.txt").write_text(output["text"], encoding="utf-8")
    export_path = export_markdown.expanduser() if export_markdown else paths["run_dir"] / "chat-export.md"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(output["text"] or visible_text, encoding="utf-8")
    payload = {
        "provider": provider_id,
        "browser": browser_id,
        "profile": profile_directory,
        "status": status,
        "chat_url": current_url or chat_url,
        "followup_prompt": prompt,
        "attachments": [str(path.expanduser()) for path in attachments or []],
        "clone": clone,
        "cdp_port": cdp_port,
        "launch": launch_status,
        "screenshot": str(screenshot) if screenshot.exists() else "",
        "inventory": final_inventory,
        "real_session_preflight": real_session_preflight,
        "workflow_events": workflow_events,
        "output": output,
        "cache": cache_payload,
        "export_markdown": str(export_path),
        "extension_ids": extension_ids,
        "commands": commands,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(paths["status_json"], payload)
    return {
        **payload,
        "status_json": str(paths["status_json"]),
        "visible_text_path": str(paths["run_dir"] / "visible-text.txt"),
        "output_text_path": str(paths["run_dir"] / "output.txt"),
    }


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


def requested_extension_ids(raw_values: list[str] | None = None, *, include_ai_exporter: bool = False) -> list[str]:
    ids: list[str] = []
    values = list(raw_values or [])
    if include_ai_exporter:
        values.append("ai-exporter")
    for raw in values:
        for item in str(raw).split(","):
            for extension_id in known_extension_ids(item.strip()):
                if extension_id and extension_id not in ids:
                    ids.append(extension_id)
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
        "notion": ["notion.so", "www.notion.so"],
    }.get(normalize_provider_name(provider), [])


def url_matches_provider(url: str, provider: str) -> bool:
    provider_id = normalize_provider_name(provider)
    try:
        hostname = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return False
    hostname = hostname.lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in provider_session_domains(provider_id))


def provider_session_cookie_names(provider: str) -> list[str]:
    return {
        "chatgpt": ["session", "__Secure-next-auth.session-token", "oai-client-auth-session", "unified_session_manifest", "_puid"],
        "gemini": ["SAPISID", "APISID", "HSID", "OSID", "__Secure-OSID", "COMPASS"],
        "claude": ["sessionKey", "lastActiveOrg", "intercom-session", "__ssid"],
        "perplexity": ["__Secure-next-auth.session-token", "pplx", "g_state", "intercom-session"],
        "grok": ["sso", "sso-rw", "x-userid", "auth_token", "twid"],
        "openrouter": ["__session", "__refresh", "__client", "__client_uat"],
        "notion": ["notion_user_id", "token_v2", "file_token"],
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


def endpoint_json_version(base: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/json/version", timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def cdp_hosts_for_port(port: int) -> list[str]:
    return [f"http://127.0.0.1:{port}", f"http://[::1]:{port}"]


def detect_cdp_endpoint(port: int, hosts: list[str] | None = None) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for base in hosts or cdp_hosts_for_port(port):
        version = endpoint_json_version(base)
        attempts.append({"base": base, "ok": bool(version), "version": version or {}})
        if version:
            return {"ok": True, "base": base, "version": version, "attempts": attempts}
    return {"ok": False, "base": "", "version": {}, "attempts": attempts}


def lsof_port_owner(port: int) -> dict[str, Any]:
    result = subprocess.run(["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN"], capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or len(lines) < 2:
        return {"port": int(port), "listening": False, "command": "", "pid": "", "raw": result.stdout}
    parts = lines[1].split()
    return {
        "port": int(port),
        "listening": True,
        "command": parts[0] if parts else "",
        "pid": parts[1] if len(parts) > 1 else "",
        "raw": result.stdout,
    }


def browser_main_process_args(browser: dict[str, Any]) -> list[str]:
    binary_path = str(browser.get("binary_path", ""))
    app_path = str(browser.get("app_path", ""))
    result = subprocess.run(["ps", "-ww", "-axo", "args="], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    matches: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if " Helper" in line:
            continue
        if binary_path and binary_path in line:
            matches.append(line)
            continue
        if app_path and app_path in line and "Contents/MacOS" in line:
            matches.append(line)
    return matches


def build_real_session_preflight(
    *,
    browser: dict[str, Any],
    profile: dict[str, str],
    provider: str = "gemini",
    port: int | None = None,
    ignore_existing_non_cdp: bool = False,
) -> dict[str, Any]:
    provider_id = normalize_provider_name(provider)
    browser_id = normalize_browser_name(str(browser.get("id", "")))
    cdp_port = int(port or browser.get("default_port") or 0)
    endpoint = detect_cdp_endpoint(cdp_port) if cdp_port else {"ok": False, "base": "", "version": {}, "attempts": []}
    owner = lsof_port_owner(cdp_port) if cdp_port else {"port": 0, "listening": False, "command": "", "pid": "", "raw": ""}
    main_args = browser_main_process_args(browser)
    running_without_cdp = bool(main_args) and not any("--remote-debugging-port" in line for line in main_args)
    expected_name = str(browser.get("display_name", browser_id)).lower()
    owner_command = str(owner.get("command", "")).lower()
    owner_matches_browser = bool(owner_command) and any(part in owner_command for part in [browser_id.lower(), expected_name.split()[0]])
    blockers: list[str] = []
    if owner.get("listening") and not endpoint.get("ok"):
        blockers.append("port-listener-is-not-cdp")
    if owner.get("listening") and not owner_matches_browser and not endpoint.get("ok"):
        blockers.append("port-owned-by-other-process")
    if running_without_cdp and not ignore_existing_non_cdp:
        blockers.append("browser-running-without-remote-debugging")
    if not endpoint.get("ok") and not blockers:
        blockers.append("cdp-endpoint-not-reachable")
    session_evidence = provider_session_evidence(profile, provider_id)
    return {
        "browser": browser_id,
        "browser_name": browser.get("display_name", ""),
        "profile_directory": profile.get("directory", ""),
        "profile_name": profile.get("name", ""),
        "provider": provider_id,
        "port": cdp_port,
        "can_attach": bool(endpoint.get("ok")) and not blockers,
        "blockers": blockers,
        "cdp_endpoint": endpoint,
        "port_owner": owner,
        "browser_main_process_count": len(main_args),
        "browser_main_process_has_remote_debugging": any("--remote-debugging-port" in line for line in main_args),
        "ignored_existing_non_cdp_processes": bool(running_without_cdp and ignore_existing_non_cdp),
        "session_evidence": session_evidence,
        "safe_next_steps": [
            "Use an already-running browser only when this preflight reports can_attach=true.",
            "Do not quit or relaunch the user's active browser automatically.",
            "For Gemini Deep Research, profile clones may preserve cookie evidence but still fail entitlement/login checks; use a real CDP-enabled session for final E2E.",
        ],
        "hidden_gemini_commands": {
            "check": [
                "python3",
                "~/.hermes/scripts/deep_research_hidden.py",
                "check-deep-research-started",
                "--browser",
                browser_id,
            ],
            "start": [
                "python3",
                "~/.hermes/scripts/deep_research_hidden.py",
                "start-deep-research",
                "--browser",
                browser_id,
                "--prompt",
                "<prompt>",
            ],
        },
    }


def apply_real_session_requirement(
    status: str,
    inventory: dict[str, Any],
    real_session_preflight: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    session_confidence = real_session_preflight.get("session_evidence", {}).get("confidence")
    clone_shows_login_wall = inventory.get("login_state") == "signed-out-or-wall"
    if clone_shows_login_wall and session_confidence in {"likely-logged-in", "site-data-present"}:
        return "real-session-required", inventory
    if status in {"submitted", "started", "verified"} and clone_shows_login_wall:
        updated_inventory = dict(inventory)
        updated_inventory["login_state"] = "signed-in-or-ready"
        return status, updated_inventory
    return status, inventory


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
                status = "captured" if account_status else ("skipped" if not can_launch else "needs-ui-capture")
                if not account_status and can_launch and session_evidence.get("confidence") != "none":
                    status = "session-detected-needs-ui-capture"
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
                        "status": status,
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
    visible_status = parse_visible_status(visible_text or "", provider=provider)
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


def cmd_real_session_preflight(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    payload = build_real_session_preflight(
        browser=browser,
        profile=profile,
        provider=args.provider,
        port=args.port or None,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("can_attach") else 1


def cmd_launch_background(args: argparse.Namespace) -> int:
    browsers = {b["id"]: b for b in discover_browsers()}
    browser_id = normalize_browser_name(args.browser)
    if browser_id not in browsers:
        raise SystemExit(f"browser not discovered: {args.browser}")
    browser = browsers[browser_id]
    can_launch, reason = launchable_browser(browser)
    if not can_launch:
        payload = {"plan": None, "execution": {"started": False, "dry_run": args.dry_run, "error": reason}}
        if args.output:
            write_json(Path(args.output).expanduser(), payload)
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
        if args.output:
            write_json(Path(args.output).expanduser(), payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if args.dry_run else 2
    execution = execute_background_launch(plan, dry_run=args.dry_run)
    payload = {"plan": plan, "execution": execution}
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    payload = {"plan": plan, "executions": executions}
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    return 0 if all((result.get("probe_result") or {}).get("status") in {"captured", "captured-without-screenshot", "signed-out-or-wall"} for result in results) else 1


def cmd_agent_browser_live_suite(args: argparse.Namespace) -> int:
    if not args.cdp_port:
        raise SystemExit("agent-browser-live-suite requires --cdp-port for the real browser session")
    if not is_port_open(args.cdp_port):
        print(json.dumps({"status": "blocked", "blocker": f"CDP port {args.cdp_port} is not reachable"}, ensure_ascii=False, indent=2))
        return 2

    providers = requested_provider_ids(args.providers) if args.providers else ["chatgpt", "gemini", "claude"]
    browsers = discover_browsers()
    selected_browser_ids = {normalize_browser_name(item.strip()) for item in args.browsers.split(",") if item.strip()}
    if selected_browser_ids:
        browsers = [browser for browser in browsers if browser.get("id") in selected_browser_ids]
    rows = build_primary_feature_suite(
        browsers,
        providers=providers,
        include_all_features=args.all_features,
        backend="agent-browser",
    )
    if args.profile:
        profile_slug = slug(args.profile)
        rows = [row for row in rows if slug(str(row.get("profile_directory", ""))) == profile_slug or slug(str(row.get("profile_name", ""))) == profile_slug]

    results = []
    for index, row in enumerate(rows, start=1):
        if args.max_runs and len(results) >= args.max_runs:
            break
        result = agent_browser_probe(
            cdp_port=args.cdp_port,
            provider=str(row["provider"]),
            mode=str(row["feature"]),
            artifact_root=Path(args.artifact_root).expanduser(),
            browser=str(row["browser"]),
            profile=str(row["profile_directory"]),
            session=args.session,
            open_controls=args.open_controls,
            timeout=args.timeout,
        )
        results.append({**row, "probe_result": result, "run_index": index, "ok": live_probe_ok(result, assert_login=args.assert_login)})

    payload = {
        "status": "completed",
        "cdp_port": args.cdp_port,
        "cdp_version": endpoint_version(args.cdp_port) or {},
        "artifact_root": str(Path(args.artifact_root).expanduser()),
        "assert_login": args.assert_login,
        "results": results,
    }
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if results and all(result.get("ok") for result in results) else 1


def cmd_agent_browser_ask(args: argparse.Namespace) -> int:
    if not args.cdp_port:
        raise SystemExit("agent-browser-ask requires --cdp-port for the real browser session")
    if not is_port_open(args.cdp_port):
        print(json.dumps({"status": "blocked", "blocker": f"CDP port {args.cdp_port} is not reachable"}, ensure_ascii=False, indent=2))
        return 2
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
    if not prompt:
        raise SystemExit("agent-browser-ask requires --prompt or --prompt-file")
    payload = agent_browser_ask_export(
        cdp_port=args.cdp_port,
        provider=args.provider,
        prompt=prompt,
        artifact_root=Path(args.artifact_root).expanduser(),
        browser=args.browser,
        profile=args.profile,
        session=args.session,
        submit=args.submit,
        timeout=args.timeout,
        cache_root=Path(args.cache_root).expanduser() if args.cache else None,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"filled", "submitted"} else 1


def workflow_prompt_from_args(args: argparse.Namespace) -> str:
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
    if not prompt:
        raise SystemExit(f"{args.command} requires --prompt or --prompt-file")
    return prompt


def resolve_workflow_browser_profile(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    browsers = discover_browsers()
    browser_id = normalize_browser_name(args.browser)
    browser_map = {browser["id"]: browser for browser in browsers}
    if browser_id not in browser_map:
        raise SystemExit(f"browser not discovered: {args.browser}")
    browser = browser_map[browser_id]
    profile = resolve_profile(browser.get("profiles", []), args.profile)
    return browser, profile


def cmd_workflow_plan(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    attachments = [Path(item).expanduser() for item in getattr(args, "attachment", []) or []]
    payload = build_ai_workflow_plan(
        browser=browser,
        profile=profile,
        provider=args.provider,
        mode=args.mode,
        prompt=workflow_prompt_from_args(args),
        artifact_root=Path(args.artifact_root).expanduser(),
        clone_root=Path(args.clone_root).expanduser(),
        submit=args.submit,
        confirm_start=args.confirm_start,
        wait_seconds=args.wait_seconds,
        attachments=attachments,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_workflow_run(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    extension_ids = requested_extension_ids(getattr(args, "include_extension", None), include_ai_exporter=getattr(args, "include_ai_exporter", False))
    attachments = [Path(item).expanduser() for item in getattr(args, "attachment", []) or []]
    payload = agent_browser_profile_workflow_run(
        browser=browser,
        profile=profile,
        provider=args.provider,
        mode=args.mode,
        prompt=workflow_prompt_from_args(args),
        artifact_root=Path(args.artifact_root).expanduser(),
        clone_root=Path(args.clone_root).expanduser(),
        submit=args.submit,
        confirm_start=args.confirm_start,
        wait_seconds=args.wait_seconds,
        timeout=args.timeout,
        cache_root=Path(args.cache_root).expanduser() if args.cache else None,
        refresh_cache=not args.no_refresh_cache,
        include_extension_ids=extension_ids,
        attachments=attachments,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"opened", "submitted", "started", "verified", "captured"} else 1


def cmd_workflow_live_run(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    attachments = [Path(item).expanduser() for item in getattr(args, "attachment", []) or []]
    payload = agent_browser_live_workflow_run(
        browser=browser,
        profile=profile,
        provider=args.provider,
        mode=args.mode,
        prompt=workflow_prompt_from_args(args),
        artifact_root=Path(args.artifact_root).expanduser(),
        cdp_port=args.cdp_port,
        submit=args.submit,
        confirm_start=args.confirm_start,
        wait_seconds=args.wait_seconds,
        timeout=args.timeout,
        cache_root=Path(args.cache_root).expanduser() if args.cache else None,
        refresh_cache=not args.no_refresh_cache,
        attachments=attachments,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"opened", "submitted", "started", "verified", "captured"} else 1


def cmd_workflow_sibling_run(args: argparse.Namespace) -> int:
    browser, source_profile = resolve_workflow_browser_profile(args)
    provider_id = normalize_provider_name(args.provider)
    prompt = workflow_prompt_from_args(args)
    extension_ids = requested_extension_ids(getattr(args, "include_extension", None), include_ai_exporter=getattr(args, "include_ai_exporter", False))
    sibling_user_data = Path(args.sibling_user_data).expanduser() if args.sibling_user_data else default_sibling_user_data_dir(
        browser=str(browser.get("id", "")),
        profile=str(source_profile.get("directory", args.profile)),
    )
    sibling_profile = prepare_sibling_profile(
        browser=browser,
        profile=source_profile,
        sibling_user_data=sibling_user_data,
        refresh=args.refresh_sibling,
        include_extension_ids=extension_ids,
    )
    if not sibling_profile.get("ok"):
        payload = {
            "status": "blocked",
            "execution_mode": "sibling-cdp-automation-profile",
            "sibling_profile": sibling_profile,
            "closed_after": False,
        }
        if args.output:
            write_json(Path(args.output).expanduser(), payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    cdp_port = args.cdp_port or find_available_port()
    extension_paths = [item["path"] for item in discover_profile_extensions(source_profile, extension_ids=extension_ids)] if extension_ids else None
    launch_args = build_sibling_cdp_launch_args(
        browser,
        sibling_user_data=str(sibling_user_data),
        profile_directory=str(sibling_profile["profile_directory"]),
        port=cdp_port,
        provider=provider_id,
        headless=args.headless,
        extension_paths=extension_paths,
    )
    artifact_root = Path(args.artifact_root).expanduser()
    log_path = artifact_root / f"sibling-{normalize_browser_name(str(browser.get('id', '')))}-{slug(str(sibling_profile['profile_directory']))}.log"
    process, launch_status = start_sibling_cdp_browser(
        launch_args=launch_args,
        port=cdp_port,
        log_path=log_path,
    )
    closed_after = False
    try:
        if not launch_status.get("ok"):
            payload = {
                "status": "blocked",
                "execution_mode": "sibling-cdp-automation-profile",
                "browser": normalize_browser_name(str(browser.get("id", ""))),
                "provider": provider_id,
                "mode": args.mode,
                "sibling_profile": sibling_profile,
                "launch": launch_status,
                "closed_after": False,
            }
            if args.output:
                write_json(Path(args.output).expanduser(), payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        sibling_browser = dict(browser)
        sibling_browser["user_data_dir"] = str(sibling_user_data)
        sibling_runtime_profile = {
            **source_profile,
            "path": str(Path(str(sibling_profile["sibling_profile"])).expanduser()),
        }
        workflow_payload = agent_browser_live_workflow_run(
            browser=sibling_browser,
            profile=sibling_runtime_profile,
            provider=provider_id,
            mode=args.mode,
            prompt=prompt,
            artifact_root=artifact_root,
            cdp_port=cdp_port,
            submit=args.submit,
            confirm_start=args.confirm_start,
            wait_seconds=args.wait_seconds,
            timeout=args.timeout,
            cache_root=Path(args.cache_root).expanduser() if args.cache else None,
            refresh_cache=not args.no_refresh_cache,
            attachments=[Path(item).expanduser() for item in args.attachment],
            ignore_existing_non_cdp=True,
            allow_active_tab_navigation_fallback=True,
        )
        payload = {
            **workflow_payload,
            "execution_mode": "sibling-cdp-automation-profile",
            "sibling_profile": sibling_profile,
            "launch": launch_status,
            "closed_after": False,
        }
    finally:
        if args.close_after:
            terminate_process(process)
            clean_sibling_profile_locks(sibling_user_data, str(sibling_profile.get("profile_directory", source_profile.get("directory", "Default"))))
            closed_after = True
    payload["closed_after"] = closed_after
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"opened", "submitted", "started", "verified", "captured"} else 1


def cmd_workflow_followup(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    prompt = workflow_prompt_from_args(args)
    extension_ids = requested_extension_ids(args.include_extension, include_ai_exporter=args.include_ai_exporter)
    attachments = [Path(item).expanduser() for item in getattr(args, "attachment", []) or []]
    payload = agent_browser_profile_followup_run(
        browser=browser,
        profile=profile,
        provider=args.provider,
        chat_url=args.chat_url,
        prompt=prompt,
        artifact_root=Path(args.artifact_root).expanduser(),
        clone_root=Path(args.clone_root).expanduser(),
        submit=not args.no_submit,
        wait_seconds=args.wait_seconds,
        timeout=args.timeout,
        cache_root=Path(args.cache_root).expanduser() if args.cache else None,
        refresh_cache=not args.no_refresh_cache,
        include_extension_ids=extension_ids,
        export_markdown=Path(args.export_markdown).expanduser() if args.export_markdown else None,
        attachments=attachments,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"opened", "submitted", "started", "verified", "captured"} else 1


def build_unbrowser_plan(
    *,
    url: str,
    prompt: str = "",
    output: str = "",
    local: bool = True,
    profile: str = "core",
    tool: str = "quick_fetch",
) -> dict[str, Any]:
    package = "@unbrowser/local" if local else "@unbrowser/cloud"
    server_command = ["npx", "-y", package, f"--profile={profile}"]
    arguments = build_unbrowser_tool_arguments(tool=tool, url=url, prompt=prompt)
    return {
        "backend": "unbrowser-local" if local else "unbrowser-cloud",
        "package": package,
        "profile": profile,
        "tool": tool,
        "source": "https://www.unbrowser.ai/",
        "commands": {
            "mcp_server": server_command,
            "probe": [
                sys.executable,
                "skills/software-development/ai-research-browser/scripts/ai_research_browser.py",
                "unbrowser-mcp-probe",
                "--profile",
                profile,
                "--tool",
                tool,
                "--url",
                url,
                *(["--output", output] if output else []),
            ],
        },
        "json_rpc_call": {"method": "tools/call", "params": {"name": tool, "arguments": arguments}},
        "notes": [
            "Unbrowser Local is an MCP stdio server, not a classic browse subcommand CLI.",
            "Use unbrowser-mcp-probe to initialize the server, list tools, and optionally call quick_fetch or smart_browse.",
            "Provider UI actions that spend quota or start Deep Research stay in the local CDP workflow so we can verify account, mode, and screenshots.",
        ],
    }


def cmd_unbrowser_plan(args: argparse.Namespace) -> int:
    payload = build_unbrowser_plan(url=args.url, prompt=args.prompt, output=args.output_path, local=not args.cloud, profile=args.profile, tool=args.tool)
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_unbrowser_tool_arguments(
    *,
    tool: str,
    url: str = "",
    prompt: str = "",
    max_chars: int = 12000,
    session_action: str = "",
    session_domain: str = "",
    session_profile: str = "default",
) -> dict[str, Any]:
    if tool == "session_management":
        arguments: dict[str, Any] = {"action": session_action or "list"}
        if session_domain:
            arguments["domain"] = session_domain
        if session_profile:
            arguments["sessionProfile"] = session_profile
        return arguments
    if tool == "research":
        return {"scope": prompt or url, "maxResults": 5}
    arguments = {}
    if url:
        arguments["url"] = url
    if tool == "smart_browse":
        arguments.update({"contentType": "main_content", "maxChars": max_chars})
    elif tool == "quick_fetch":
        arguments.update({"maxChars": max_chars})
    if prompt:
        arguments["prompt"] = prompt
    return arguments


def mcp_send_json_line(process: subprocess.Popen[bytes], payload: dict[str, Any]) -> None:
    if not process.stdin:
        raise RuntimeError("MCP process stdin is closed")
    process.stdin.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
    process.stdin.flush()


def mcp_read_json_line(
    process: subprocess.Popen[bytes],
    *,
    timeout: float,
    buffer: bytearray,
) -> dict[str, Any] | None:
    if not process.stdout:
        return None
    fd = process.stdout.fileno()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b"\n" in buffer:
            line, _, rest = bytes(buffer).partition(b"\n")
            buffer[:] = rest
            if not line.strip():
                continue
            return json.loads(line.decode("utf-8", errors="replace"))
        readable, _, _ = select.select([fd], [], [], 0.2)
        if readable:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buffer.extend(chunk)
        elif process.poll() is not None:
            break
    return None


def mcp_read_until_id(
    process: subprocess.Popen[bytes],
    request_id: int,
    *,
    timeout: float,
    buffer: bytearray,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = mcp_read_json_line(process, timeout=max(0.2, deadline - time.monotonic()), buffer=buffer)
        if payload is None:
            return None
        events.append(payload)
        if payload.get("id") == request_id:
            return payload
    return None


def run_unbrowser_mcp_probe(
    *,
    url: str,
    tool: str = "quick_fetch",
    profile: str = "core",
    prompt: str = "",
    artifact_root: Path = Path("/tmp/hermes-unbrowser-mcp-probe"),
    timeout: float = 90.0,
    max_chars: int = 12000,
    session_action: str = "",
    session_domain: str = "",
    session_profile: str = "default",
) -> dict[str, Any]:
    artifact_root = artifact_root.expanduser()
    artifact_root.mkdir(parents=True, exist_ok=True)
    command = ["npx", "-y", "@unbrowser/local", f"--profile={profile}"]
    events: list[dict[str, Any]] = []
    started_at = time.time()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(artifact_root),
        start_new_session=True,
    )
    stdout_buffer = bytearray()
    try:
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-research-browser", "version": "0.1"},
            },
        }
        mcp_send_json_line(process, initialize)
        init_response = mcp_read_until_id(process, 1, timeout=min(timeout, 45.0), buffer=stdout_buffer, events=events)
        mcp_send_json_line(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        mcp_send_json_line(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_response = mcp_read_until_id(process, 2, timeout=min(timeout, 45.0), buffer=stdout_buffer, events=events)
        call_response = None
        if url or tool == "session_management":
            arguments = build_unbrowser_tool_arguments(
                tool=tool,
                url=url,
                prompt=prompt,
                max_chars=max_chars,
                session_action=session_action,
                session_domain=session_domain,
                session_profile=session_profile,
            )
            mcp_send_json_line(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
            call_response = mcp_read_until_id(process, 3, timeout=timeout, buffer=stdout_buffer, events=events)
    finally:
        terminate_process(process)
    stderr = ""
    if process.stderr:
        try:
            stderr = process.stderr.read().decode("utf-8", errors="replace")
        except Exception:
            stderr = ""
    tools = []
    if isinstance(tools_response, dict):
        tools = [tool_record.get("name", "") for tool_record in tools_response.get("result", {}).get("tools", [])]
    payload = {
        "backend": "unbrowser-local",
        "status": "ok" if init_response and tools_response and (not url or call_response) else "failed",
        "command": command,
        "cwd": str(artifact_root),
        "profile": profile,
        "tool": tool,
        "url": url,
        "session_action": session_action,
        "session_domain": session_domain,
        "session_profile": session_profile,
        "server_info": (init_response or {}).get("result", {}).get("serverInfo", {}),
        "tools": tools,
        "tool_schemas": (tools_response or {}).get("result", {}).get("tools", []),
        "call_response": call_response,
        "events_path": str(artifact_root / "events.json"),
        "stderr_tail": stderr[-4000:],
        "duration_seconds": round(time.time() - started_at, 3),
    }
    write_json(artifact_root / "events.json", events)
    write_json(artifact_root / "status.json", payload)
    return payload


def cmd_unbrowser_mcp_probe(args: argparse.Namespace) -> int:
    payload = run_unbrowser_mcp_probe(
        url=args.url,
        tool=args.tool,
        profile=args.profile,
        prompt=args.prompt,
        artifact_root=Path(args.artifact_root).expanduser(),
        timeout=args.timeout,
        max_chars=args.max_chars,
        session_action=getattr(args, "session_action", ""),
        session_domain=getattr(args, "session_domain", ""),
        session_profile=getattr(args, "session_profile", "default"),
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


def cmd_unbrowser_session(args: argparse.Namespace) -> int:
    payload = run_unbrowser_mcp_probe(
        url="",
        tool="session_management",
        profile=args.profile,
        artifact_root=Path(args.artifact_root).expanduser(),
        timeout=args.timeout,
        session_action=args.action,
        session_domain=args.domain,
        session_profile=args.session_profile,
    )
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


def cmd_extensions(args: argparse.Namespace) -> int:
    extension_ids: list[str] = []
    if args.extension:
        extension_ids = requested_extension_ids(args.extension)
    if args.ai_exporter:
        extension_ids = requested_extension_ids(extension_ids, include_ai_exporter=True)
    payload = discover_extensions(extension_ids=extension_ids or None)
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_ai_exporter_capabilities(args: argparse.Namespace) -> int:
    payload = build_ai_exporter_capabilities()
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("rows") else 1


def compact_workflow_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    output = payload.get("output") or {}
    inventory = payload.get("inventory") or {}
    clone = payload.get("clone") or {}
    return {
        "status": payload.get("status", ""),
        "status_json": payload.get("status_json", ""),
        "visible_text_path": payload.get("visible_text_path", ""),
        "output_text_path": payload.get("output_text_path", ""),
        "screenshot": payload.get("screenshot", ""),
        "chat_url": payload.get("chat_url", ""),
        "inventory": {
            "provider": inventory.get("provider", ""),
            "login_state": inventory.get("login_state", ""),
            "visible_status": inventory.get("visible_status", {}),
            "available_models": inventory.get("available_models", []),
            "available_tools": inventory.get("available_tools", []),
            "available_modes": inventory.get("available_modes", {}),
        },
        "output": {
            "status": output.get("status", ""),
            "text_length": output.get("text_length", 0),
            "completion_markers_found": output.get("completion_markers_found", []),
            "running_markers_found": output.get("running_markers_found", []),
        },
        "cache": payload.get("cache"),
        "clone": {
            "source_profile": clone.get("source_profile", ""),
            "profile_directory": clone.get("profile_directory", ""),
            "clone_user_data": clone.get("clone_user_data", ""),
        },
    }


def compact_unbrowser_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    call_response = payload.get("call_response") or {}
    content = ((call_response.get("result") or {}).get("content") or []) if isinstance(call_response, dict) else []
    text = ""
    if content and isinstance(content[0], dict):
        text = str(content[0].get("text", ""))
    return {
        "backend": payload.get("backend", ""),
        "status": payload.get("status", ""),
        "profile": payload.get("profile", ""),
        "tool": payload.get("tool", ""),
        "url": payload.get("url", ""),
        "session_action": payload.get("session_action", ""),
        "session_domain": payload.get("session_domain", ""),
        "session_profile": payload.get("session_profile", ""),
        "server_info": payload.get("server_info", {}),
        "tools": payload.get("tools", []),
        "call_text_preview": text[:1200],
        "events_path": payload.get("events_path", ""),
        "duration_seconds": payload.get("duration_seconds", 0),
    }


def cleanup_workflow_clone(payload: dict[str, Any]) -> None:
    clone_user_data = str((payload.get("clone") or {}).get("clone_user_data") or "")
    if not clone_user_data:
        return
    clone_root = Path(clone_user_data).expanduser().parent
    if clone_root.exists() and clone_root.is_dir() and "/tmp/" in str(clone_root):
        shutil.rmtree(clone_root, ignore_errors=True)


def build_notion_export_plan(
    *,
    requested: bool,
    allow_external_write: bool,
    provider: str,
    ai_exporter_capabilities: dict[str, Any],
    workflow_payload: dict[str, Any] | None,
    followup_payload: dict[str, Any] | None,
    workspace_hint: str = "Martin Workspace",
) -> dict[str, Any]:
    rows = [
        row
        for row in ai_exporter_capabilities.get("rows", [])
        if normalize_provider_name(provider) in row.get("supported_providers", [])
    ]
    notion_rows = [
        {
            "browser": row.get("browser", ""),
            "profile_directory": row.get("profile_directory", ""),
            "extension_version": (row.get("extension") or {}).get("version", ""),
            "notion_session_confidence": ((row.get("notion") or {}).get("session_evidence") or {}).get("confidence", ""),
            "actions": [action for action in row.get("actions", []) if "Notion" in action],
        }
        for row in rows
    ]
    source_payload = followup_payload or workflow_payload or {}
    output_text_path = source_payload.get("output_text_path", "")
    status = str(source_payload.get("status", ""))
    eligible_statuses = {"submitted", "started", "verified", "captured"}
    blocked_reasons: list[str] = []
    if not requested:
        blocked_reasons.append("notion-sync-not-requested")
    if not allow_external_write:
        blocked_reasons.append("external-write-not-enabled")
    if not notion_rows:
        blocked_reasons.append("ai-exporter-notion-capability-not-found")
    if status not in eligible_statuses:
        blocked_reasons.append(f"workflow-status-{status or 'missing'}")
    if not output_text_path:
        blocked_reasons.append("no-exportable-output-path")
    return {
        "requested": requested,
        "allow_external_write": allow_external_write,
        "workspace_hint": workspace_hint,
        "eligible": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "source_output_text_path": output_text_path,
        "source_status": status,
        "ai_exporter_rows": notion_rows,
        "intended_action": "saveFullChatsToNotion",
        "safety": {
            "writes_externally": True,
            "local_export_first": True,
            "requires_visible_extension_state": True,
        },
    }


def cmd_workflow_suite(args: argparse.Namespace) -> int:
    browsers = discover_browsers()
    browser_ids = {normalize_browser_name(item.strip()) for item in args.browsers.split(",") if item.strip()}
    providers = requested_provider_ids(args.providers) if args.providers else []
    rows = build_workflow_suite_rows(
        browsers,
        providers=providers,
        browser_ids=browser_ids,
        profile_selector=args.profile,
        all_profiles=args.all_profiles,
        features=args.features,
        include_all_features=args.all_features,
    )
    artifact_root = Path(args.artifact_root).expanduser()
    clone_root = Path(args.clone_root).expanduser()
    extension_ids = requested_extension_ids(getattr(args, "include_extension", None), include_ai_exporter=getattr(args, "include_ai_exporter", False))
    plan_payload = {
        "status": "planned",
        "artifact_root": str(artifact_root),
        "clone_root": str(clone_root),
        "submit": args.submit,
        "confirm_start": args.confirm_start,
        "all_profiles": args.all_profiles,
        "rows": rows,
    }
    if args.plan_only:
        if args.output:
            write_json(Path(args.output).expanduser(), plan_payload)
        print(json.dumps(plan_payload, ensure_ascii=False, indent=2))
        return 0

    browser_map = {normalize_browser_name(str(browser.get("id", ""))): browser for browser in browsers}
    results: list[dict[str, Any]] = []
    for row in rows:
        if args.max_runs and len([item for item in results if item.get("status") != "skipped"]) >= args.max_runs:
            break
        if row.get("status") == "skipped":
            results.append({**row, "run_status": "skipped"})
            continue
        browser = browser_map.get(str(row.get("browser", "")))
        if not browser:
            results.append({**row, "run_status": "blocked", "blocker": "browser not discovered at execution time"})
            if not args.continue_on_failure:
                break
            continue
        try:
            profile = resolve_profile(browser.get("profiles", []), str(row.get("profile_directory", "")))
        except ValueError as exc:
            results.append({**row, "run_status": "blocked", "blocker": str(exc)})
            if not args.continue_on_failure:
                break
            continue
        try:
            run_payload = agent_browser_profile_workflow_run(
                browser=browser,
                profile=profile,
                provider=str(row["provider"]),
                mode=str(row["mode"]),
                prompt=str(row["prompt"]),
                artifact_root=artifact_root,
                clone_root=clone_root,
                submit=args.submit,
                confirm_start=args.confirm_start,
                wait_seconds=args.wait_seconds,
                timeout=args.timeout,
                cache_root=Path(args.cache_root).expanduser() if args.cache else None,
                refresh_cache=not args.no_refresh_cache,
                include_extension_ids=extension_ids,
            )
            run_status = str(run_payload.get("status", "unknown"))
            compact_payload = compact_workflow_run_payload(run_payload)
            if not args.keep_clones:
                cleanup_workflow_clone(run_payload)
            ok_statuses = {"opened", "submitted", "started", "verified", "captured"}
            if args.require_started:
                ok_statuses = {"started", "verified"}
            results.append(
                {
                    **row,
                    "run_status": run_status,
                    "ok": run_status in ok_statuses,
                    **compact_payload,
                }
            )
            if run_status not in ok_statuses and not args.continue_on_failure:
                break
        except Exception as exc:
            results.append({**row, "run_status": "error", "ok": False, "error": str(exc)})
            if not args.continue_on_failure:
                break

    summary = {
        "total": len(results),
        "ok": sum(1 for item in results if item.get("ok")),
        "started_or_verified": sum(1 for item in results if item.get("run_status") in {"started", "verified"}),
        "submitted": sum(1 for item in results if item.get("run_status") == "submitted"),
        "blocked": sum(1 for item in results if item.get("run_status") in {"blocked", "error"}),
    }
    payload = {
        "status": "completed",
        "artifact_root": str(artifact_root),
        "clone_root": str(clone_root),
        "submit": args.submit,
        "confirm_start": args.confirm_start,
        "require_started": args.require_started,
        "summary": summary,
        "results": results,
    }
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if results and all(item.get("ok") or item.get("run_status") == "skipped" for item in results) else 1


def cmd_workflow_orchestrate(args: argparse.Namespace) -> int:
    browser, profile = resolve_workflow_browser_profile(args)
    provider_id = normalize_provider_name(args.provider)
    artifact_root = Path(args.artifact_root).expanduser()
    clone_root = Path(args.clone_root).expanduser()
    prompt = workflow_prompt_from_args(args)
    if not prompt:
        prompt = default_workflow_prompt(provider_id, args.mode)
    extension_ids = requested_extension_ids(getattr(args, "include_extension", None), include_ai_exporter=getattr(args, "include_ai_exporter", False))
    preflight = build_real_session_preflight(browser=browser, profile=profile, provider=provider_id, port=args.port or None)
    unbrowser_payload = None
    if args.unbrowser:
        unbrowser_payload = run_unbrowser_mcp_probe(
            url=args.unbrowser_url or "https://www.unbrowser.ai/",
            prompt=args.prompt,
            profile=args.unbrowser_profile,
            tool=args.unbrowser_tool,
            artifact_root=Path(args.unbrowser_artifact_root).expanduser(),
            timeout=args.timeout,
            max_chars=args.unbrowser_max_chars,
        )
    unbrowser_session_payload = None
    if args.unbrowser_session:
        unbrowser_session_payload = run_unbrowser_mcp_probe(
            url="",
            tool="session_management",
            profile=args.unbrowser_profile,
            artifact_root=Path(args.unbrowser_artifact_root).expanduser() / "session",
            timeout=args.timeout,
            session_action=args.unbrowser_session_action,
            session_domain=args.unbrowser_session_domain or provider_domain(provider_id),
            session_profile=args.unbrowser_session_profile,
        )
    ai_exporter_payload = build_ai_exporter_capabilities() if args.include_ai_exporter or args.notion_sync else {"rows": []}
    ai_exporter_status_path = ""
    if ai_exporter_payload.get("rows"):
        ai_exporter_status_path = str(artifact_root / "ai-exporter-capabilities.json")
        write_json(Path(ai_exporter_status_path), ai_exporter_payload)
    if args.live_cdp:
        workflow_payload = agent_browser_live_workflow_run(
            browser=browser,
            profile=profile,
            provider=provider_id,
            mode=args.mode,
            prompt=prompt,
            artifact_root=artifact_root,
            cdp_port=args.port or int(browser.get("default_port") or 0),
            submit=args.submit,
            confirm_start=args.confirm_start,
            wait_seconds=args.wait_seconds,
            timeout=args.timeout,
            cache_root=Path(args.cache_root).expanduser() if args.cache else None,
            refresh_cache=not args.no_refresh_cache,
            attachments=[Path(item).expanduser() for item in args.attachment],
        )
    else:
        workflow_payload = agent_browser_profile_workflow_run(
            browser=browser,
            profile=profile,
            provider=provider_id,
            mode=args.mode,
            prompt=prompt,
            artifact_root=artifact_root,
            clone_root=clone_root,
            submit=args.submit,
            confirm_start=args.confirm_start,
            wait_seconds=args.wait_seconds,
            timeout=args.timeout,
            cache_root=Path(args.cache_root).expanduser() if args.cache else None,
            refresh_cache=not args.no_refresh_cache,
            include_extension_ids=extension_ids,
            attachments=[Path(item).expanduser() for item in args.attachment],
        )
    followup_payload = None
    if args.followup and workflow_payload.get("chat_url") and workflow_payload.get("status") in {"submitted", "started", "verified", "captured"}:
        followup_payload = agent_browser_profile_followup_run(
            browser=browser,
            profile=profile,
            provider=provider_id,
            chat_url=str(workflow_payload["chat_url"]),
            prompt=args.followup_prompt,
            artifact_root=Path(args.followup_artifact_root).expanduser(),
            clone_root=Path(args.followup_clone_root).expanduser(),
            submit=not args.no_followup_submit,
            wait_seconds=args.followup_wait_seconds,
            timeout=args.timeout,
            cache_root=Path(args.cache_root).expanduser() if args.cache else None,
            refresh_cache=not args.no_refresh_cache,
            include_extension_ids=extension_ids,
            attachments=[Path(item).expanduser() for item in args.followup_attachment],
            export_markdown=Path(args.export_markdown).expanduser() if args.export_markdown else None,
        )
    notion_plan = build_notion_export_plan(
        requested=args.notion_sync,
        allow_external_write=args.allow_external_write,
        provider=provider_id,
        ai_exporter_capabilities=ai_exporter_payload,
        workflow_payload=workflow_payload,
        followup_payload=followup_payload,
        workspace_hint=args.notion_workspace,
    )
    payload = {
        "status": "completed" if workflow_payload.get("status") in {"submitted", "started", "verified", "captured"} else "blocked",
        "provider": provider_id,
        "mode": args.mode,
        "browser": browser.get("id", ""),
        "profile": profile,
        "execution_mode": "live-cdp-background-tab" if args.live_cdp else "temporary-profile-clone-cdp",
        "real_session_preflight": preflight,
        "unbrowser": compact_unbrowser_payload(unbrowser_payload),
        "unbrowser_session": compact_unbrowser_payload(unbrowser_session_payload),
        "ai_exporter_capabilities": {
            "row_count": len(ai_exporter_payload.get("rows", [])),
            "actions": ai_exporter_payload.get("actions", []),
            "status_path": ai_exporter_status_path,
        },
        "workflow": compact_workflow_run_payload(workflow_payload),
        "followup": compact_workflow_run_payload(followup_payload) if followup_payload else None,
        "notion_export_plan": notion_plan,
        "artifacts": {
            "workflow_status_json": workflow_payload.get("status_json", ""),
            "followup_status_json": (followup_payload or {}).get("status_json", ""),
            "unbrowser_events": (unbrowser_payload or {}).get("events_path", ""),
            "unbrowser_session_events": (unbrowser_session_payload or {}).get("events_path", ""),
        },
    }
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "completed" else 1


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
    extensions = sub.add_parser("extensions")
    extensions.add_argument("--extension", action="append", help="Extension id or known alias. Can be repeated or comma-separated.")
    extensions.add_argument("--ai-exporter", action="store_true", help="Filter for the known SaveAI / AI Exporter extension id.")
    extensions.add_argument("--output", default="")
    ai_exporter_capabilities = sub.add_parser("ai-exporter-capabilities")
    ai_exporter_capabilities.add_argument("--output", default="")
    unbrowser_plan = sub.add_parser("unbrowser-plan")
    unbrowser_plan.add_argument("--url", default="")
    unbrowser_plan.add_argument("--prompt", default="")
    unbrowser_plan.add_argument("--output-path", default="")
    unbrowser_plan.add_argument("--cloud", action="store_true")
    unbrowser_plan.add_argument("--profile", default="core", choices=["core", "api", "full"])
    unbrowser_plan.add_argument("--tool", default="quick_fetch", choices=["quick_fetch", "smart_browse", "research", "session_management"])
    unbrowser_plan.add_argument("--output", default="")
    unbrowser_probe = sub.add_parser("unbrowser-mcp-probe")
    unbrowser_probe.add_argument("--url", default="")
    unbrowser_probe.add_argument("--prompt", default="")
    unbrowser_probe.add_argument("--profile", default="core", choices=["core", "api", "full"])
    unbrowser_probe.add_argument("--tool", default="quick_fetch", choices=["quick_fetch", "smart_browse", "research", "session_management"])
    unbrowser_probe.add_argument("--artifact-root", default="/tmp/hermes-unbrowser-mcp-probe")
    unbrowser_probe.add_argument("--timeout", type=float, default=90.0)
    unbrowser_probe.add_argument("--max-chars", type=int, default=12000)
    unbrowser_probe.add_argument("--session-action", default="list", choices=["list", "health"])
    unbrowser_probe.add_argument("--session-domain", default="")
    unbrowser_probe.add_argument("--session-profile", default="default")
    unbrowser_probe.add_argument("--output", default="")
    unbrowser_session = sub.add_parser("unbrowser-session")
    unbrowser_session.add_argument("--profile", default="core", choices=["core", "api", "full"])
    unbrowser_session.add_argument("--action", default="list", choices=["list", "health"])
    unbrowser_session.add_argument("--domain", default="")
    unbrowser_session.add_argument("--session-profile", default="default")
    unbrowser_session.add_argument("--artifact-root", default="/tmp/hermes-unbrowser-session")
    unbrowser_session.add_argument("--timeout", type=float, default=90.0)
    unbrowser_session.add_argument("--output", default="")
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
    real_session_preflight = sub.add_parser("real-session-preflight")
    real_session_preflight.add_argument("--browser", default="brave")
    real_session_preflight.add_argument("--profile", default="work")
    real_session_preflight.add_argument("--provider", choices=provider_cli_choices(), default="google")
    real_session_preflight.add_argument("--port", type=int)
    real_session_preflight.add_argument("--output", default="")
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
    launch_background.add_argument("--output", default="")
    launch_all_background = sub.add_parser("launch-all-background")
    launch_all_background.add_argument("--provider", choices=provider_cli_choices(), required=True)
    launch_all_background.add_argument("--mode", default="chat")
    launch_all_background.add_argument("--model", default="Auto")
    launch_all_background.add_argument("--headless", action="store_true")
    launch_all_background.add_argument("--dry-run", action="store_true")
    launch_all_background.add_argument("--force", action="store_true", help="Launch even when preflight reports running non-CDP browsers.")
    launch_all_background.add_argument("--all-profiles", action="store_true")
    launch_all_background.add_argument("--port-offset", type=int, default=100)
    launch_all_background.add_argument("--output", default="")
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
    live_suite = sub.add_parser("agent-browser-live-suite")
    live_suite.add_argument("--artifact-root", default="/tmp/hermes-ai-research-agent-browser-live-e2e")
    live_suite.add_argument("--providers", default="chatgpt,gemini,claude")
    live_suite.add_argument("--browsers", default="brave", help="Comma-separated browser ids. Defaults to brave.")
    live_suite.add_argument("--profile", default="Work", help="Profile directory or display name to filter, e.g. Work or Default.")
    live_suite.add_argument("--cdp-port", type=int, required=True)
    live_suite.add_argument("--session", default="")
    live_suite.add_argument("--all-features", action="store_true")
    live_suite.add_argument("--open-controls", action="store_true")
    live_suite.add_argument("--assert-login", action="store_true", help="Fail if the live snapshot is signed out or blocked.")
    live_suite.add_argument("--max-runs", type=int, default=0)
    live_suite.add_argument("--timeout", type=float, default=45.0)
    live_suite.add_argument("--output", default="")
    ask = sub.add_parser("agent-browser-ask")
    ask.add_argument("--artifact-root", default="/tmp/hermes-ai-research-agent-browser-ask")
    ask.add_argument("--browser", default="brave")
    ask.add_argument("--profile", default="Work")
    ask.add_argument("--provider", choices=provider_cli_choices(), required=True)
    ask.add_argument("--cdp-port", type=int, required=True)
    ask.add_argument("--session", default="")
    ask.add_argument("--prompt", default="")
    ask.add_argument("--prompt-file", default="")
    ask.add_argument("--submit", action="store_true", help="Actually press Enter after filling the prompt.")
    ask.add_argument("--cache", action="store_true", help="Save visible text to the chat cache after capture.")
    ask.add_argument("--cache-root", default=str(default_chat_cache_root()))
    ask.add_argument("--timeout", type=float, default=90.0)
    ask.add_argument("--output", default="")
    workflow_plan = sub.add_parser("workflow-plan")
    workflow_plan.add_argument("--artifact-root", default="/tmp/hermes-ai-research-workflows")
    workflow_plan.add_argument("--clone-root", default="/tmp/hermes-ai-research-workflow-clones")
    workflow_plan.add_argument("--browser", default="brave")
    workflow_plan.add_argument("--profile", default="work")
    workflow_plan.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_plan.add_argument("--mode", default="chat")
    workflow_plan.add_argument("--prompt", default="")
    workflow_plan.add_argument("--prompt-file", default="")
    workflow_plan.add_argument("--submit", action="store_true")
    workflow_plan.add_argument("--confirm-start", action="store_true")
    workflow_plan.add_argument("--wait-seconds", type=int, default=30)
    workflow_plan.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach through the provider file input when visible.")
    workflow_plan.add_argument("--output", default="")
    workflow_run = sub.add_parser("workflow-run")
    workflow_run.add_argument("--artifact-root", default="/tmp/hermes-ai-research-workflows")
    workflow_run.add_argument("--clone-root", default="/tmp/hermes-ai-research-workflow-clones")
    workflow_run.add_argument("--browser", default="brave")
    workflow_run.add_argument("--profile", default="work")
    workflow_run.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_run.add_argument("--mode", default="chat")
    workflow_run.add_argument("--prompt", default="")
    workflow_run.add_argument("--prompt-file", default="")
    workflow_run.add_argument("--submit", action="store_true", help="Actually send the prompt.")
    workflow_run.add_argument("--confirm-start", action="store_true", help="Click the provider plan/start confirmation when visible.")
    workflow_run.add_argument("--wait-seconds", type=int, default=30)
    workflow_run.add_argument("--timeout", type=float, default=90.0)
    workflow_run.add_argument("--cache", action="store_true")
    workflow_run.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_run.add_argument("--no-refresh-cache", action="store_true")
    workflow_run.add_argument("--include-extension", action="append", help="Copy/load an extension id or alias into the temporary clone.")
    workflow_run.add_argument("--include-ai-exporter", action="store_true", help="Copy/load SaveAI / AI Exporter into the temporary clone.")
    workflow_run.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach through the provider file input when visible.")
    workflow_run.add_argument("--output", default="")
    workflow_live_run = sub.add_parser("workflow-live-run")
    workflow_live_run.add_argument("--artifact-root", default="/tmp/hermes-ai-research-live-workflows")
    workflow_live_run.add_argument("--browser", default="brave")
    workflow_live_run.add_argument("--profile", default="work")
    workflow_live_run.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_live_run.add_argument("--mode", default="chat")
    workflow_live_run.add_argument("--prompt", default="")
    workflow_live_run.add_argument("--prompt-file", default="")
    workflow_live_run.add_argument("--cdp-port", type=int, required=True, help="Attach to an already-started background browser with this CDP port.")
    workflow_live_run.add_argument("--submit", action="store_true", help="Actually send the prompt.")
    workflow_live_run.add_argument("--confirm-start", action="store_true", help="Click the provider plan/start confirmation when visible.")
    workflow_live_run.add_argument("--wait-seconds", type=int, default=30)
    workflow_live_run.add_argument("--timeout", type=float, default=90.0)
    workflow_live_run.add_argument("--cache", action="store_true")
    workflow_live_run.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_live_run.add_argument("--no-refresh-cache", action="store_true")
    workflow_live_run.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach through the provider file input when visible.")
    workflow_live_run.add_argument("--output", default="")
    workflow_sibling_run = sub.add_parser("workflow-sibling-run")
    workflow_sibling_run.add_argument("--artifact-root", default="/tmp/hermes-ai-research-sibling-workflows")
    workflow_sibling_run.add_argument("--browser", default="brave")
    workflow_sibling_run.add_argument("--profile", default="work")
    workflow_sibling_run.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_sibling_run.add_argument("--mode", default="chat")
    workflow_sibling_run.add_argument("--prompt", default="")
    workflow_sibling_run.add_argument("--prompt-file", default="")
    workflow_sibling_run.add_argument("--cdp-port", type=int, help="CDP port for the sibling automation browser. Uses a free port when omitted.")
    workflow_sibling_run.add_argument("--sibling-user-data", default="", help="Dedicated automation user-data-dir. Defaults to ~/.cache/ai-research-browser/sibling-profiles/<browser-profile>/user-data.")
    workflow_sibling_run.add_argument("--refresh-sibling", action="store_true", help="Re-seed the sibling profile from the source profile before launch.")
    workflow_sibling_run.add_argument("--headless", action="store_true", help="Use Chromium headless mode instead of the default offscreen headful mode.")
    workflow_sibling_run.add_argument("--close-after", action="store_true", help="Terminate the launched sibling browser after the workflow. Default leaves it open for long-running research.")
    workflow_sibling_run.add_argument("--submit", action="store_true", help="Actually send the prompt.")
    workflow_sibling_run.add_argument("--confirm-start", action="store_true", help="Click the provider plan/start confirmation when visible.")
    workflow_sibling_run.add_argument("--wait-seconds", type=int, default=30)
    workflow_sibling_run.add_argument("--timeout", type=float, default=90.0)
    workflow_sibling_run.add_argument("--cache", action="store_true")
    workflow_sibling_run.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_sibling_run.add_argument("--no-refresh-cache", action="store_true")
    workflow_sibling_run.add_argument("--include-extension", action="append", help="Copy/load an extension id or alias into the sibling session.")
    workflow_sibling_run.add_argument("--include-ai-exporter", action="store_true", help="Copy/load SaveAI / AI Exporter into the sibling session.")
    workflow_sibling_run.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach through the provider file input when visible.")
    workflow_sibling_run.add_argument("--output", default="")
    workflow_followup = sub.add_parser("workflow-followup")
    workflow_followup.add_argument("--artifact-root", default="/tmp/hermes-ai-research-workflow-followups")
    workflow_followup.add_argument("--clone-root", default="/tmp/hermes-ai-research-workflow-followup-clones")
    workflow_followup.add_argument("--browser", default="brave")
    workflow_followup.add_argument("--profile", default="work")
    workflow_followup.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_followup.add_argument("--chat-url", required=True)
    workflow_followup.add_argument("--prompt", default="Fass den bisherigen Deep-Research-Report kompakt zusammen und nenne die wichtigsten Quellen.")
    workflow_followup.add_argument("--prompt-file", default="")
    workflow_followup.add_argument("--no-submit", action="store_true", help="Fill the follow-up prompt but do not press Enter.")
    workflow_followup.add_argument("--wait-seconds", type=int, default=30)
    workflow_followup.add_argument("--timeout", type=float, default=90.0)
    workflow_followup.add_argument("--cache", action="store_true")
    workflow_followup.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_followup.add_argument("--no-refresh-cache", action="store_true")
    workflow_followup.add_argument("--include-extension", action="append", help="Copy/load an extension id or alias into the temporary clone.")
    workflow_followup.add_argument("--include-ai-exporter", action="store_true", help="Copy/load SaveAI / AI Exporter into the temporary clone.")
    workflow_followup.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach through the provider file input when visible.")
    workflow_followup.add_argument("--export-markdown", default="")
    workflow_followup.add_argument("--output", default="")
    workflow_suite = sub.add_parser("workflow-suite")
    workflow_suite.add_argument("--artifact-root", default="/tmp/hermes-ai-research-workflow-suite")
    workflow_suite.add_argument("--clone-root", default="/tmp/hermes-ai-research-workflow-suite-clones")
    workflow_suite.add_argument("--browsers", default="brave", help="Comma-separated browser ids. Defaults to brave.")
    workflow_suite.add_argument("--profile", default="work")
    workflow_suite.add_argument("--all-profiles", action="store_true")
    workflow_suite.add_argument("--providers", default="chatgpt,gemini,perplexity,grok,claude")
    workflow_suite.add_argument("--features", default="", help="Comma-separated provider:mode entries, e.g. chatgpt:agent,gemini:deep-research.")
    workflow_suite.add_argument("--all-features", action="store_true", help="Run every provider mode supported by workflow-run.")
    workflow_suite.add_argument("--plan-only", action="store_true")
    workflow_suite.add_argument("--submit", action="store_true")
    workflow_suite.add_argument("--confirm-start", action="store_true")
    workflow_suite.add_argument("--require-started", action="store_true", help="Fail submitted-only workflows unless they reach started/verified.")
    workflow_suite.add_argument("--continue-on-failure", action="store_true")
    workflow_suite.add_argument("--max-runs", type=int, default=0)
    workflow_suite.add_argument("--wait-seconds", type=int, default=30)
    workflow_suite.add_argument("--timeout", type=float, default=90.0)
    workflow_suite.add_argument("--cache", action="store_true")
    workflow_suite.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_suite.add_argument("--no-refresh-cache", action="store_true")
    workflow_suite.add_argument("--include-extension", action="append", help="Copy/load an extension id or alias into each temporary clone.")
    workflow_suite.add_argument("--include-ai-exporter", action="store_true", help="Copy/load SaveAI / AI Exporter into each temporary clone.")
    workflow_suite.add_argument("--keep-clones", action="store_true", help="Keep temporary profile clones after each suite row for debugging.")
    workflow_suite.add_argument("--output", default="")
    workflow_orchestrate = sub.add_parser("workflow-orchestrate")
    workflow_orchestrate.add_argument("--artifact-root", default="/tmp/hermes-ai-research-orchestrate")
    workflow_orchestrate.add_argument("--clone-root", default="/tmp/hermes-ai-research-orchestrate-clones")
    workflow_orchestrate.add_argument("--browser", default="brave")
    workflow_orchestrate.add_argument("--profile", default="work")
    workflow_orchestrate.add_argument("--provider", choices=provider_cli_choices(), required=True)
    workflow_orchestrate.add_argument("--mode", default="deep-research")
    workflow_orchestrate.add_argument("--prompt", default="")
    workflow_orchestrate.add_argument("--prompt-file", default="")
    workflow_orchestrate.add_argument("--submit", action="store_true")
    workflow_orchestrate.add_argument("--confirm-start", action="store_true")
    workflow_orchestrate.add_argument("--wait-seconds", type=int, default=30)
    workflow_orchestrate.add_argument("--timeout", type=float, default=90.0)
    workflow_orchestrate.add_argument("--port", type=int, help="Real browser CDP port to preflight.")
    workflow_orchestrate.add_argument("--live-cdp", action="store_true", help="Use the real CDP session and open a new background tab instead of a disposable clone.")
    workflow_orchestrate.add_argument("--cache", action="store_true")
    workflow_orchestrate.add_argument("--cache-root", default=str(default_chat_cache_root()))
    workflow_orchestrate.add_argument("--no-refresh-cache", action="store_true")
    workflow_orchestrate.add_argument("--include-extension", action="append", help="Copy/load an extension id or alias into temporary clones.")
    workflow_orchestrate.add_argument("--include-ai-exporter", action="store_true", help="Copy/load SaveAI / AI Exporter and inspect export/Notion capability.")
    workflow_orchestrate.add_argument("--attachment", action="append", default=[], help="Local file/image path to attach to the first provider workflow.")
    workflow_orchestrate.add_argument("--followup", action="store_true", help="After a started/captured chat, send the configured follow-up prompt.")
    workflow_orchestrate.add_argument("--followup-prompt", default="Fass den bisherigen Deep-Research-Report kompakt zusammen und nenne die wichtigsten Quellen.")
    workflow_orchestrate.add_argument("--no-followup-submit", action="store_true")
    workflow_orchestrate.add_argument("--followup-wait-seconds", type=int, default=30)
    workflow_orchestrate.add_argument("--followup-artifact-root", default="/tmp/hermes-ai-research-orchestrate-followup")
    workflow_orchestrate.add_argument("--followup-clone-root", default="/tmp/hermes-ai-research-orchestrate-followup-clones")
    workflow_orchestrate.add_argument("--followup-attachment", action="append", default=[])
    workflow_orchestrate.add_argument("--export-markdown", default="")
    workflow_orchestrate.add_argument("--unbrowser", action="store_true", help="Run an Unbrowser Local MCP probe as part of the workflow evidence.")
    workflow_orchestrate.add_argument("--unbrowser-url", default="https://www.unbrowser.ai/")
    workflow_orchestrate.add_argument("--unbrowser-profile", default="core", choices=["core", "api", "full"])
    workflow_orchestrate.add_argument("--unbrowser-tool", default="quick_fetch", choices=["quick_fetch", "smart_browse", "research"])
    workflow_orchestrate.add_argument("--unbrowser-artifact-root", default="/tmp/hermes-unbrowser-orchestrate")
    workflow_orchestrate.add_argument("--unbrowser-max-chars", type=int, default=12000)
    workflow_orchestrate.add_argument("--unbrowser-session", action="store_true", help="Run Unbrowser session_management list/health as workflow evidence.")
    workflow_orchestrate.add_argument("--unbrowser-session-action", default="list", choices=["list", "health"])
    workflow_orchestrate.add_argument("--unbrowser-session-domain", default="")
    workflow_orchestrate.add_argument("--unbrowser-session-profile", default="default")
    workflow_orchestrate.add_argument("--notion-sync", action="store_true", help="Plan AI Exporter Save to Notion after local export.")
    workflow_orchestrate.add_argument("--allow-external-write", action="store_true", help="Allow the orchestrator to mark external Notion write as eligible.")
    workflow_orchestrate.add_argument("--notion-workspace", default="Martin Workspace")
    workflow_orchestrate.add_argument("--output", default="")
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
    if args.command == "extensions":
        return cmd_extensions(args)
    if args.command == "ai-exporter-capabilities":
        return cmd_ai_exporter_capabilities(args)
    if args.command == "unbrowser-plan":
        return cmd_unbrowser_plan(args)
    if args.command == "unbrowser-mcp-probe":
        return cmd_unbrowser_mcp_probe(args)
    if args.command == "unbrowser-session":
        return cmd_unbrowser_session(args)
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
    if args.command == "real-session-preflight":
        return cmd_real_session_preflight(args)
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
    if args.command == "agent-browser-live-suite":
        return cmd_agent_browser_live_suite(args)
    if args.command == "agent-browser-ask":
        return cmd_agent_browser_ask(args)
    if args.command == "workflow-plan":
        return cmd_workflow_plan(args)
    if args.command == "workflow-run":
        return cmd_workflow_run(args)
    if args.command == "workflow-live-run":
        return cmd_workflow_live_run(args)
    if args.command == "workflow-sibling-run":
        return cmd_workflow_sibling_run(args)
    if args.command == "workflow-followup":
        return cmd_workflow_followup(args)
    if args.command == "workflow-suite":
        return cmd_workflow_suite(args)
    if args.command == "workflow-orchestrate":
        return cmd_workflow_orchestrate(args)
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
