# Contributing

Thanks for improving Martin's Awesome Skills.

## Good Contributions

- Public-safe skills with reusable workflows.
- Small deterministic scripts or tests next to a skill.
- Docs that help people install, verify, or adapt skills.
- SVGs or examples that make the catalog clearer without embedding private data.

## Before Opening a PR

Run:

```bash
scripts/audit-public-safety.sh
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
(cd skills/telegram-channel-poster && python3 scripts/test_telegram_channel_post.py)
```

Also check:

- No `.env`, token, cookie, session, chat export, memory, accounting, location, or private automation file is included.
- No local machine path or personal account ID appears in examples.
- New skills are listed in `README.md` and `docs/SKILL_CATALOG.md`.

## Skill Style

Use `templates/SKILL_TEMPLATE.md` as the starting point. Keep skills short, trigger-focused, and testable.
