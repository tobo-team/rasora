#!/bin/bash
# Navigateur DEDIE AUX BOTS. Totalement separe du Chrome personnel.
#
# Pourquoi il existe (08/08/2026). L'ancien montage partageait le Chrome de
# l utilisateur : le tracker le fermait et le relancait en boucle, et ses 14 comptes
# disparaissaient. La cause profonde n'etait pas un bug, c'etait le partage.
# Deux programmes ne peuvent pas se disputer une meme instance de Chrome.
#
# Garanties, dans l'ordre d'importance :
#   1. Ne touche JAMAIS au Chrome personnel. Aucun pkill global, aucun
#      osascript quit. Il ne connait que les processus dont la ligne de
#      commande contient SON user-data-dir.
#   2. Profil a lui : ~/.bot-navigateur. Jamais un lien vers ses profils.
#   3. Port 9333, pas 9222, pour ne rien croiser.
#   4. Pas de --enable-automation : navigator.webdriver reste false, donc
#      Cloudflare (gmgn, axiom) ne voit pas d'automatisation. C'est ce qui
#      distingue ce montage du Chromium de gstack, bloque par construction.
#
# Usage :
#   navigateur-bot.sh                lance ou verifie
#   navigateur-bot.sh <url>          lance puis ouvre l'url dans un onglet
#   navigateur-bot.sh --etat         dit si le pont repond
#   navigateur-bot.sh --arret        arrete UNIQUEMENT ce navigateur

set -uo pipefail
PORT=9333
DOSSIER="$HOME/.bot-navigateur"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MARQUE="user-data-dir=$DOSSIER"

vivant() { curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; }
mes_pids() { pgrep -f "$MARQUE" 2>/dev/null; }

case "${1:-}" in
  --etat)
    if vivant; then
      v=$(curl -s "http://127.0.0.1:$PORT/json/version" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("Browser",""))' 2>/dev/null)
      echo "pret sur $PORT  ($v)"; exit 0
    fi
    echo "eteint"; exit 1 ;;
  --arret)
    # on ne tue que nos propres processus, jamais "Google Chrome" en general
    pids=$(mes_pids)
    if [ -n "$pids" ]; then echo "$pids" | xargs kill 2>/dev/null; echo "navigateur bot arrete"; fi
    exit 0 ;;
esac

[ -x "$CHROME" ] || { echo "Chrome introuvable" >&2; exit 1; }

if ! vivant; then
  # nettoyage d'un reliquat a nous qui ne repondrait plus
  pids=$(mes_pids); [ -n "$pids" ] && { echo "$pids" | xargs kill 2>/dev/null; sleep 1; }

  mkdir -p "$DOSSIER"
  "$CHROME" \
    --remote-debugging-port="$PORT" \
    --remote-debugging-address=127.0.0.1 \
    --remote-allow-origins="http://127.0.0.1:$PORT" \
    --user-data-dir="$DOSSIER" \
    --no-first-run --no-default-browser-check \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-background-timer-throttling \
    --window-size=1200,900 --window-position=-2400,0 \
    "about:blank" >/dev/null 2>&1 &
  disown

  for _ in $(seq 1 30); do vivant && break; sleep 1; done
  vivant || { echo "le navigateur bot n'a pas repondu apres 30 s" >&2; exit 1; }

  # Il travaille MASQUE. Il ne doit jamais surgir par-dessus l'ecran de l'utilisateur :
  # la position hors ecran evite le surgissement au demarrage, la minimisation
  # finit le travail. Clics, lecture et captures continuent de fonctionner
  # fenetre minimisee (verifie le 16/08/2026). `nav.py montrer` la ramene quand
  # un login demande ses mains. `--visible` saute cette etape.
  if [ "${1:-}" != "--visible" ]; then
    # `discret` masque l'application ET repousse ses fenetres. Le masquage est ce
    # qui compte : macOS ne donne pas le premier plan a une app masquee.
    "$HOME/.claude/scripts/.venv-cdp/bin/python" "$HOME/.claude/scripts/nav.py" discret >/dev/null 2>&1
    "$HOME/.claude/scripts/masquer.py" >/dev/null 2>&1
  fi
  echo "navigateur bot demarre sur $PORT (masque)"
fi

# `--visible` n'est pas une url a ouvrir
[ "${1:-}" = "--visible" ] && set --

# Ouverture d'un onglet, si une url est demandee. On passe par nav.py, qui cree la
# cible EN ARRIERE-PLAN : l'appel HTTP /json/new, lui, restaure et ramene la fenetre
# devant l'ecran de l'utilisateur a chaque ouverture.
if [ -n "${1:-}" ]; then
  "$HOME/.claude/scripts/.venv-cdp/bin/python" "$HOME/.claude/scripts/nav.py" ouvrir "$1" 20 \
    || curl -s --max-time 10 -X PUT "http://127.0.0.1:$PORT/json/new?$1" >/dev/null 2>&1
fi

# Verification positive : on compte les instances principales, en distinguant
# la notre (elle porte notre user-data-dir) de celle personnel.
#
# Piege de mesure paye le 08/08/2026 : `grep "MacOS/Google Chrome "` avec une
# espace finale ne matche PAS l'instance personnelle, dont la ligne de commande
# s'arrete au binaire, sans argument. On croit alors que le Chrome personnel a
# disparu alors qu'il tourne. Toujours grepper "Contents/MacOS/Google Chrome"
# sans espace finale, et exclure "Helper".
perso=0
while read -r p rest; do
  echo "$rest" | grep -q "bot-navigateur" || perso=$((perso+1))
done < <(ps -Ao pid,args | grep "Contents/MacOS/Google Chrome" | grep -v Helper | grep -v grep)

if [ "$perso" -gt 0 ]; then
  echo "verifie : le Chrome personnel tourne toujours ($perso instance)"
else
  echo "note : aucun Chrome personnel ouvert en ce moment (ce script ne l'a pas ferme)"
fi
exit 0
