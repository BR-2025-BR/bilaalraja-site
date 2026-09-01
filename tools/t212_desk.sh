#!/usr/bin/env bash
# Start the Trading 212 desk, optionally published to your phone via Tailscale.
#
#   ./tools/t212_desk.sh              read-only, this machine only
#   ./tools/t212_desk.sh --phone      read-only, reachable from your devices
#   ./tools/t212_desk.sh --trade      order placement enabled, this machine only
#
# --phone and --trade are deliberately awkward to combine: reading positions from
# the sofa is a different risk from being able to trade with a mis-tap. Pass
# --trade --phone if you really mean it and the script will say so out loud.
#
# Credentials come from the environment and are never written to disk:
#
#   export T212_ID='...'
#   export T212_SECRET='...'
#
# Put those two lines in ~/.zshrc if you would rather not retype them. That file
# is not in any repository; the key must never end up in one.

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-python3}"
PORT="${T212_PORT:-8212}"
PHONE=0; TRADE=0
for a in "$@"; do
  case "$a" in
    --phone) PHONE=1 ;;
    --trade) TRADE=1 ;;
    *) echo "unknown option: $a"; exit 2 ;;
  esac
done

if [[ -z "${T212_ID:-}" || -z "${T212_SECRET:-}" ]]; then
  echo "Set T212_ID and T212_SECRET first:"
  echo "  export T212_ID='...'; export T212_SECRET='...'"
  exit 1
fi

ARGS=()
[[ $TRADE -eq 1 ]] && ARGS+=(--allow-orders)

cleanup() {
  if [[ $PHONE -eq 1 ]] && command -v tailscale >/dev/null; then
    tailscale serve --https="$PORT" off 2>/dev/null || true
    echo "  tailscale share withdrawn"
  fi
}
trap cleanup EXIT

if [[ $PHONE -eq 1 ]]; then
  if ! command -v tailscale >/dev/null; then
    echo "Tailscale is not installed. Either:"
    echo "  brew install --cask tailscale     then sign in on the Mac and the phone"
    echo "or drop --phone to run on this machine only."
    exit 1
  fi
  if ! tailscale status >/dev/null 2>&1; then
    echo "Tailscale is installed but not signed in. Open the app and log in,"
    echo "then run this again."
    exit 1
  fi
fi

echo
[[ $TRADE -eq 1 ]] && echo "  ORDERS ENABLED — this session can place trades" \
                   || echo "  read-only — restart with --trade to place orders"
if [[ $PHONE -eq 1 && $TRADE -eq 1 ]]; then
  echo "  !! and it is reachable from your phone. A mis-tap is a real order. !!"
fi

"$PY" tools/t212_server.py "${ARGS[@]}" &
SRV=$!
sleep 2

if [[ $PHONE -eq 1 ]]; then
  # The server stays on 127.0.0.1. Tailscale terminates TLS and forwards to it,
  # so the dashboard is never exposed to the local network, only to devices
  # signed in to your tailnet.
  tailscale serve --bg --https="$PORT" "http://127.0.0.1:${PORT}" >/dev/null
  echo
  echo "  on your phone (signed in to the same Tailscale account):"
  tailscale serve status | grep -Eo 'https://[^ ]+' | head -1 | sed 's/^/    /'
  echo
fi

echo "  Ctrl-C to stop"
wait $SRV
