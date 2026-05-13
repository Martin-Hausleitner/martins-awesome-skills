#!/usr/bin/env python3
"""Telegram inline-button approval gate for Hermes drafts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ACTIONS = {"send", "edit", "cancel"}


def _env_file_values(start: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for directory in [start, *start.parents]:
        env_path = directory / ".env"
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip("'\""))
    return values


def _read_draft(args: argparse.Namespace) -> str:
    if args.draft_file:
        return Path(args.draft_file).expanduser().read_text(encoding="utf-8").strip()
    if args.draft:
        return args.draft.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise SystemExit("Provide --draft, --draft-file, or stdin.")


def _post_json(base_url: str, method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {body}") from exc


def _get_json(base_url: str, method: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/{method}?{query}", timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_approval(base_url: str, chat_id: str, title: str, draft: str) -> int:
    text = f"{title}\n\n{draft}"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Senden", "callback_data": "approval:send"},
                {"text": "Bearbeiten", "callback_data": "approval:edit"},
            ],
            [{"text": "Abbrechen", "callback_data": "approval:cancel"}],
        ]
    }
    result = _post_json(
        base_url,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:4096],
            "reply_markup": reply_markup,
            "disable_web_page_preview": True,
        },
    )
    if not result.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {result}")
    return int(result["result"]["message_id"])


def _answer_callback(base_url: str, callback_id: str, text: str) -> None:
    _post_json(base_url, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


def _edit_status(base_url: str, chat_id: str, message_id: int, action: str) -> None:
    labels = {"send": "Freigegeben", "edit": "Bearbeitung angefordert", "cancel": "Abgebrochen"}
    _post_json(
        base_url,
        "editMessageReplyMarkup",
        {"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}},
    )
    _post_json(
        base_url,
        "sendMessage",
        {"chat_id": chat_id, "text": f"Approval: {labels[action]}."},
    )


def _wait_for_decision(base_url: str, chat_id: str, message_id: int, timeout_s: int) -> dict:
    offset = 0
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = _get_json(base_url, "getUpdates", {"timeout": 25, "offset": offset})
        if not result.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {result}")
        for update in result.get("result", []):
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            callback = update.get("callback_query")
            if not callback:
                continue
            data = callback.get("data", "")
            message = callback.get("message", {})
            if message.get("message_id") != message_id:
                continue
            if str(message.get("chat", {}).get("id")) != str(chat_id):
                continue
            action = data.split(":", 1)[1] if data.startswith("approval:") else ""
            if action not in ACTIONS:
                continue
            _answer_callback(base_url, callback["id"], action)
            _edit_status(base_url, chat_id, message_id, action)
            return {"status": "ok", "decision": action, "message_id": message_id}
    return {"status": "timeout", "decision": "cancel", "message_id": message_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Telegram approval card for an outgoing draft.")
    parser.add_argument("--draft")
    parser.add_argument("--draft-file")
    parser.add_argument("--title", default="Hermes Freigabe")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("HERMES_APPROVAL_TIMEOUT", "900")))
    parser.add_argument("--bot-token", default=os.getenv("HERMES_APPROVAL_BOT_TOKEN"))
    parser.add_argument("--chat-id", default=os.getenv("HERMES_APPROVAL_CHAT_ID"))
    parser.add_argument("--api-base", default=os.getenv("HERMES_APPROVAL_API_BASE"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_values = _env_file_values(Path.cwd())
    token = args.bot_token or env_values.get("HERMES_APPROVAL_BOT_TOKEN")
    chat_id = args.chat_id or env_values.get("HERMES_APPROVAL_CHAT_ID")
    draft = _read_draft(args)

    if args.dry_run:
        print(json.dumps({"status": "dry-run", "title": args.title, "draft": draft}, ensure_ascii=False, indent=2))
        return 0
    if not token and not args.api_base:
        raise SystemExit("Missing HERMES_APPROVAL_BOT_TOKEN.")
    if not chat_id:
        raise SystemExit("Missing HERMES_APPROVAL_CHAT_ID.")

    base_url = args.api_base or f"https://api.telegram.org/bot{token}"
    message_id = _send_approval(base_url, chat_id, args.title, draft)
    print(json.dumps(_wait_for_decision(base_url, chat_id, message_id, args.timeout), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
