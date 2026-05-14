# Release Checklist

Use this before pushing a public update.

## Content

- [ ] New skills have `name` and `description` frontmatter.
- [ ] Descriptions say when to use the skill, not a full process summary.
- [ ] README and `docs/SKILL_CATALOG.md` include new skills.
- [ ] Examples use placeholders, not real accounts, tokens, chat IDs, or machine paths.
- [ ] Private OpenClaw, Hermes, OpenCloud, chat, memory, health, accounting, and location material is excluded.

## Verification

```bash
scripts/audit-public-safety.sh
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
(cd skills/telegram-channel-poster && python3 scripts/test_telegram_channel_post.py)
```

## GitHub

- [ ] Repo description still communicates public-safe scope.
- [ ] Topics are relevant and discoverable.
- [ ] The release commit only contains public-safe files.
- [ ] No generated local caches are staged.
