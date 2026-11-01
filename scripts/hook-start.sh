#!/bin/bash
# Session start: set up in the background if needed, then give Claude its context.
# Prints nothing on the screen: this text only reaches Claude.
[ "$(uname)" = "Darwin" ] || exit 0
ICI="$(cd "$(dirname "$0")" && pwd)"
ENTREE="$(cat)"
RACINE="$HOME/.rasora"
V="$(cat "$ICI"/* 2>/dev/null | cksum | cut -d' ' -f1)"
if [ "$(cat "$RACINE/.version" 2>/dev/null)" != "$V" ]; then
  nohup bash "$ICI/bootstrap.sh" >/dev/null 2>&1 </dev/null &
  disown
fi
CWD="$(printf '%s' "$ENTREE" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("cwd",""))' 2>/dev/null)"
python3 "$ICI/contexte.py" "${CWD:-$PWD}" 2>/dev/null
exit 0
