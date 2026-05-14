---
name: github-pr-workflow
description: Use when creating, updating, reviewing, testing, or merging a GitHub pull request
---

# GitHub PR Workflow

## Overview

Keep pull request work reviewable: one branch, one purpose, clear tests, and a concise body.

## Workflow

1. Inspect status:

```bash
git status --short --branch
git remote -v
```

2. Create a branch with a conventional prefix:

```bash
git checkout -b codex/short-description
```

3. Make scoped changes and run relevant tests.
4. Stage only intended files:

```bash
git add README.md docs/SKILL_CATALOG.md
git diff --cached --stat
```

5. Commit with a precise message:

```bash
git commit -m "docs: improve public skill catalog"
```

6. Push and open the PR:

```bash
git push -u origin HEAD
gh pr create --fill
```

## PR Body

Include:

- Summary
- Verification
- Risk or rollback notes
- Screenshots for visible docs/site changes when useful

## Safety

- Do not include private config, real credentials, private logs, or local cache files.
- Run the repo safety audit before opening public PRs.
