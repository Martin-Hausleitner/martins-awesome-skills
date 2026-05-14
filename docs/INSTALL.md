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

## Dedicated Telegram Approval Bot

Use a separate bot for approval polling:

```bash
cp config-templates/hermes-approval.env.example .env.telegram-approval
```

Fill the copied file privately. Never commit the real token or chat id.

Do not reuse a bot token that is already being polled by another gateway. Telegram allows only one active `getUpdates` poller per bot token.
