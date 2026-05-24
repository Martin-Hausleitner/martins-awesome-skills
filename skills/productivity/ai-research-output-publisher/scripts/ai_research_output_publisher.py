#!/usr/bin/env python3
"""Render and optionally publish finished AI research outputs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NOTION_VERSION = "2022-06-28"


@dataclass(frozen=True)
class ResearchResult:
    title: str
    provider: str
    mode: str
    status: str
    summary: str
    text: str
    research_url: str
    pspin_url: str
    notion_url: str
    research_duration_seconds: float | None
    total_duration_seconds: float | None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "render":
        return cmd_render(args)
    if args.command == "publish-notion":
        return cmd_publish_notion(args)
    if args.command == "send-chat":
        return cmd_send_chat(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    render = sub.add_parser("render", help="Render chat message, status JSON, and Notion payload.")
    add_common_input_args(render)
    render.add_argument("--message-output", default="", help="Write Markdown chat message to this path.")
    render.add_argument("--status-output", default="", help="Write normalized status JSON to this path.")
    render.add_argument("--payload-output", default="", help="Write Notion payload JSON to this path.")
    render.add_argument("--chat-summary", choices=["on", "off"], default="on")
    render.add_argument("--privacy", choices=["redacted", "full"], default="redacted", help="Redact secret-like values before rendering by default.")
    render.add_argument("--json", action="store_true", help="Print normalized status JSON instead of message text.")

    publish = sub.add_parser("publish-notion", help="Create a Notion page or produce the planned payload.")
    add_common_input_args(publish)
    publish.add_argument("--parent-page-id", default=os.environ.get("NOTION_PARENT_PAGE_ID", ""))
    publish.add_argument("--notion-api-url", default=os.environ.get("NOTION_API_URL", "https://api.notion.com/v1/pages"))
    publish.add_argument("--notion-token", default=os.environ.get("NOTION_API_KEY", ""))
    publish.add_argument("--allow-external-write", action="store_true")
    publish.add_argument("--payload-output", default="")
    publish.add_argument("--status-output", default="")
    publish.add_argument("--privacy", choices=["redacted", "full"], default="redacted", help="Redact secret-like values before rendering/publishing by default.")
    publish.add_argument("--json", action="store_true")

    send_chat = sub.add_parser("send-chat", help="Send or dry-run a finished research notification to a chat/webhook destination.")
    add_common_input_args(send_chat)
    send_chat.add_argument("--channel", choices=["webhook", "discord", "telegram"], required=True)
    send_chat.add_argument("--webhook-url", default=os.environ.get("AI_RESEARCH_WEBHOOK_URL", ""))
    send_chat.add_argument("--telegram-api-url", default=os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org"))
    send_chat.add_argument("--telegram-token", default=os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    send_chat.add_argument("--telegram-chat-id", default=os.environ.get("TELEGRAM_CHAT_ID", ""))
    send_chat.add_argument("--allow-external-write", action="store_true")
    send_chat.add_argument("--chat-summary", choices=["on", "off"], default="on")
    send_chat.add_argument("--privacy", choices=["redacted", "full"], default="redacted", help="Redact secret-like values before sending by default.")
    send_chat.add_argument("--status-output", default="")
    send_chat.add_argument("--json", action="store_true")
    return parser


def add_common_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Research result JSON file.")
    parser.add_argument("--title", default="", help="Override batch title.")
    parser.add_argument("--icon", default="✅", help="Notification icon.")


def cmd_render(args: argparse.Namespace) -> int:
    batch = load_batch(Path(args.input), title_override=args.title)
    batch = apply_privacy(batch, mode=args.privacy)
    message = render_chat_message(batch, icon=args.icon, include_summary=args.chat_summary == "on")
    notion_payload = build_notion_payload(batch)
    status = build_status(batch, message=message, notion_payload=notion_payload, notion_result=None, privacy=args.privacy)

    write_optional(args.message_output, message)
    write_optional(args.payload_output, json.dumps(notion_payload, indent=2, ensure_ascii=False) + "\n")
    write_optional(args.status_output, json.dumps(status, indent=2, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(message)
    return 0


def cmd_publish_notion(args: argparse.Namespace) -> int:
    batch = load_batch(Path(args.input), title_override=args.title)
    batch = apply_privacy(batch, mode=args.privacy)
    payload = build_notion_payload(batch, parent_page_id=args.parent_page_id)
    notion_result: dict[str, Any]

    if not args.allow_external_write:
        notion_result = {
            "status": "planned",
            "external_write": False,
            "reason": "missing --allow-external-write",
        }
    else:
        if not args.parent_page_id:
            raise SystemExit("--parent-page-id or NOTION_PARENT_PAGE_ID is required for live Notion writes")
        if not args.notion_token:
            raise SystemExit("--notion-token or NOTION_API_KEY is required for live Notion writes")
        notion_result = create_notion_page(
            api_url=args.notion_api_url,
            token=args.notion_token,
            payload=payload,
        )

    message = render_chat_message(batch, icon=args.icon, include_summary=True, notion_url=notion_result.get("url", ""))
    status = build_status(batch, message=message, notion_payload=payload, notion_result=notion_result, privacy=args.privacy)
    write_optional(args.payload_output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    write_optional(args.status_output, json.dumps(status, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(message)
    return 0


def cmd_send_chat(args: argparse.Namespace) -> int:
    batch = apply_privacy(load_batch(Path(args.input), title_override=args.title), mode=args.privacy)
    message = render_chat_message(batch, icon=args.icon, include_summary=args.chat_summary == "on")
    status_base = build_status(batch, message=message, notion_payload=build_notion_payload(batch), notion_result=None, privacy=args.privacy)
    if not args.allow_external_write:
        result = {
            "status": "planned",
            "external_write": False,
            "reason": "missing --allow-external-write",
            "channel": args.channel,
        }
    else:
        result = send_chat_message(args, message)
    status = {
        **status_base,
        "status": result.get("status", "planned"),
        "chat_delivery": redact_delivery_result(result),
    }
    write_optional(args.status_output, json.dumps(status, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(message)
    return 0 if result.get("status") in {"planned", "sent"} else 1


def load_batch(path: Path, *, title_override: str = "") -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw_results = raw.get("results")
    if raw_results is None:
        raw_results = [raw]
    if not isinstance(raw_results, list) or not raw_results:
        raise ValueError("input must contain at least one result")
    results = [normalize_result(item) for item in raw_results]
    title = title_override or raw.get("title") or "AI Research Results"
    job_id = raw.get("job_id") or raw.get("id") or f"research-{int(time.time())}"
    return {
        "job_id": job_id,
        "title": title,
        "results": results,
        "metrics": compute_metrics(results),
    }


def normalize_result(item: dict[str, Any]) -> ResearchResult:
    return ResearchResult(
        title=str(item.get("title") or item.get("name") or "Untitled research"),
        provider=str(item.get("provider") or ""),
        mode=str(item.get("mode") or item.get("feature") or ""),
        status=str(item.get("status") or ""),
        summary=str(item.get("summary") or item.get("precis") or item.get("abstract") or ""),
        text=str(item.get("text") or item.get("full_text") or item.get("output") or ""),
        research_url=first_present(item, ["deep_research_url", "research_url", "chat_url", "source_url"]),
        pspin_url=first_present(item, ["pspin_url", "pin_url", "paste_url", "artifact_url"]),
        notion_url=first_present(item, ["notion_url", "notion_page_url"]),
        research_duration_seconds=duration_value(item, ["research_duration_seconds", "research_seconds"], ["research_started_at", "completed_at"]),
        total_duration_seconds=duration_value(item, ["total_duration_seconds", "elapsed_seconds"], ["started_at", "completed_at"]),
    )


def first_present(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def duration_value(item: dict[str, Any], scalar_keys: list[str], timestamp_keys: list[str]) -> float | None:
    for key in scalar_keys:
        value = item.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                pass
    if len(timestamp_keys) == 2 and item.get(timestamp_keys[0]) and item.get(timestamp_keys[1]):
        try:
            return parse_epoch(item[timestamp_keys[1]]) - parse_epoch(item[timestamp_keys[0]])
        except ValueError:
            return None
    return None


def parse_epoch(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    from datetime import datetime

    return datetime.fromisoformat(text).timestamp()


def compute_metrics(results: list[ResearchResult]) -> dict[str, Any]:
    research_values = [result.research_duration_seconds for result in results if result.research_duration_seconds is not None]
    total_values = [result.total_duration_seconds for result in results if result.total_duration_seconds is not None]
    return {
        "result_count": len(results),
        "completed_count": sum(1 for result in results if result.status.lower() in {"completed", "done", "verified"}),
        "average_research_seconds": average(research_values),
        "average_total_seconds": average(total_values),
        "average_research_human": format_seconds(average(research_values)),
        "average_total_human": format_seconds(average(total_values)),
    }


def average(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<redacted-email>"),
    (re.compile(r"\b(?:sk|rk|pk|ghp|github_pat|xox[baprs])-[-A-Za-z0-9_]{12,}\b", re.I), "<redacted-token>"),
    (re.compile(r"\b(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s,;]{6,}", re.I), r"\1=<redacted-secret>"),
    (re.compile(r"\b(?:bearer|basic)\s+[-A-Za-z0-9._~+/]+=*\b", re.I), "<redacted-auth-header>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}:[A-Za-z0-9_-]{2,}:[A-Za-z0-9_-]{2,}\b"), "<redacted-proxy>"),
]


def redact_text(text: str) -> str:
    redacted = str(text or "")
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_url(url: str) -> str:
    text = redact_text(url)
    if not text:
        return ""
    if "?" not in text and "#" not in text:
        return text
    base = re.split(r"[?#]", text, maxsplit=1)[0]
    return f"{base}?<redacted-query>"


def apply_privacy(batch: dict[str, Any], *, mode: str) -> dict[str, Any]:
    if mode == "full":
        return batch
    redacted_results: list[ResearchResult] = []
    for result in batch["results"]:
        redacted_results.append(
            ResearchResult(
                title=redact_text(result.title),
                provider=redact_text(result.provider),
                mode=redact_text(result.mode),
                status=redact_text(result.status),
                summary=redact_text(result.summary),
                text=redact_text(result.text),
                research_url=redact_url(result.research_url),
                pspin_url=redact_url(result.pspin_url),
                notion_url=redact_url(result.notion_url),
                research_duration_seconds=result.research_duration_seconds,
                total_duration_seconds=result.total_duration_seconds,
            )
        )
    return {
        **batch,
        "title": redact_text(batch["title"]),
        "job_id": redact_text(batch["job_id"]),
        "results": redacted_results,
    }


def render_chat_message(
    batch: dict[str, Any],
    *,
    icon: str = "✅",
    include_summary: bool = True,
    notion_url: str = "",
) -> str:
    metrics = batch["metrics"]
    lines = [
        f"{icon} **Research fertig: {batch['title']}**",
        "",
        f"Ergebnisse: {metrics['completed_count']}/{metrics['result_count']} abgeschlossen · "
        f"Ø Recherche: {metrics['average_research_human']} · Ø Gesamt: {metrics['average_total_human']}",
        "",
    ]
    for index, result in enumerate(batch["results"], start=1):
        research_link = markdown_link("Deep Research", result.research_url)
        pspin_link = markdown_link("PSPin", result.pspin_url)
        notion_link = markdown_link("Notion", notion_url or result.notion_url)
        links = " · ".join(link for link in [research_link, pspin_link, notion_link] if link)
        suffix = f" · {links}" if links else ""
        mode_label = " / ".join(part for part in [result.provider, result.mode] if part)
        timing = f"Recherche {format_seconds(result.research_duration_seconds)} · Gesamt {format_seconds(result.total_duration_seconds)}"
        lines.append(f"{index}. **{result.title}** ({mode_label or 'research'}) · {timing}{suffix}")
        if include_summary and result.summary:
            lines.append(f"   {compact(result.summary, 480)}")
    copy_text = build_copy_text(batch)
    lines.extend(
        [
            "",
            "**Copy-Text**",
            "```text",
            copy_text,
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def markdown_link(label: str, url: str) -> str:
    if not url:
        return ""
    return f"[{label}]({url})"


def compact(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def build_copy_text(batch: dict[str, Any]) -> str:
    sections = []
    for result in batch["results"]:
        summary = result.summary or compact(result.text, 800)
        sections.append(f"{result.title}\n{summary}".strip())
    return "\n\n---\n\n".join(sections)


def build_status(
    batch: dict[str, Any],
    *,
    message: str,
    notion_payload: dict[str, Any],
    notion_result: dict[str, Any] | None,
    privacy: str = "redacted",
) -> dict[str, Any]:
    buttons = []
    for result in batch["results"]:
        if result.research_url:
            buttons.append({"label": f"Open {result.title}", "type": "url", "url": result.research_url})
        if result.pspin_url:
            buttons.append({"label": f"PSPin {result.title}", "type": "url", "url": result.pspin_url})
    buttons.append({"label": "Copy summary", "type": "copy_to_clipboard", "value": build_copy_text(batch)})
    if notion_result and notion_result.get("url"):
        buttons.append({"label": "Open Notion", "type": "url", "url": notion_result["url"]})
    return {
        "status": "rendered" if not notion_result else notion_result.get("status", "notion-planned"),
        "job_id": batch["job_id"],
        "title": batch["title"],
        "privacy": {"mode": privacy, "secret_like_values_redacted": privacy == "redacted"},
        "metrics": batch["metrics"],
        "message": message,
        "buttons": buttons,
        "notion": notion_result or {"status": "payload-ready", "external_write": False},
        "notion_payload_preview": {
            "title": notion_payload["properties"]["title"]["title"][0]["text"]["content"],
            "children": len(notion_payload["children"]),
        },
    }


def build_notion_payload(batch: dict[str, Any], *, parent_page_id: str = "") -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    metrics = batch["metrics"]
    children.append(heading("Summary", level=2))
    children.append(paragraph(f"Results: {metrics['completed_count']}/{metrics['result_count']} completed. Average research: {metrics['average_research_human']}. Average total: {metrics['average_total_human']}."))
    for result in batch["results"]:
        children.append(heading(result.title, level=3))
        if result.summary:
            children.extend(markdownish_paragraphs(result.summary))
        link_text = " · ".join(
            part
            for part in [
                f"Deep Research: {result.research_url}" if result.research_url else "",
                f"PSPin: {result.pspin_url}" if result.pspin_url else "",
            ]
            if part
        )
        if link_text:
            children.append(paragraph(link_text))
    children.append(heading("Full Text", level=2))
    for result in batch["results"]:
        children.append(heading(result.title, level=3))
        children.extend(markdownish_paragraphs(result.text or result.summary or "No full text captured."))
    payload: dict[str, Any] = {
        "properties": {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": batch["title"][:200],
                        }
                    }
                ]
            }
        },
        "children": children[:100],
    }
    if parent_page_id:
        payload["parent"] = {"page_id": parent_page_id}
    return payload


def heading(text: str, *, level: int) -> dict[str, Any]:
    key = {2: "heading_2", 3: "heading_3"}.get(level, "heading_2")
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def markdownish_paragraphs(text: str) -> list[dict[str, Any]]:
    chunks = []
    for raw in textwrap.wrap(" ".join(text.split()), width=1800) or [""]:
        chunks.append(paragraph(raw))
    return chunks


def create_notion_page(*, api_url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": os.environ.get("NOTION_VERSION", NOTION_VERSION),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return {"status": "failed", "external_write": True, "http_status": error.code, "error": detail[:800]}
    return {
        "status": "created",
        "external_write": True,
        "id": data.get("id", ""),
        "url": data.get("url", ""),
    }


def send_chat_message(args: argparse.Namespace, message: str) -> dict[str, Any]:
    if args.channel == "webhook":
        if not args.webhook_url:
            raise SystemExit("--webhook-url or AI_RESEARCH_WEBHOOK_URL is required")
        return post_json(args.webhook_url, {"text": message, "message": message, "source": "ai-research-output-publisher"}, channel="webhook")
    if args.channel == "discord":
        if not args.webhook_url:
            raise SystemExit("--webhook-url or AI_RESEARCH_WEBHOOK_URL is required for Discord webhooks")
        return post_json(args.webhook_url, {"content": message[:1900], "allowed_mentions": {"parse": []}}, channel="discord")
    if args.channel == "telegram":
        if not args.telegram_token:
            raise SystemExit("--telegram-token or TELEGRAM_BOT_TOKEN is required")
        if not args.telegram_chat_id:
            raise SystemExit("--telegram-chat-id or TELEGRAM_CHAT_ID is required")
        api_url = args.telegram_api_url.rstrip("/") + f"/bot{args.telegram_token}/sendMessage"
        return post_json(
            api_url,
            {
                "chat_id": args.telegram_chat_id,
                "text": message[:3900],
                "disable_web_page_preview": True,
            },
            channel="telegram",
        )
    raise SystemExit(f"Unsupported channel: {args.channel}")


def post_json(url: str, payload: dict[str, Any], *, channel: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw[:800]}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return {"status": "failed", "external_write": True, "channel": channel, "http_status": error.code, "error": detail[:800]}
    return {"status": "sent", "external_write": True, "channel": channel, "http_status": getattr(response, "status", 0), "response": data}


def redact_delivery_result(result: dict[str, Any]) -> dict[str, Any]:
    return redact_json_value(result)


def redact_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): redact_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_json_value(item) for item in value]
    if isinstance(value, str):
        return redact_url(value) if value.startswith(("http://", "https://")) else redact_text(value)
    return value


def write_optional(path: str, content: str) -> None:
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
