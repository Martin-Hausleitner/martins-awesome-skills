---
name: github-issues
description: Use when triaging, creating, labeling, searching, or closing GitHub issues
---

# GitHub Issues

## Overview

Use issues as lightweight, searchable work records. Keep them specific enough that another agent or human can act without recovering hidden context.

## Common Commands

```bash
gh issue list --limit 20
gh issue view ISSUE_NUMBER --comments
gh issue create --title "Short title" --body "Context, tasks, acceptance criteria"
gh issue edit ISSUE_NUMBER --add-label documentation
gh issue close ISSUE_NUMBER --comment "Resolved by PR #123"
```

## Triage Shape

- Problem: what is broken or missing.
- Evidence: logs, screenshots, commands, or reproduction steps.
- Scope: files, skills, docs, or workflows likely involved.
- Done when: concrete acceptance criteria.

## Safety

- Do not paste private chat logs, tokens, local account data, or personal identifiers into public issues.
- Summarize sensitive evidence instead of copying it verbatim.
