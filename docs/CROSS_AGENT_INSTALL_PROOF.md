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

## Harness Usage Table

This table explains how each harness is expected to find and use the skills.
It is intentionally written as an operator-facing map, not just an install log.

| Harness | Where the core skills were added | How a user/agent should find them | Best first skill to use | Practical use |
|---|---|---|---|---|
| Hermes | `~/.hermes/skills/software-development/...`, `~/.hermes/skills/productivity/...`, `~/.hermes/skills/research/...` | Hermes skill discovery should show category-preserved names such as `ai-research-browser` and `oracle-ai-research-e2e` | `ai-research-browser-cli` | Operate guarded Brave/Comet live-CDP checks, restart recovery, Deep Research/Agent status JSON, and local evidence |
| Codex | `~/.codex/skills/<skill-name>/SKILL.md` | Restart Codex or refresh skill discovery, then ask for `ai-research-browser`, `oracle-ai-research-e2e`, or `cross-agent-skill-sync` | `ai-research-browser-cli` | Use the CLI recipes while keeping Computer Use/browser validation in the loop |
| Generic Agents | `~/.agents/skills/<skill-name>/SKILL.md` | Agents that read `~/.agents/skills` can discover the flat skill names directly | `cross-agent-skill-sync` | Re-project or verify the shared skill set across other local roots |
| OpenClaw workspace | `~/.openclaw/workspace/skills/<skill-name>/SKILL.md` | OpenClaw-style workspace skill discovery can load the flat skill folders | `ai-research-browser` | Run the browser workflow planning, preflight, and evidence-oriented automation helpers |
| Gemini CLI | `~/.gemini/skills/<skill-name>/SKILL.md` | Gemini-compatible local skill discovery can load the flat folders | `comparison-deep-research` | Generate strict comparison prompts and scorecards before sending work to a research model |
| OpenCode | `~/.config/opencode/skills/<skill-name>/SKILL.md` | OpenCode can discover flat skill folders from its config skill root | `ai-research-browser-cli` | Use reproducible CLI commands and local status artifacts while coding/debugging the harness |
| Claude Code / Claude-adjacent | `~/.claude/skills/<skill-name>/SKILL.md` | Claude-compatible setups vary; this root acts as the default bridge and can be changed with `--target-root` | `oracle-ai-research-e2e` | Validate Oracle assist/reattach behavior and public-safe proof without bypassing local guards |

## Which Skill Should An Agent Pick?

| User intent | Skill to use first | Why |
|---|---|---|
| "Run or debug ChatGPT/Gemini/Comet browser automation" | `ai-research-browser-cli` | It has the shortest operational command recipes and safety rules |
| "Understand or extend the whole browser automation stack" | `ai-research-browser` | It documents the capabilities, strategy router, provider guards, and E2E evidence model |
| "Prove Oracle is integrated with the browser stack" | `oracle-ai-research-e2e` | It focuses on Oracle 0.13 commands, runner blocking, and reattach evidence |
| "Format/publish a finished research result" | `ai-research-output-publisher` | It handles output cards, links, summaries, local export plans, and safe external-write boundaries |
| "Compare many tools, repos, packages, or products" | `comparison-deep-research` | It produces linked comparison prompts with five weighted categories and `/100` scoring |
| "Make every local agent see the same skills" | `cross-agent-skill-sync` | It is the dry-run-first installer/verifier across Hermes, Codex, OpenClaw, Gemini, OpenCode, Claude, and generic roots |

## Skill Content Improvement Checklist

These are the usability improvements that make the skills easier for different
harnesses to apply consistently:

| Improvement | Current status | Why it helps |
|---|---|---|
| Clear "when to use this skill" front matter | Present in all six core skills | Lets agents select the right skill without scanning the whole repo |
| Short first command in each skill | Present | Gives operators a copyable entry point |
| Safety rules before command recipes | Present for browser and Oracle skills | Prevents accidental provider submits, CAPTCHA bypass attempts, or private artifact commits |
| Public-safe install proof | Present in this file | Shows the skill is installed without leaking local account/session data |
| Harness-specific usage map | Present in this file | Helps Codex, Claude, Hermes, Gemini, OpenCode, OpenClaw, and generic agents pick the same workflow |
| One-page "happy path" per harness | Future improvement | Could reduce onboarding friction further by adding a tiny Codex/Hermes/Claude example per target |
| Machine-readable manifest of installed core skills | Future improvement | Would let agents verify install state without parsing Markdown |
| More examples for non-browser skills | Future improvement | `comparison-deep-research` and publisher flows could include more sample outputs |

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
