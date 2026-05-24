---
name: ai-research-output-publisher
description: Use when turning finished AI research results into clear chat messages, copy-ready summaries, duration metrics, PSPin/deep-research links, and optional Notion pages without exposing private data.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [ai-research, output, notion, clipboard, reporting, deep-research]
    related_skills: [ai-research-browser, oracle-ai-research-e2e, notion]
---

# AI Research Output Publisher

Use this skill after a Deep Research, Agent, or long AI workflow has finished and you need a polished result message plus optional Notion sync.

It does not run the browser workflow itself. It consumes a result JSON file from `ai-research-browser`, Oracle harvest output, or another orchestrator and produces:

- a clear chat message with icon, readable links, and copy-ready summary text;
- support for multiple research results in one notification;
- average research duration and total duration metrics;
- a Notion page payload where the summary appears above the full text;
- optional live Notion page creation only when explicitly allowed.

## Safe Default

Render a message and Notion payload without external writes:

```bash
python3 skills/productivity/ai-research-output-publisher/scripts/ai_research_output_publisher.py render \
  --input /tmp/research-results.json \
  --message-output /tmp/research-message.md \
  --payload-output /tmp/research-notion-payload.json
```

The chat message includes summary text by default. Add `--chat-summary off` when only links and metrics should be shown.

Try the bundled public-safe example:

```bash
python3 skills/productivity/ai-research-output-publisher/scripts/ai_research_output_publisher.py render \
  --input skills/productivity/ai-research-output-publisher/examples/research-results.example.json
```

Expected message shape: [examples/research-message.example.md](examples/research-message.example.md).

## Input Shape

```json
{
  "job_id": "research-batch-001",
  "title": "Weekly AI research",
  "results": [
    {
      "title": "Obsidian AI plugins",
      "provider": "gemini",
      "mode": "deep-research",
      "status": "completed",
      "deep_research_url": "https://example.com/research",
      "pspin_url": "https://example.com/pin",
      "summary": "Short summary shown in chat and at the top of Notion.",
      "text": "Full research report.",
      "research_duration_seconds": 720,
      "total_duration_seconds": 900
    }
  ]
}
```

The script accepts `research_url`, `deep_research_url`, `chat_url`, or `source_url` for the main research link.

## Publish To Notion

Live Notion writes require explicit opt-in:

```bash
NOTION_API_KEY="secret-token" \
python3 skills/productivity/ai-research-output-publisher/scripts/ai_research_output_publisher.py publish-notion \
  --input /tmp/research-results.json \
  --parent-page-id "<notion-parent-page-id>" \
  --allow-external-write
```

Without `--allow-external-write`, the command writes only the planned Notion payload.

## Output Contract

Each notification includes:

- an icon-based headline;
- one row per completed result;
- readable Markdown links for Deep Research and PSPin;
- average research duration and average total duration;
- copy-ready summary text;
- button metadata for copy, Deep Research, PSPin, and Notion page actions.

## Verification

Run the deterministic local E2E test:

```bash
python3 -m unittest discover -s skills/productivity/ai-research-output-publisher/tests -p 'test_*.py'
```

The tests use fake input and a local fake Notion endpoint. They do not write to a real workspace.
