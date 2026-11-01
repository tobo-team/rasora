#!/bin/bash
# Installs neverlogout. Everything lives in ~/.neverlogout, your own Chrome is not touched.
#
#   curl -fsSL https://raw.githubusercontent.com/vocalyagent/neverlogout/main/install.sh -o install.sh
#   less install.sh
#   bash install.sh
#
# Nothing is allowed unless you say yes.
#   NEVERLOGOUT_SITES=github,gmail    allow these sites without asking (all = everywhere)
#   NEVERLOGOUT_NO_LAUNCHD=1          do not install the background guardians

set -uo pipefail

DEPOT="${NEVERLOGOUT_REPO:-https://github.com/vocalyagent/neverlogout}"
BRANCHE="${NEVERLOGOUT_BRANCH:-main}"
RACINE="$HOME/.neverlogout"
DEST="$RACINE/bin"
ETAT="$RACINE/state"
VENV="$DEST/.venv-cdp"
PORT="${CDP_PORT:-9333}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

V=$'\033[32m'; R=$'\033[31m'; J=$'\033[33m'; N=$'\033[0m'
ok()   { echo "${V}ok${N}   $*"; }
info() { echo "     $*"; }
stop() { echo "${R}stop${N} $*" >&2; exit 1; }
note() { echo "${J}note${N} $*"; }

echo
echo "  neverlogout: install"
echo "  ----------------------------------------------"

# 1. Requirements ---------------------------------------------------------------
[ "$(uname)" = "Darwin" ] || stop "macOS only for now (launchd, Keychain, Chrome)."
[ -x "$CHROME" ] || stop "Google Chrome not found. Install it, sign in to your accounts, then run this again."
command -v python3 >/dev/null || stop "python3 is missing. Run: xcode-select --install"
[ -d "$HOME/Library/Application Support/Google/Chrome" ] || stop "Chrome has never been opened here. Open it once, sign in, then run this again."
if curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 \
  && ! pgrep -f "user-data-dir=$RACINE/chrome-profile" >/dev/null 2>&1; then
  stop "port $PORT is already used by something else. Close it, or set CDP_PORT."
fi
ok "macOS, Chrome and python3 found"

# 2. Files ----------------------------------------------------------------------
SOURCE=""
ICI="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$ICI" ] && [ -f "$ICI/scripts/nav.py" ]; then
  SOURCE="$ICI"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  URL="${DEPOT}/archive/refs/heads/${BRANCHE}.tar.gz"
  curl -fsSL "$URL" | tar xz -C "$TMP" 2>/dev/null || stop "could not download $URL"
  SOURCE="$(find "$TMP" -maxdepth 1 -type d -name 'neverlogout-*' | head -1)"
  [ -f "$SOURCE/scripts/nav.py" ] || stop "incomplete archive"
fi

umask 077
mkdir -p "$DEST" "$ETAT" "$RACINE/sessions"
chmod 700 "$RACINE"
cp "$SOURCE"/scripts/* "$DEST"/
chmod +x "$DEST"/*.py "$DEST"/*.sh "$DEST/neverlogout" 2>/dev/null
ok "files installed in $RACINE"

# 3. Python ---------------------------------------------------------------------
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV" >/dev/null 2>&1 || stop "could not create the python environment"
"$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1
"$VENV/bin/pip" install -q websocket-client cryptography pillow beautifulsoup4 >/dev/null 2>&1 \
  || stop "could not install python dependencies (network?)"
ok "python environment ready"

# 4. The command ----------------------------------------------------------------
if [ -d "$HOME/.local/bin" ]; then
  ln -sf "$DEST/neverlogout" "$HOME/.local/bin/neverlogout"
fi

# 5. Claude Code skill, only if Claude Code is here -----------------------------
if [ -d "$HOME/.claude" ]; then
  mkdir -p "$HOME/.claude/skills/neverlogout"
  cp "$SOURCE/skills/neverlogout/SKILL.md" "$HOME/.claude/skills/neverlogout/SKILL.md"
  ok "Claude Code skill installed"
fi

# 6. The browser ----------------------------------------------------------------
"$DEST/navigateur-bot.sh" >/dev/null 2>&1
"$DEST/navigateur-bot.sh" --etat >/dev/null 2>&1 || stop "the browser did not start. Run: $DEST/navigateur-bot.sh"
ok "separate Chrome running on port $PORT, hidden"

# 7. Your choice of sites -------------------------------------------------------
echo
if [ -n "${NEVERLOGOUT_SITES:-}" ]; then
  S="${NEVERLOGOUT_SITES//,/ }"; [ "$S" = "all" ] && S="--all"
  # shellcheck disable=SC2086
  "$VENV/bin/python" "$DEST/configurer-sessions.py" allow $S
else
  "$VENV/bin/python" "$DEST/configurer-sessions.py" ask
fi
echo
if [ -s "$DEST/sessions.json" ] && [ "$(cat "$DEST/sessions.json")" != "{}" ]; then
  info "Copying sessions. macOS will ask for Keychain access: that is Chrome's cookie key."
  info "Only the sites you allowed are read, and nothing leaves your Mac."
  "$VENV/bin/python" "$DEST/sessions.py" reparer 2>&1 | sed 's/^/     /'
else
  note "no site allowed yet. Later: neverlogout allow <site>"
fi

# 8. Guardians ------------------------------------------------------------------
if [ "${NEVERLOGOUT_NO_LAUNCHD:-0}" = "1" ]; then
  note "background guardians not installed"
else
  AGENTS="$HOME/Library/LaunchAgents"
  mkdir -p "$AGENTS"
  plist() { # name, python, script, interval or "boucle", [argument]
    local nom="$1" py="$2" script="$3" mode="$4" arg="${5:-}"
    local f="$AGENTS/$nom.plist"
    launchctl unload "$f" >/dev/null 2>&1
    {
      echo '<?xml version="1.0" encoding="UTF-8"?>'
      echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
      echo '<plist version="1.0"><dict>'
      echo "  <key>Label</key><string>$nom</string>"
      echo '  <key>ProgramArguments</key><array>'
      echo "    <string>$py</string><string>$script</string>"
      [ -n "$arg" ] && echo "    <string>$arg</string>"
      echo '  </array>'
      if [ "$mode" = "boucle" ]; then
        echo '  <key>KeepAlive</key><true/>'
      else
        echo "  <key>StartInterval</key><integer>$mode</integer>"
      fi
      echo '  <key>RunAtLoad</key><true/>'
      echo "  <key>StandardOutPath</key><string>$ETAT/$nom.log</string>"
      echo "  <key>StandardErrorPath</key><string>$ETAT/$nom.log</string>"
      echo '</dict></plist>'
    } > "$f"
    launchctl load "$f" >/dev/null 2>&1
  }
  plist com.neverlogout.sessions "$VENV/bin/python" "$DEST/sessions.py"  1200 reparer
  plist com.neverlogout.nav-gc   /usr/bin/python3    "$DEST/nav-gc.py"    300
  plist com.neverlogout.nav-fond "$VENV/bin/python"  "$DEST/nav-fond.py"  boucle
  # focus-fond needs PyObjC, which only the system python ships.
  plist com.neverlogout.focus-fond /usr/bin/python3    "$DEST/focus-fond.py" boucle
  ok "guardians running: sessions checked every 20 min, old tabs closed, window kept hidden"
fi

cat <<FIN

  ----------------------------------------------
  Done.

  Check it:        $DEST/neverlogout sessions
  Allow a site:    $DEST/neverlogout allow github
  Give it a task:  $DEST/neverlogout do "open my GitHub notifications and summarize them"
  Other agents:    $DEST/neverlogout mcp
  Remove it all:   $DEST/neverlogout wipe

FIN
