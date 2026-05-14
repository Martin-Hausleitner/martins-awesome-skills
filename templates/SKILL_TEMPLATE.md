---
name: example-skill-name
description: Use when a reusable workflow needs a public-safe, skill-compatible guide
---

# Example Skill Name

## Overview

State the core purpose in one or two sentences. Keep the skill reusable and avoid private workspace assumptions.

## When to Use

- The user asks for this workflow directly.
- The task matches the trigger language in the description.
- The workflow is repeatable across projects or machines.

## Inputs

- Required: list required commands, files, API keys, or permissions.
- Optional: list nice-to-have context.
- Never require real secrets in the repo. Use placeholders and environment variables.

## Workflow

1. Inspect the local context before changing anything.
2. Prefer dry runs for external side effects.
3. Make the smallest useful change.
4. Verify with deterministic tests or explicit checks.
5. Summarize what changed, what passed, and what still needs human input.

## Safety

- Do not commit `.env`, auth databases, memory files, chat exports, session logs, cookies, or private keys.
- Ask before sending messages, publishing posts, opening pull requests, or changing public settings.
- Use placeholders such as `YOUR_TOKEN_HERE`, never realistic secret examples.

## Verification

```bash
# Add the fastest useful local check here.
echo "replace with a real command"
```
