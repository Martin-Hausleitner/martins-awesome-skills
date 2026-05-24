---
name: cross-agent-skill-sync
description: Use when discovering, verifying, or sharing SKILL.md based skills across local Hermes, Codex, OpenClaw, Gemini, OpenCode, Claude-adjacent, and generic agent skill roots without overwriting existing skills or leaking private paths.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, sync, hermes, codex, claude, opencode, gemini, openclaw]
    related_skills: [native-mcp, codex, claude-code, hermes-agent, opencode]
---

# Cross-Agent Skill Sync

Use this skill when the user wants the same skill layer to be visible to multiple local agents, including Hermes, Codex, OpenClaw-style workspaces, Gemini CLI, OpenCode, Claude-adjacent setups, and generic `SKILL.md` consumers.

The helper is additive and dry-run-first:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs --target all
```

## Operating Rules

- Never overwrite an existing skill unless the user explicitly asks for a destructive replacement workflow.
- Prefer `--strategy symlink` for local same-machine sharing; use `--strategy copy` for portable snapshots or remote machines.
- Treat paths, prompts, profiles, tokens, memory, browser state, and agent logs as private. The report redacts `$HOME` by default.
- Use `--execute` only after the dry-run plan looks correct.
- Use `--require-skill <name>` for must-have skills, especially bridge skills such as `codex-computer-use-eu-activate`.
- For Claude Code, project skills only into a configured local skill directory or emit docs/indexes. Do not assume Claude consumes arbitrary `SKILL.md` folders unless the local setup has that bridge.

## Common Local Sync

Plan a sync of the repository skills into all known local agent roots:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --require-skill ai-research-browser \
  --require-skill oracle-ai-research-e2e
```

Add an external local skill, such as a Codex Computer Use activation bridge, without committing its private path:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target hermes \
  --include-skill /path/to/codex-computer-use-eu-activate/skill/codex-computer-use-eu-activate \
  --require-skill codex-computer-use-eu-activate
```

Execute after review:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --strategy symlink \
  --execute \
  --out /tmp/cross-agent-skill-sync-report.json
```

## Verification

Run the deterministic tests:

```bash
node --test skills/software-development/cross-agent-skill-sync/tests/cross_agent_skill_sync.test.mjs
```

Then run the repository-wide public safety audit:

```bash
scripts/audit-public-safety.sh
```

## Status Meanings

- `install`: destination is missing and will be created when `--execute` is set.
- `installed`: destination was created in this run.
- `exists`: destination already exists and was left untouched.
- `conflict`: destination exists with different content or an unexpected shape; manual review needed.
- `missing-required-skill`: a required skill was not found in the selected sources.

## Good Boundaries

This skill shares instructions and helper files. It does not share browser cookies, provider sessions, private memories, shell histories, token files, or agent transcripts.
