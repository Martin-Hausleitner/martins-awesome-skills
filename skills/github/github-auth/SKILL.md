---
name: github-auth
description: Use when GitHub authentication is missing, broken, or needed before repository, issue, pull request, or CI work
---

# GitHub Auth

## Overview

Choose the least surprising GitHub auth path for the current machine, then verify it before doing repository work.

## Workflow

1. Check what is installed:

```bash
git --version
gh --version 2>/dev/null || true
gh auth status 2>/dev/null || true
```

2. Prefer an already-authenticated `gh` session when available.
3. If `gh` is not authenticated, ask the user to complete `gh auth login`.
4. If `gh` is unavailable, use normal `git` credentials or SSH.
5. Configure commit identity only when needed:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

6. Verify with a read-only command before pushing:

```bash
git ls-remote origin
```

## Safety

- Never paste tokens into committed files.
- Prefer credential helpers or `gh auth login` over token-in-remote URLs.
- Do not print full secrets in summaries, logs, screenshots, or pull requests.
