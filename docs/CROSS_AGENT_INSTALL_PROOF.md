# Cross-Agent Install Proof

This document records a public-safe proof that the core AI research skills are
discoverable from every supported local agent harness. It uses `~`-relative
paths and does not include browser state, accounts, prompts, tokens, or private
session data.

## Verified Command

Dry-run first:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --strategy symlink \
  --require-skill ai-research-browser \
  --require-skill ai-research-browser-cli \
  --require-skill oracle-ai-research-e2e \
  --require-skill ai-research-output-publisher \
  --require-skill comparison-deep-research \
  --require-skill cross-agent-skill-sync \
  --out /tmp/cross-agent-skill-sync-plan.json
```

Execute only after the plan has no warnings:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --strategy symlink \
  --execute \
  --require-skill ai-research-browser \
  --require-skill ai-research-browser-cli \
  --require-skill oracle-ai-research-e2e \
  --require-skill ai-research-output-publisher \
  --require-skill comparison-deep-research \
  --require-skill cross-agent-skill-sync \
  --out /tmp/cross-agent-skill-sync-execute.json \
  --json
```

Latest local execution summary:

```text
targets: 7
skills: 35
actions: 245
exists: 238
installed: 7
warnings: 0
```

## Core Skills

These are the skills that make the browser-research stack findable and usable
from each harness:

| Skill | Purpose |
|---|---|
| `ai-research-browser` | Guarded live-CDP AI provider workflows, account guards, screenshots, status JSON, rate-limit handling |
| `ai-research-browser-cli` | Operational CLI reference for `ai_research_browser.py` |
| `oracle-ai-research-e2e` | Oracle 0.13 assist/reattach validation with the local browser workflow stack |
| `ai-research-output-publisher` | Formats completed research output and local publish/export plans |
| `comparison-deep-research` | Strict comparison prompts with linked candidates, five weighted categories, diagrams, and `/100` scorecards |
| `cross-agent-skill-sync` | Additive, dry-run-first projection into agent skill roots |

## Harness Matrix

Each listed destination has a `SKILL.md` for every core skill above.

| Harness | Skill root | Projection | Verified core skills |
|---|---|---:|---|
| Hermes | `~/.hermes/skills/...` | preserve categories | 6/6 |
| Codex | `~/.codex/skills/...` | flat | 6/6 |
| Generic Agents | `~/.agents/skills/...` | flat | 6/6 |
| OpenClaw workspace | `~/.openclaw/workspace/skills/...` | flat | 6/6 |
| Gemini CLI | `~/.gemini/skills/...` | flat | 6/6 |
| OpenCode | `~/.config/opencode/skills/...` | flat | 6/6 |
| Claude Code / Claude-adjacent | `~/.claude/skills/...` | flat | 6/6 |

## Direct Verification

To verify on a machine after install:

```bash
for root in \
  ~/.hermes/skills \
  ~/.codex/skills \
  ~/.agents/skills \
  ~/.openclaw/workspace/skills \
  ~/.gemini/skills \
  ~/.config/opencode/skills \
  ~/.claude/skills
do
  find "$root" -path '*/SKILL.md' \
    | grep -E 'ai-research-browser|ai-research-browser-cli|oracle-ai-research-e2e|ai-research-output-publisher|comparison-deep-research|cross-agent-skill-sync'
done
```

Claude Code note: Claude-compatible local skill roots vary by setup. This repo
projects to `~/.claude/skills` as a Claude-adjacent bridge; if a Claude Code
installation uses another skill directory, add it with:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target-root claude-custom=/path/to/claude/skills:flat \
  --strategy symlink \
  --execute
```
