#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${TELEGRAM_ENV_FILE:-.env.telegram-channel}"
DRY_RUN=0
TEXT=""
TEXT_FILE=""
PARSE_MODE="${TELEGRAM_PARSE_MODE:-}"
DISABLE_NOTIFICATION="${TELEGRAM_DISABLE_NOTIFICATION:-false}"
PROTECT_CONTENT="${TELEGRAM_PROTECT_CONTENT:-false}"
NOTION_LOG="${TELEGRAM_NOTION_LOG:-false}"
NOTION_HELPER="${NOTION_HELPER:-}"

usage() {
  cat >&2 <<'USAGE'
usage: telegram_channel_post.sh [--dry-run] [--env FILE] (--text TEXT | --file PATH) [--parse-mode HTML|MarkdownV2]

Required environment:
  TELEGRAM_BOT_TOKEN   BotFather token. Keep it in an env file or secret store.
  TELEGRAM_CHANNEL_ID  Channel username (@name) or numeric chat id.

Optional:
  TELEGRAM_NOTION_LOG=true  Log a redacted delivery note through notion-openclaw-log.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --env)
      ENV_FILE="${2:?--env requires a file}"
      shift 2
      ;;
    --text)
      TEXT="${2:?--text requires content}"
      shift 2
      ;;
    --file)
      TEXT_FILE="${2:?--file requires a path}"
      shift 2
      ;;
    --parse-mode)
      PARSE_MODE="${2:?--parse-mode requires HTML or MarkdownV2}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 64
      ;;
  esac
done

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${TELEGRAM_CHANNEL_ID:?TELEGRAM_CHANNEL_ID is required}"

if [[ -n "$TEXT_FILE" ]]; then
  if [[ ! -f "$TEXT_FILE" ]]; then
    echo "text file not found: $TEXT_FILE" >&2
    exit 66
  fi
  TEXT="$(cat "$TEXT_FILE")"
fi

if [[ -z "$TEXT" ]]; then
  echo "message text is required; pass --text or --file" >&2
  exit 64
fi

export TELEGRAM_CHANNEL_ID TEXT PARSE_MODE DISABLE_NOTIFICATION PROTECT_CONTENT

payload_json="$(python3 - <<'PY'
import json
import os

payload = {
    "chat_id": os.environ["TELEGRAM_CHANNEL_ID"],
    "text": os.environ["TEXT"],
    "disable_notification": os.environ.get("DISABLE_NOTIFICATION", "false").lower() == "true",
    "protect_content": os.environ.get("PROTECT_CONTENT", "false").lower() == "true",
}
parse_mode = os.environ.get("PARSE_MODE", "")
if parse_mode:
    payload["parse_mode"] = parse_mode
print(json.dumps(payload, ensure_ascii=False))
PY
)"

export PAYLOAD_JSON="$payload_json"

if [[ "$DRY_RUN" -eq 1 ]]; then
  export NOTION_LOG
  python3 - <<'PY'
import json
import os

result = {
    "method": "sendMessage",
    "endpoint": "https://api.telegram.org/bot<redacted>/sendMessage",
    "payload": json.loads(os.environ["PAYLOAD_JSON"]),
}
if os.environ.get("NOTION_LOG", "").lower() in {"1", "true", "yes", "on"}:
    result["notion_log"] = {
        "status": "planned",
        "title": "Telegram channel post",
        "helper": os.environ.get("NOTION_HELPER", "<configured externally>"),
    }
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
  exit 0
fi

response="$(curl -fsS \
  -X POST \
  -H "Content-Type: application/json" \
  --data "$payload_json" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage")"

printf '%s\n' "$response"

if [[ "$NOTION_LOG" =~ ^(1|true|yes|on)$ ]] && [[ -x "$NOTION_HELPER" ]]; then
  export TELEGRAM_RESPONSE="$response"
  notion_text="$(python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["PAYLOAD_JSON"])
response = json.loads(os.environ.get("TELEGRAM_RESPONSE", "{}"))
print("\n".join([
    "Telegram channel post",
    f"chat_id: {payload.get('chat_id')}",
    f"text_preview: {payload.get('text', '')[:500]}",
    f"telegram_ok: {response.get('ok')}",
]))
PY
)"
  "$NOTION_HELPER" --title "Telegram channel post" --text "$notion_text" >/dev/null
fi
