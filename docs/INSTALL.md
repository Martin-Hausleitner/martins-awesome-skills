# Install Skills

## Hermes Agent

Copy any skill folder into your Hermes skills directory:

```bash
mkdir -p ~/.hermes/skills/messaging
cp -R skills/telegram-approval-gate ~/.hermes/skills/messaging/
```

Restart or reload your agent if it caches skill discovery.

## OpenClaw-Style Workspace

Copy into your OpenClaw-style workspace skill directory:

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R skills/telegram-channel-poster ~/.openclaw/workspace/skills/
```

## Codex

Copy public-safe skills into Codex's local skill root. Codex is a flat target by default:

```bash
mkdir -p ~/.codex/skills
cp -R skills/software-development/ai-research-browser-cli ~/.codex/skills/
cp -R skills/software-development/oracle-ai-research-e2e ~/.codex/skills/
```

Restart Codex if it caches skill discovery.

## Claude Code

Claude-compatible local skill roots vary by setup. This repo's sync helper targets `~/.claude/skills` as a flat target by default:

```bash
mkdir -p ~/.claude/skills
cp -R skills/software-development/cross-agent-skill-sync ~/.claude/skills/
```

## Gemini CLI

Install into the Gemini local skill root. Gemini is treated as a flat target by the sync helper:

```bash
mkdir -p ~/.gemini/skills
cp -R skills/research/comparison-deep-research ~/.gemini/skills/
```

## OpenCode

Install into the OpenCode local skill root. OpenCode is treated as a flat target by the sync helper:

```bash
mkdir -p ~/.config/opencode/skills
cp -R skills/software-development/ai-research-browser-cli ~/.config/opencode/skills/
```

## Cross-Agent Sync

Prefer a dry run before projecting skills into multiple local roots:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --source-root skills \
  --target all \
  --require-skill ai-research-browser \
  --require-skill ai-research-browser-cli \
  --require-skill oracle-ai-research-e2e \
  --require-skill ai-research-output-publisher \
  --require-skill comparison-deep-research \
  --require-skill cross-agent-skill-sync
```

Only execute after reviewing the plan:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --source-root skills \
  --target all \
  --strategy symlink \
  --execute \
  --require-skill ai-research-browser \
  --require-skill ai-research-browser-cli \
  --require-skill oracle-ai-research-e2e \
  --require-skill ai-research-output-publisher \
  --require-skill comparison-deep-research \
  --require-skill cross-agent-skill-sync
```

See [CROSS_AGENT_INSTALL_PROOF.md](CROSS_AGENT_INSTALL_PROOF.md) for the
sanitized proof matrix covering Hermes, Codex, OpenClaw, Gemini, OpenCode,
Claude-adjacent, and generic Agents roots.

## Dedicated Telegram Approval Bot

Use a separate bot for approval polling:

```bash
cp config-templates/hermes-approval.env.example .env.telegram-approval
```

Fill the copied file privately. Never commit the real token or chat id.

Do not reuse a bot token that is already being polled by another gateway. Telegram allows only one active `getUpdates` poller per bot token.
