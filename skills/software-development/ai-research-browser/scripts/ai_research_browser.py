#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
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
}


def provider_registry() -> dict[str, dict[str, Any]]:
    return {
        "chatgpt": {
            "url": "https://chatgpt.com/",
            "modes": ["chat", "deep-research", "agent"],
            "models": ["default", "GPT-5.2", "GPT-5.2 Thinking", "GPT-4.1", "GPT-4.1 mini"],
            "mode_markers": {
                "deep-research": ["Deep research", "/Deepresearch", "Start research"],
                "agent": ["Agent", "/agent", "Take control", "Codex"],
                "chat": ["ChatGPT", "Message ChatGPT"],
            },
        },
        "gemini": {
            "url": "https://gemini.google.com/app?hl=de",
            "modes": ["chat", "deep-research", "agent"],
            "models": ["Fast", "Thinking", "Pro"],
            "mode_markers": {
                "deep-research": ["Deep Research", "Recherche starten", "Start research"],
                "agent": ["Agent", "Confirm", "Bestätigen"],
                "chat": ["Gemini", "Prompt eingeben"],
            },
        },
        "perplexity": {
            "url": "https://www.perplexity.ai/",
            "modes": ["chat", "research"],
            "models": ["Best", "Sonar", "GPT-5.2", "Claude Sonnet", "Gemini Pro"],
            "mode_markers": {"research": ["Research", "Deep Research"], "chat": ["Perplexity"]},
        },
        "claude": {
            "url": "https://claude.ai/new",
            "aliases": ["anthropic"],
            "modes": ["chat", "research", "artifacts"],
            "models": ["default", "Claude Sonnet", "Claude Opus"],
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
            "models": ["Auto", "Grok 4.1", "Grok 4.1 Thinking"],
            "mode_markers": {"research": ["Research", "DeepSearch", "Think"], "chat": ["Grok", "Ask anything"]},
        },
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def discover_profiles(user_data_dir: str | Path) -> list[dict[str, str]]:
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
        display_name = data.get("name") or prefs.get("profile", {}).get("name") or directory
        profiles.append(
            {
                "directory": directory,
                "name": str(display_name),
                "account": str(account),
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
                        "name": str(prefs.get("profile", {}).get("name") or child.name),
                        "account": str(((prefs.get("account_info") or [{}])[0].get("email") if isinstance(prefs.get("account_info"), list) else "") or ""),
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


def discover_browsers() -> list[dict[str, Any]]:
    out = []
    for key, cfg in BROWSER_CANDIDATES.items():
        app_path = Path(str(cfg["app_path"])).expanduser()
        user_data_dir = Path(str(cfg["user_data_dir"])).expanduser()
        if not app_path.exists() and not user_data_dir.exists():
            continue
        profiles = discover_profiles(user_data_dir)
        out.append(
            {
                "id": key,
                "display_name": cfg["display_name"],
                "app_path": str(app_path),
                "binary_path": str(app_path / str(cfg["binary_rel"])),
                "user_data_dir": str(user_data_dir),
                "default_port": cfg["default_port"],
                "profiles": profiles,
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


def parse_visible_status(text: str) -> dict[str, Any]:
    account_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text or "")
    model_match = re.search(r"Model:\s*([^\n]+)", text or "", flags=re.I)
    deep_match = re.search(r"(?:Deep research|Rechercheberichte?)\D{0,40}(\d+)\s*(?:remaining|left|übrig|verbleibend)?", text or "", flags=re.I)
    agent_match = re.search(r"(?:Agent tasks?|Agent)\D{0,40}(\d+)\s*(?:remaining|left|übrig|verbleibend)?", text or "", flags=re.I)
    return {
        "account": account_match.group(0) if account_match else "",
        "model": model_match.group(1).strip() if model_match else "",
        "quotas": {
            "deep_research_remaining": int(deep_match.group(1)) if deep_match else None,
            "agent_remaining": int(agent_match.group(1)) if agent_match else None,
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
    if process_args and "--remote-debugging-port" not in process_args:
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


def build_test_matrix(browsers: list[dict[str, Any]], providers: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    provider_map = providers or provider_registry()
    rows: list[dict[str, Any]] = []
    for browser in browsers:
        profiles = browser.get("profiles") or [{"directory": "", "name": "", "account": ""}]
        for profile in profiles:
            for provider_id, provider in provider_map.items():
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
                            "status": "untested",
                        }
                    )
    return rows


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
        "quotas": visible_status.get("quotas", {}),
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
    }
    payload["matrix"] = build_test_matrix(payload["browsers"], payload["providers"])
    if args.output:
        write_json(Path(args.output).expanduser(), payload)
    print(json.dumps(payload if args.json else payload["matrix"], ensure_ascii=False, indent=2))
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
    launch_args = build_launch_args(
        browser,
        profile_directory=profile_choice["id"],
        port=args.port or int(browser["default_port"]),
        provider=provider_id,
        mode=feature_choice["id"],
        headless=not args.headful,
    )
    payload = {
        "selection": {
            "browser": browser["id"],
            "profile": profile_choice["id"],
            "provider": provider_id,
            "feature": feature_choice["id"],
        },
        "account_status": account_status_record(
            browser=browser["id"],
            profile=resolve_profile(browser.get("profiles", []), profile_choice["id"]),
            provider=provider_id,
        ),
        "launch_args": launch_args,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    browsers = {b["id"]: b for b in discover_browsers()}
    browser_id = normalize_browser_name(args.browser)
    if browser_id not in browsers:
        raise SystemExit(f"browser not discovered: {args.browser}")
    browser = browsers[browser_id]
    profile = resolve_profile(browser["profiles"], args.profile)
    port = args.port or int(browser["default_port"])
    blockers = detect_launch_blockers(
        browser_name=str(browser["display_name"]),
        port=port,
        port_owner=port_owner(port),
        process_args=process_args_for_browser(str(browser["display_name"])),
    )
    print(json.dumps({"browser": browser, "profile": profile, "port": port, "blockers": blockers}, ensure_ascii=False, indent=2))
    return 2 if blockers else 0


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
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--json", action="store_true", help="Include discovered browsers and provider registry.")
    matrix.add_argument("--output", default="")
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
    launch.add_argument("--port", type=int)
    launch.add_argument("--headful", action="store_true")
    launch.add_argument("--artifact-root", default="")
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
    if args.command == "matrix":
        return cmd_matrix(args)
    if args.command == "accounts":
        return cmd_accounts(args)
    if args.command == "wizard":
        return cmd_wizard(args)
    if args.command == "preflight":
        return cmd_preflight(args)
    if args.command == "launch-args":
        browsers = {b["id"]: b for b in discover_browsers()}
        browser_id = normalize_browser_name(args.browser)
        if browser_id not in browsers:
            raise SystemExit(f"browser not discovered: {args.browser}")
        browser = browsers[browser_id]
        profile = resolve_profile(browser["profiles"], args.profile)
        launch_args = build_launch_args(
            browser,
            profile_directory=profile["directory"],
            port=args.port or int(browser["default_port"]),
            provider=normalize_provider_name(args.provider),
            mode=args.mode,
            headless=not args.headful,
        )
        payload = {
            "browser": browser["id"],
            "profile": profile,
            "provider": normalize_provider_name(args.provider),
            "mode": args.mode,
            "launch_args": launch_args,
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
