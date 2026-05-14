---
name: notion
description: Use when reading, creating, updating, or organizing Notion pages and databases through the Notion API
---

# Notion

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
