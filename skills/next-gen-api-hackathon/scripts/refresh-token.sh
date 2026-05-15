#!/usr/bin/env bash
# Refresh DEALROOM_ACCESS_TOKEN in .env after a 401 (or proactively, daily).
# Reads existing credentials from .env in the current directory.

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

red() { printf "\033[31m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }

if [[ ! -f "$ENV_FILE" ]]; then
  red "$ENV_FILE not found in $(pwd)."
  echo "Run scripts/setup.sh first."
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

for var in DEALROOM_AUTH_URL DEALROOM_AUDIENCE DEALROOM_CLIENT_ID DEALROOM_CLIENT_SECRET; do
  if [[ -z "${!var:-}" ]]; then
    red "$var is missing from $ENV_FILE."
    echo "Re-run scripts/setup.sh to recreate the file."
    exit 1
  fi
done

RESPONSE=$(curl -s -X POST "$DEALROOM_AUTH_URL" \
  -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$DEALROOM_CLIENT_ID\",\"client_secret\":\"$DEALROOM_CLIENT_SECRET\",\"audience\":\"$DEALROOM_AUDIENCE\",\"grant_type\":\"client_credentials\"}")

NEW_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token // empty')

if [[ -z "$NEW_TOKEN" ]]; then
  red "Token refresh failed:"
  echo "$RESPONSE" | jq .
  exit 1
fi

# Replace the DEALROOM_ACCESS_TOKEN line in place. Works on both GNU and BSD sed.
TMP="$(mktemp)"
awk -v tok="$NEW_TOKEN" '
  /^DEALROOM_ACCESS_TOKEN=/ { print "DEALROOM_ACCESS_TOKEN=\"" tok "\""; next }
  { print }
' "$ENV_FILE" > "$TMP"
mv "$TMP" "$ENV_FILE"
chmod 600 "$ENV_FILE"

green "Refreshed DEALROOM_ACCESS_TOKEN in $ENV_FILE."
echo "Re-source the file in your shell:  source $ENV_FILE"
