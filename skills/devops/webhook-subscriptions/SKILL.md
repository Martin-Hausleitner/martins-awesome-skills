---
name: webhook-subscriptions
description: Use when external services should trigger agent runs through webhook events
---

# Webhook Subscriptions

## Overview

Webhook-triggered agents are powerful because they turn external events into work. Treat every webhook as an untrusted public input unless proven otherwise.

## Setup Pattern

1. Confirm the gateway or webhook receiver is available.
2. Generate a strong per-subscription secret outside the repo.
3. Subscribe to the smallest event set that solves the task.
4. Test with a synthetic payload.
5. Log only event metadata, not secret headers or private payload fields.

## Example Shape

```bash
hermes webhook subscribe repo-issues \
  --events "issues" \
  --prompt "Triage this issue event and propose next steps." \
  --skills "github-issues,github-code-review"
```

## Verification

```bash
hermes webhook list
hermes webhook test repo-issues --payload '{"action":"opened"}'
```

## Safety

- Require HMAC validation or an equivalent signature check.
- Keep webhook secrets in environment variables or a private config file.
- Do not commit event payloads from production systems.
- Prefer dry-run delivery until the prompt is proven safe.
