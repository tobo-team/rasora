#!/bin/bash
# Installs Rasora without the Claude Code plugin, for MCP clients.
# With Claude Code, use the plugin instead: see the README.
#
#   curl -fsSL https://raw.githubusercontent.com/vocalyagent/rasora/main/install.sh -o install.sh
#   less install.sh
#   bash install.sh
#
#   RASORA_SITES=github,gmail    allow these sites without asking (all = everywhere)
#   RASORA_NO_LAUNCHD=1          do not install the background guardians
set -uo pipefail

DEPOT="${RASORA_REPO:-https://github.com/vocalyagent/rasora}"
BRANCHE="${RASORA_BRANCH:-main}"
DEST="$HOME/.rasora/bin"
stop() { echo "stop: $*" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || stop "macOS only for now."
[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] || stop "Google Chrome not found."
command -v python3 >/dev/null || stop "python3 is missing. Run: xcode-select --install"

ICI="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$ICI" ] && [ -f "$ICI/scripts/nav.py" ]; then
  SOURCE="$ICI"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fsSL "${DEPOT}/archive/refs/heads/${BRANCHE}.tar.gz" | tar xz -C "$TMP" 2>/dev/null || stop "download failed"
  SOURCE="$(find "$TMP" -maxdepth 1 -type d -name 'rasora-*' | head -1)"
  [ -f "$SOURCE/scripts/nav.py" ] || stop "incomplete archive"
fi

bash "$SOURCE/scripts/bootstrap.sh" || stop "setup failed"
[ -d "$HOME/.local/bin" ] && ln -sf "$DEST/rasora" "$HOME/.local/bin/rasora"
echo "ok: installed in ~/.rasora"
echo

"$DEST/navigateur-bot.sh" >/dev/null 2>&1 || stop "the browser did not start"
PY="$DEST/.venv-cdp/bin/python"
if [ -n "${RASORA_SITES:-}" ]; then
  S="${RASORA_SITES//,/ }"; [ "$S" = "all" ] && S="--all"
  # shellcheck disable=SC2086
  "$PY" "$DEST/configurer-sessions.py" allow $S
else
  "$PY" "$DEST/configurer-sessions.py" ask
fi
if [ -s "$DEST/sessions.json" ] && [ "$(cat "$DEST/sessions.json")" != "{}" ]; then
  echo "Copying sessions. macOS will ask for Keychain access once: click Always Allow."
  "$PY" "$DEST/sessions.py" reparer 2>&1 | sed 's/^/  /'
fi

cat <<FIN

Done. Add it to your MCP client:  command $DEST/rasora, args ["mcp"]
Remove it all:                    $DEST/rasora wipe

FIN
