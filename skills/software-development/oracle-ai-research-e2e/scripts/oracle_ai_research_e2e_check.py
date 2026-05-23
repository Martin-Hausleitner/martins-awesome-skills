#!/usr/bin/env python3
"""Public-safe Oracle + ai-research-browser integration checker."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def repo_root_from_script() -> Path:
    env_root = os.environ.get("AI_RESEARCH_BROWSER_REPO_ROOT", "")
    candidates = [
        Path(env_root).expanduser() if env_root else None,
        Path.cwd(),
        Path(__file__).resolve().parents[4],
    ]
    marker = Path("skills/software-development/ai-research-browser/scripts/ai_research_browser.py")
    for candidate in candidates:
        if candidate and (candidate.resolve() / marker).exists():
            return candidate.resolve()
    return Path(__file__).resolve().parents[4]


def run_command(command: list[str], *, cwd: Path, expect: set[int] | None = None, timeout: int = 180) -> dict[str, Any]:
    expected = expect or {0}
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    ok = result.returncode in expected
    return {
        "ok": ok,
        "returncode": result.returncode,
        "expected_returncodes": sorted(expected),
        "command": redact_command(command),
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-6000:],
    }


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_value = False
    sensitive_flags = {"--prompt", "-p"}
    for item in command:
        if skip_value:
            redacted.append("<redacted>")
            skip_value = False
            continue
        redacted.append(item)
        if item in sensitive_flags:
            skip_value = True
    return redacted


def parse_json_stdout(step: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(step.get("stdout") or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def assert_payload(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Oracle 0.13 integration with ai-research-browser.")
    parser.add_argument("--repo-root", default=str(repo_root_from_script()))
    parser.add_argument("--browser", default="brave")
    parser.add_argument("--profile", default="work")
    parser.add_argument("--provider", default="chatgpt", choices=["chatgpt", "gemini", "google"])
    parser.add_argument("--mode", default="thinking", choices=["thinking", "agent", "deep-research"])
    parser.add_argument("--cdp-port", type=int, default=9223)
    parser.add_argument("--live", action="store_true", help="Run opt-in real provider E2E via oracle-e2e-smoke.")
    parser.add_argument("--quick", action="store_true", help="Run targeted tests instead of the full ai-research-browser unit suite.")
    parser.add_argument("--skip-public-safety", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root).expanduser().resolve()
    arb = root / "skills/software-development/ai-research-browser/scripts/ai_research_browser.py"
    failures: list[str] = []
    steps: list[dict[str, Any]] = []

    def record(name: str, command: list[str], *, expect: set[int] | None = None, timeout: int = 180) -> dict[str, Any]:
        step = run_command(command, cwd=root, expect=expect, timeout=timeout)
        step["name"] = name
        steps.append(step)
        if not step["ok"]:
            failures.append(f"{name} returned {step['returncode']}, expected {step['expected_returncodes']}")
        return step

    record("py_compile", ["python3", "-m", "py_compile", str(arb.relative_to(root))])

    if args.quick:
        for pattern in ["oracle", "chatgpt_model_safety", "slash_feature"]:
            record(
                f"unit_{pattern}",
                [
                    "python3",
                    "-m",
                    "unittest",
                    "skills/software-development/ai-research-browser/tests/test_ai_research_browser.py",
                    "-k",
                    pattern,
                ],
                timeout=90,
            )
    else:
        record(
            "unit_ai_research_browser",
            [
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "skills/software-development/ai-research-browser/tests",
                "-p",
                "test_ai_research_browser.py",
            ],
            timeout=240,
        )

    oracle_plan = record(
        "oracle_plan",
        [
            "python3",
            str(arb.relative_to(root)),
            "oracle-plan",
            "-p",
            "Validate Oracle integration with ai-research-browser.",
            "--provider",
            args.provider,
            "--mode",
            "deep-research" if args.mode == "deep-research" else args.mode,
            "--remote-chrome",
            f"127.0.0.1:{args.cdp_port}",
            "--research-depth",
            "deep",
            "--browser-attachment-timeout",
            "240",
        ],
    )
    plan_payload = parse_json_stdout(oracle_plan)
    plan_command = plan_payload.get("consult_dry_run") or []
    assert_payload(plan_payload.get("package") == "@steipete/oracle@0.13.0", "oracle-plan did not pin @steipete/oracle@0.13.0", failures)
    assert_payload("--browser-attach-running" in plan_command, "oracle-plan missing --browser-attach-running", failures)
    assert_payload("--remote-chrome" in plan_command, "oracle-plan missing --remote-chrome", failures)
    assert_payload("--browser-research" in plan_command, "oracle-plan missing --browser-research", failures)
    assert_payload(bool(plan_payload.get("reattach")), "oracle-plan missing reattach command", failures)
    assert_payload("--render" in (plan_payload.get("show_session") or []), "oracle-plan missing session --render", failures)

    runner = record(
        "workflow_runner_blocked",
        [
            "python3",
            str(arb.relative_to(root)),
            "workflow-run",
            "--browser",
            args.browser,
            "--profile",
            args.profile,
            "--provider",
            "chatgpt",
            "--mode",
            "agent",
            "--prompt",
            "Validate guarded Oracle runner behavior.",
            "--strategy",
            "auto",
            "--oracle-mode",
            "runner",
            "--cdp-port",
            "59999",
            "--allow-paid-quota-use",
        ],
        expect={1},
    )
    runner_payload = parse_json_stdout(runner)
    assert_payload(runner_payload.get("oracle", {}).get("runner_status") == "blocked-by-local-guards", "Oracle runner did not block behind local guards", failures)
    assert_payload(runner_payload.get("oracle_evidence", {}).get("prompt_redacted") is True, "Oracle runner evidence did not redact prompt", failures)

    smoke = record(
        "oracle_e2e_smoke_opt_in_block",
        [
            "python3",
            str(arb.relative_to(root)),
            "oracle-e2e-smoke",
            "--browser",
            args.browser,
            "--profile",
            args.profile,
            "--provider",
            args.provider,
            "--mode",
            args.mode,
        ],
        expect={1},
    )
    smoke_payload = parse_json_stdout(smoke)
    assert_payload(smoke_payload.get("blocker") == "real Oracle E2E smoke requires AI_RESEARCH_BROWSER_E2E=1", "oracle-e2e-smoke did not enforce opt-in", failures)

    if not args.skip_public_safety:
        record("public_safety", ["scripts/audit-public-safety.sh"], timeout=90)

    if args.live:
        if os.environ.get("AI_RESEARCH_BROWSER_E2E") != "1":
            failures.append("--live requires AI_RESEARCH_BROWSER_E2E=1")
        else:
            record(
                "oracle_e2e_smoke_live",
                [
                    "python3",
                    str(arb.relative_to(root)),
                    "oracle-e2e-smoke",
                    "--browser",
                    args.browser,
                    "--profile",
                    args.profile,
                    "--provider",
                    args.provider,
                    "--mode",
                    args.mode,
                    "--cdp-port",
                    str(args.cdp_port),
                    "--oracle-mode",
                    "assist",
                ],
                timeout=900,
            )

    payload = {
        "ok": not failures,
        "repo_root": str(root),
        "live": bool(args.live),
        "failures": failures,
        "steps": steps,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("PASS" if payload["ok"] else "FAIL")
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
