# OpenClaw / Hermes Public Skills

Public, sanitized skill examples for Hermes Agent and OpenClaw workflows.

## Included

- `skills/telegram-approval-gate` - human-in-the-loop Telegram approval cards with `Senden`, `Bearbeiten`, and `Abbrechen`.
- `skills/telegram-channel-poster` - native Telegram channel posting workflow with dry-run-first safety.
- `config-templates` - example environment templates only. No real tokens, chat ids, memories, or sessions.

## Safety Rules

- Do not commit `.env`, `auth.json`, `MEMORY.md`, `USER.md`, session exports, accounting data, private chat logs, or real Telegram chat ids.
- Use a dedicated approval bot token for approval polling. Do not reuse a bot token that is already owned by a running Hermes/OpenClaw gateway.
- Always run the local tests before publishing changes.

## Tests

```bash
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
python3 skills/telegram-channel-poster/scripts/test_telegram_channel_post.py
```
