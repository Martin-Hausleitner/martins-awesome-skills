#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    if provider not in providers:
        raise ValueError(f"unknown provider: {provider}")
    return str(providers[provider]["url"])


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


def build_artifact_paths(root: Path, *, provider: str, mode: str, browser: str, profile: str) -> dict[str, Path]:
    run_dir = root / f"{slug(provider)}-{slug(mode)}-{slug(browser)}-{slug(profile)}"
    return {
        "run_dir": run_dir,
        "status_json": run_dir / "status.json",
        "screenshot_png": run_dir / "screenshot.png",
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
        provider=args.provider,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover browser profiles and run AI research/agent workflows with E2E artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--browser", required=True)
    preflight.add_argument("--profile", default="Default")
    preflight.add_argument("--port", type=int)
    launch = sub.add_parser("launch-args")
    launch.add_argument("--browser", required=True)
    launch.add_argument("--profile", default="Default")
    launch.add_argument("--provider", choices=sorted(provider_registry().keys()), required=True)
    launch.add_argument("--mode", default="chat")
    launch.add_argument("--port", type=int)
    launch.add_argument("--headful", action="store_true")
    launch.add_argument("--artifact-root", default="")
    verify = sub.add_parser("verify-text")
    verify.add_argument("--provider", choices=sorted(provider_registry().keys()), required=True)
    verify.add_argument("--mode", required=True)
    verify.add_argument("--text-file", default="")
    record = sub.add_parser("record-e2e")
    record.add_argument("--artifact-root", required=True)
    record.add_argument("--provider", choices=sorted(provider_registry().keys()), required=True)
    record.add_argument("--mode", required=True)
    record.add_argument("--browser", required=True)
    record.add_argument("--profile", required=True)
    record.add_argument("--status", choices=["blocked", "selected", "started", "verified", "failed"], required=True)
    record.add_argument("--screenshot", default="")
    record.add_argument("--text-file", default="")
    record.add_argument("--note", action="append")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "discover":
        return cmd_discover(args)
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
            provider=args.provider,
            mode=args.mode,
            headless=not args.headful,
        )
        payload = {
            "browser": browser["id"],
            "profile": profile,
            "provider": args.provider,
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
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
