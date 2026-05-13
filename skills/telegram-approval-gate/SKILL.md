---
name: telegram-approval-gate
description: Use when Hermes is about to send, publish, forward, reply, post, email, DM, or otherwise deliver text/media to another person, group, channel, or external service and the operator expects Telegram confirmation buttons.
---

# Telegram Approval Gate

Before Hermes sends external communication, route the final draft through the operator's Telegram approval gate.

## Rule

Never send user-facing or public content directly when this skill applies. First send a Telegram approval card with:

- `Senden` - send the draft exactly as approved.
- `Bearbeiten` - ask the operator for edits, revise the draft, then submit a new approval card.
- `Abbrechen` - stop without sending.

This applies to Telegram, WhatsApp, Signal, email, social posts, channels, group messages, support replies, public comments, and any automation that sends on the operator's behalf.

## Helper

Use the bundled helper when a real Telegram approval round is needed:

```bash
python3 ~/.hermes/skills/messaging/telegram-approval-gate/scripts/telegram_approval_gate.py \
  --title "Freigabe" \
  --draft-file /path/to/draft.txt
```

Required environment:

- `HERMES_APPROVAL_BOT_TOKEN` - a dedicated approval bot token.
- `HERMES_APPROVAL_CHAT_ID` - the operator's approval DM/chat id.

Do not reuse the live Hermes/OpenClaw Telegram bot token while another gateway is polling it. A dedicated approval bot avoids `getUpdates` conflicts.

For dry runs:

```bash
python3 ~/.hermes/skills/messaging/telegram-approval-gate/scripts/telegram_approval_gate.py \
  --dry-run \
  --draft "Hallo"
```

## Workflow

1. Draft the exact outgoing message locally.
2. Run the approval helper or use the active messaging gateway's native inline-button approval mechanism.
3. If the decision is `send`, deliver exactly the approved content.
4. If the decision is `edit`, ask the operator for changes, revise, and repeat approval.
5. If the decision is `cancel` or timeout, do not send.
6. Record the approval result in the task summary.

## Testing

Run the local end-to-end fake Telegram test before relying on changes:

```bash
python3 ~/.hermes/skills/messaging/telegram-approval-gate/tests/test_telegram_approval_gate.py
```

Optional live smoke test requires `HERMES_APPROVAL_BOT_TOKEN` and `HERMES_APPROVAL_CHAT_ID`; do not run it with the same token currently owned by OpenClaw/Hermes gateway polling.
