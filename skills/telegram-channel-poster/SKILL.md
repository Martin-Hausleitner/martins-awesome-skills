---
name: telegram-channel-poster
description: Use when the user asks to publish, post, announce, syndicate, or automatically send content to a Telegram channel using a native Telegram bot rather than Beeper chat lookup.
---

# Telegram Channel Poster

Use this skill for outbound Telegram channel publishing through the native Telegram Bot API.

## Safety

- Posting is external communication. If the user did not explicitly ask to publish in this turn, prepare a dry run and ask before sending.
- Never write bot tokens, channel secrets, or invite links into the skill. Load them from a private env file, Keychain, or OpenClaw secrets.
- The bot must be an administrator in the target channel. Use `@channelusername` or the Bot API channel id.
- Keep Beeper separate: `telegram-chats` is for reading chats; this skill is for native bot/channel publishing.

## Helper

```bash
./scripts/telegram_channel_post.sh --dry-run --text "Hello"
./scripts/telegram_channel_post.sh --text "Hello"
./scripts/telegram_channel_post.sh --file /path/to/message.md --parse-mode MarkdownV2
```

Required env file shape:

```bash
TELEGRAM_BOT_TOKEN="123456:token-from-botfather"
TELEGRAM_CHANNEL_ID="@channelusername"
```

Optional Notion logging uses the `notion-openclaw-log` skill:

```bash
TELEGRAM_NOTION_LOG="true"
NOTION_PARENT_PAGE_ID="page-id-shared-with-integration"
```

## Workflow

1. Confirm the user requested an external Telegram post.
2. Draft the exact message locally.
3. Run the helper with `--dry-run` and inspect the redacted payload.
4. For first-time setup, ask the user for the BotFather token and channel id, then store them outside the skill.
5. If the user wants an audit trail, enable `TELEGRAM_NOTION_LOG=true` and dry-run the Notion payload.
6. Send with the helper only after the publish intent is explicit.
7. Verify the Telegram API response has `"ok": true`; if not, report the API error without exposing the token.

## References

- Telegram Bot API `sendMessage`: https://core.telegram.org/bots/api#sendmessage
- Telegram Bot API dialog ids: https://core.telegram.org/api/bots/ids
- Optional local Notion log skill, configured via `NOTION_HELPER`.

## Tests

```bash
python3 scripts/test_telegram_channel_post.py
```
