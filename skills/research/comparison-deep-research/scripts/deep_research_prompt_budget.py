#!/usr/bin/env python3
"""Check whether a Deep Research prompt fits conservative UI budgets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


IDEAL_CHARS = 6_000
STANDARD_MAX_CHARS = 12_000
REVIEW_MAX_CHARS = 24_000


def approx_tokens(text: str) -> int:
    return max(1, round(len(text) / 4)) if text else 0


def classify_prompt(text: str) -> dict[str, object]:
    char_count = len(text)
    token_estimate = approx_tokens(text)
    if char_count <= IDEAL_CHARS:
        level = "ideal"
        allowed = True
        action = "safe for normal Deep Research prompts"
    elif char_count <= STANDARD_MAX_CHARS:
        level = "standard_max"
        allowed = True
        action = "allowed for automated UI submit if other guards pass"
    elif char_count <= REVIEW_MAX_CHARS:
        level = "review"
        allowed = False
        action = "compress first or ask for explicit confirmation"
    else:
        level = "block"
        allowed = False
        action = "do not paste into provider UI; summarize or attach files"

    return {
        "level": level,
        "allowed": allowed,
        "characters": char_count,
        "approx_tokens": token_estimate,
        "limits": {
            "ideal_chars": IDEAL_CHARS,
            "standard_max_chars": STANDARD_MAX_CHARS,
            "review_max_chars": REVIEW_MAX_CHARS,
        },
        "action": action,
    }


def read_prompt(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="Prompt text to measure.")
    parser.add_argument("--file", help="Read prompt text from a file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args(argv)

    result = classify_prompt(read_prompt(args))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"{result['level']}: {result['characters']} chars, "
            f"~{result['approx_tokens']} tokens. {result['action']}."
        )
    return 0 if result["allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

