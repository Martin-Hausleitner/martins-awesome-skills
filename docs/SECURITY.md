# Security Checklist

This repository is public. Treat every commit as permanent.

## Never Commit

- real `.env` files
- `auth.json`, cookies, browser profiles, OAuth caches, or credential stores
- bot tokens, GitHub tokens, API keys, private keys, certificates, or session tokens
- `MEMORY.md`, `USER.md`, daily memory files, chat exports, transcripts, or trajectories
- accounting, health, location, clipboard, Find My, or private automation data
- private local paths, device names, account ids, Telegram chat ids, or one-off workspace setup

## Before Pushing

Run:

```bash
scripts/audit-public-safety.sh
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
(cd skills/telegram-channel-poster && python3 scripts/test_telegram_channel_post.py)
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py'
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
python3 -m unittest discover -s skills/productivity/ai-research-output-publisher/tests -p 'test_*.py'
python3 -m unittest discover -s skills/research/comparison-deep-research/tests -p 'test_*.py'
node --test tests/skill-sync-doctor.test.mjs
node --test skills/software-development/cross-agent-skill-sync/tests/cross_agent_skill_sync.test.mjs
```

Review all staged changes:

```bash
git diff --staged --stat
git diff --staged
```

## Pattern Policy

Examples must use placeholders like:

```text
<api-key-placeholder>
<github-token-placeholder>
@your_channel_username
```

Avoid realistic-looking secrets. They make scanners noisy and train bad habits.
