#!/bin/bash
# Installe le navigateur bot : un Chrome pilotable par Claude Code, deja connecte
# a tes comptes, qui travaille hors de ton ecran.
#
#   curl -fsSL https://raw.githubusercontent.com/vocalyagent/nav-bot/main/install.sh | bash
#
# Ne demande rien, ne touche pas a ton Chrome, ne fait sortir aucune donnee.
# Tout ce qui existait deja sous le meme nom est sauvegarde en .avant-navbot.

set -uo pipefail

DEPOT="${NAVBOT_DEPOT:-https://github.com/vocalyagent/nav-bot}"
BRANCHE="${NAVBOT_BRANCHE:-main}"
DEST="${NAVBOT_DEST:-$HOME/.claude/scripts}"
SKILLS="${NAVBOT_SKILLS:-$HOME/.claude/skills}"
ETAT="$HOME/.claude/etat"
VENV="$DEST/.venv-cdp"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

V=$'\033[32m'; R=$'\033[31m'; J=$'\033[33m'; N=$'\033[0m'
ok()   { echo "${V}ok${N}   $*"; }
info() { echo "     $*"; }
stop() { echo "${R}stop${N} $*" >&2; exit 1; }
avert(){ echo "${J}note${N} $*"; }

echo
echo "  navigateur bot - installation"
echo "  ----------------------------------------------"

# 1. Le terrain -----------------------------------------------------------------
[ "$(uname)" = "Darwin" ] || stop "ce systeme ne marche que sur Mac (launchd, Trousseau, Chrome)."
[ -x "$CHROME" ] || stop "Google Chrome est introuvable. Installe-le, connecte-toi a tes comptes, puis relance."
command -v python3 >/dev/null || stop "python3 manquant. Ouvre le Terminal et tape : xcode-select --install"
[ -d "$HOME/Library/Application Support/Google/Chrome" ] || stop "Chrome n'a jamais ete lance sur ce Mac. Ouvre-le une fois, connecte-toi, puis relance."
ok "Mac, Chrome et python3 sont la"

# 2. Les fichiers ---------------------------------------------------------------
# Lance depuis un dossier du depot, on copie ; lance par curl, on telecharge.
SOURCE=""
ICI="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$ICI" ] && [ -f "$ICI/scripts/nav.py" ]; then
  SOURCE="$ICI"
  info "fichiers pris dans $ICI"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  URL="${DEPOT}/archive/refs/heads/${BRANCHE}.tar.gz"
  curl -fsSL "$URL" | tar xz -C "$TMP" 2>/dev/null || stop "telechargement impossible depuis $URL"
  SOURCE="$(find "$TMP" -maxdepth 1 -type d -name 'nav-bot-*' | head -1)"
  [ -f "$SOURCE/scripts/nav.py" ] || stop "archive incomplete"
  info "fichiers telecharges"
fi

mkdir -p "$DEST" "$SKILLS" "$ETAT" "$HOME/.claude/sessions"
DATE="$(date +%Y%m%d-%H%M)"
for f in "$SOURCE"/scripts/*; do
  base="$(basename "$f")"
  cible="$DEST/$base"
  if [ -f "$cible" ] && ! cmp -s "$f" "$cible"; then
    cp "$cible" "$cible.avant-navbot-$DATE"
    avert "$base existait deja, sauvegarde en $base.avant-navbot-$DATE"
  fi
  cp "$f" "$cible"
done
chmod +x "$DEST"/*.py "$DEST"/*.sh 2>/dev/null
ok "scripts installes dans $DEST"

# 3. Python ---------------------------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" >/dev/null 2>&1 || stop "creation de l'environnement python impossible"
fi
"$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1
"$VENV/bin/pip" install -q websocket-client cryptography pillow beautifulsoup4 >/dev/null 2>&1 \
  || stop "installation des dependances python impossible (reseau ?)"
ok "environnement python pret"

# 4. La skill que Claude lira ---------------------------------------------------
if [ -d "$SKILLS/naviguer" ] && ! cmp -s "$SOURCE/skills/naviguer/SKILL.md" "$SKILLS/naviguer/SKILL.md"; then
  mv "$SKILLS/naviguer" "$SKILLS/naviguer.avant-navbot-$DATE"
  avert "une skill 'naviguer' existait, sauvegardee en naviguer.avant-navbot-$DATE"
fi
mkdir -p "$SKILLS/naviguer"
cp "$SOURCE/skills/naviguer/SKILL.md" "$SKILLS/naviguer/SKILL.md"
ok "skill 'naviguer' installee (Claude Code la lira tout seul)"

# 5. Le navigateur --------------------------------------------------------------
"$DEST/navigateur-bot.sh" >/dev/null 2>&1
if "$DEST/navigateur-bot.sh" --etat >/dev/null 2>&1; then
  ok "navigateur bot demarre sur le port 9333, hors de ton ecran"
else
  stop "le navigateur bot n'a pas demarre. Relance : $DEST/navigateur-bot.sh"
fi

# 6. Tes sessions, trouvees toutes seules ---------------------------------------
echo
info "lecture de tes profils Chrome..."
"$VENV/bin/python" "$DEST/configurer-sessions.py" || stop "configuration des sessions impossible"
echo
info "greffe des sessions dans le navigateur bot (ton Trousseau va demander l'acces,"
info "c'est Chrome qui protege tes cookies : accepte, rien ne quitte le Mac)"
"$VENV/bin/python" "$DEST/sessions.py" reparer 2>&1 | sed 's/^/     /'

# 7. Les gardiens ---------------------------------------------------------------
if [ "${NAVBOT_SANS_LAUNCHD:-0}" = "1" ]; then
  avert "gardiens non installes (NAVBOT_SANS_LAUNCHD=1)"
else
  AGENTS="$HOME/Library/LaunchAgents"
  mkdir -p "$AGENTS"
  plist() { # nom, arg-python, [intervalle | boucle]
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
  plist com.navbot.sessions "$VENV/bin/python" "$DEST/sessions.py"  1200 reparer
  plist com.navbot.nav-gc   /usr/bin/python3    "$DEST/nav-gc.py"    300
  plist com.navbot.nav-fond "$VENV/bin/python"  "$DEST/nav-fond.py"  boucle
  # focus-fond a besoin de PyObjC, que seul le python du systeme embarque.
  plist com.navbot.focus-fond /usr/bin/python3    "$DEST/focus-fond.py" boucle
  ok "gardiens en place : sessions rafraichies toutes les 20 min, onglets"
  ok "nettoyes toutes les 5 min, fenetre tenue hors de ton ecran en permanence,"
  ok "focus rendu a ton app si le navigateur bot passe devant"
fi

# 8. Verdict --------------------------------------------------------------------
echo
echo "  ----------------------------------------------"
# `elaguer` teste tout et retire de la table ce qui n'est connecte nulle part :
# la liste finale ne montre que des sessions qui marchent vraiment.
"$VENV/bin/python" "$DEST/sessions.py" elaguer 2>&1 | sed 's/^/  /'
echo "  ----------------------------------------------"
cat <<'FIN'

  C'est installe. Ouvre Claude Code et demande-lui par exemple :

      "ouvre mon Gmail dans le navigateur bot et dis-moi les 3 derniers mails"
      "va sur ma boutique Shopify et regarde les commandes du jour"

  Il connait deja la marche a suivre, la skill 'naviguer' lui explique tout.

  A la main, si tu veux voir :
      ~/.claude/scripts/navigateur-bot.sh --etat
      ~/.claude/scripts/.venv-cdp/bin/python ~/.claude/scripts/nav.py ouvrir https://gmail.com
      ~/.claude/scripts/.venv-cdp/bin/python ~/.claude/scripts/nav.py lire gmail

  Une session marquee MORTE : connecte-toi UNE fois a ce site dans ton Chrome
  habituel, la greffe repart toute seule dans les 20 minutes.

FIN
