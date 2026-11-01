#!/bin/bash
# Sets up ~/.rasora. Asks nothing and opens nothing. Safe to run again.
set -uo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
RACINE="$HOME/.rasora"; DEST="$RACINE/bin"; ETAT="$RACINE/state"; VENV="$DEST/.venv-cdp"
[ "$(uname)" = "Darwin" ] || exit 1

umask 077
mkdir -p "$RACINE"
chmod 700 "$RACINE"
mkdir "$RACINE/.boot" 2>/dev/null || {                       # another setup is running
  for _ in $(seq 1 90); do [ -d "$RACINE/.boot" ] || exit 0; sleep 1; done
  rmdir "$RACINE/.boot" 2>/dev/null; exit 1
}
trap 'rmdir "$RACINE/.boot" 2>/dev/null' EXIT
mkdir -p "$DEST" "$ETAT" "$RACINE/sessions" "$RACINE/memory"

# A port of our own. Never share one: another tool may already drive a Chrome on 9333.
if [ ! -s "$RACINE/port" ]; then
  P="${CDP_PORT:-9333}"
  while [ "$P" -lt 9400 ] && curl -s --max-time 1 "http://127.0.0.1:$P/json/version" >/dev/null 2>&1; do
    P=$((P + 1))
  done
  echo "$P" > "$RACINE/port"
fi
export CDP_PORT="$(cat "$RACINE/port")"

empreinte() { find "$1" -maxdepth 1 -type f ! -name sessions.json -print0 | sort -z | xargs -0 cat | cksum | cut -d' ' -f1; }
[ "$ICI" = "$DEST" ] || find "$ICI" -maxdepth 1 -type f -exec cp {} "$DEST"/ \;
chmod +x "$DEST"/*.py "$DEST"/*.sh "$DEST/rasora" 2>/dev/null

[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV" >/dev/null 2>&1 || exit 1
# Exact versions and hashes: a poisoned release can't slip in through an update.
"$VENV/bin/pip" install -q --require-hashes --only-binary=:all: -r "$ICI/requirements.lock" >/dev/null 2>&1 || exit 1

if [ "${RASORA_NO_LAUNCHD:-0}" != "1" ]; then
  AGENTS="$HOME/Library/LaunchAgents"
  mkdir -p "$AGENTS"
  plist() { # name, python, script, interval or "boucle", [argument]
    local nom="$1" py="$2" script="$3" mode="$4" arg="${5:-}" f="$AGENTS/$1.plist"
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
      if [ "$mode" = "boucle" ]; then echo '  <key>KeepAlive</key><true/>'
      else echo "  <key>StartInterval</key><integer>$mode</integer>"; fi
      echo "  <key>EnvironmentVariables</key><dict><key>CDP_PORT</key><string>$CDP_PORT</string></dict>"
      echo '  <key>RunAtLoad</key><true/>'
      echo "  <key>StandardOutPath</key><string>$ETAT/$nom.log</string>"
      echo "  <key>StandardErrorPath</key><string>$ETAT/$nom.log</string>"
      echo '</dict></plist>'
    } > "$f"
    launchctl load "$f" >/dev/null 2>&1
  }
  plist com.rasora.nav-gc   /usr/bin/python3    "$DEST/nav-gc.py"    300
  # Once a day: a visit keeps sessions fresh, and tells Claude which ones ended.
  plist com.rasora.sessions /bin/bash           "$DEST/rasora"       86400 sessions
  plist com.rasora.nav-fond "$VENV/bin/python"  "$DEST/nav-fond.py"  boucle
  # focus-fond needs PyObjC, which only the system python ships.
  plist com.rasora.focus-fond /usr/bin/python3    "$DEST/focus-fond.py" boucle
fi

empreinte "$ICI" > "$RACINE/.version"
