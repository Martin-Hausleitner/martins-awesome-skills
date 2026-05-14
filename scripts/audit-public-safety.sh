#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

patterns=(
  'gho_'
  'github_pat_'
  'sk-[A-Za-z0-9_-]{20,}'
  'xox[baprs]-'
  'AIza[0-9A-Za-z_-]'
  'ntn_'
  '-----BEGIN'
  '[0-9]{8,}:[A-Za-z0-9_-]{20,}'
  '/Users/mh'
  'Buchhaltung'
  'AKTE'
  'auth\.json'
  'client_secret'
)

status=0
for pattern in "${patterns[@]}"; do
  if rg -n --hidden -S -e "$pattern" "$ROOT" \
    -g '!.git/**' \
    -g '!.gitignore' \
    -g '!docs/SECURITY.md' \
    -g '!README.md' \
    -g '!scripts/audit-public-safety.sh'; then
    status=1
  fi
done

if [[ "$status" -ne 0 ]]; then
  echo "Public safety audit failed." >&2
  exit "$status"
fi

echo "Public safety audit passed."
