---
name: notion
description: Use when reading, creating, updating, or organizing Notion pages and databases through the Notion API
---

# Notion

## Martins Setup (kanonisch, Stand 2026-07-14)

- **Aktueller Token:** `cat ~/.config/notion/api_key` (Mac, chmod 600) — Integration **„test"** (Owner Martin). Hat Zugriff u.a. auf die Seite **EDV Hausleitner** (`39c95d5fb89280f4bc5bcb143dff62d5`).
- **Alter Key (Backup):** `~/.config/notion/api_key.leo` — Integration „Leo" (Zugriff: Prectus-Seite). Nur nutzen, wenn eine Seite mit dem aktuellen Token 404 liefert.
- Token NIEMALS ausgeben, loggen oder committen — immer per `$(cat ~/.config/notion/api_key)` einlesen.
- Liefert eine Seite 404: Seite ist nicht mit der Integration geteilt → Operator bitten: ··· → Verbindungen → Integration hinzufügen.
- `Notion-Version: 2022-06-28` verwenden.

## Overview

Use Notion as a structured workspace through its API. Keep integrations narrow, explicit, and easy to revoke.

## Setup

1. Create a Notion integration in the Notion developer settings.
2. Store the token outside the repo:

```bash
export NOTION_API_KEY="YOUR_NOTION_TOKEN"
export NOTION_VERSION="YYYY-MM-DD"
```

3. Share only the needed pages or databases with the integration.
4. Verify access with a read-only request before writing.

## Common Requests

Search:

```bash
curl -s -X POST "https://api.notion.com/v1/search" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: $NOTION_VERSION" \
  -H "Content-Type: application/json" \
  -d '{"query":"project notes"}'
```

Read page blocks:

```bash
curl -s "https://api.notion.com/v1/blocks/PAGE_ID/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: $NOTION_VERSION"
```

## Safety

- Do not commit Notion tokens, page IDs for private workspaces, exports, or database dumps.
- Ask before creating, editing, deleting, or publishing pages.
- Prefer small updates over replacing whole pages.
