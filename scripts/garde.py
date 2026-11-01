#!/usr/bin/env python3
"""PreToolUse guard. It runs outside the model, so text on a page can't talk it out of it.

  allow Rasora's ordinary actions go through without a prompt
  ask   a human confirms: payments, publishing, deleting, messages, changing what is allowed
  deny  never: reading cookies or the Chrome key, reaching local addresses

Everything else is left to Claude Code's normal permissions. A broken guard must not break the user's other work, so
unexpected input lets the call through.
"""
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensibles import CHAMP, RISQUE, refus_url  # noqa: E402

VOLE = re.compile(r"document\.cookie|localStorage|sessionStorage|indexedDB|cookieStore", re.I)
SECRETS = re.compile(r"chrome-profile|\.rasora/(bin/sessions\.json|port)|Chrome Safe Storage|"
                     r"Google/Chrome/[^ ]*(Cookies|Login Data)|Default/Cookies|Login Data|"
                     r"find-(generic|internet)-password|dump-keychain")
# Only the ports Rasora's Chrome can use: anything else on 9xxx is the user's own work.
HOTES_LOCAUX = r"(127\.\d+\.\d+\.\d+|127\.1|localhost|0\.0\.0\.0|\[[0-9a-f:.]*\])"
BACKDOOR = re.compile(HOTES_LOCAUX + r":(93[3-9]\d|9400)\b", re.I)
INTOUCHABLE = re.compile(r"\.rasora/bin/|\.claude/plugins/(cache|marketplaces)/rasora/")
MODIFIE = re.compile(r">|\b(sed\s+-i|rm|mv|cp|tee|chmod|ln|install|truncate)\b")
REGLAGES_CLAUDE = re.compile(r"disableAllHooks|enabledPlugins")
DESACTIVE = re.compile(r"\bclaude\s+plugins?\s+(disable|uninstall|remove)\b")
REGLAGES = ("login", "logout", "wipe", "do", "resume")
SORTIE = re.compile(r"\.submit\(|fetch\(|XMLHttpRequest|sendBeacon|new Image|\.src\s*=|"
                    r"location(\.href)?\s*=|location\.(assign|replace)\(|window\.open|WebSocket|"
                    r"\.click\(|requestSubmit|dispatchEvent|\.value\s*=[^=]|\beval\(|\bFunction\(|"
                    r"\batob\(|\bimport\(|\[\s*[`'" + '"' + r"]")
# The word rasora, or the script behind it, wherever it stands in a command.
APPEL = re.compile(r"(?:^|[\s;&|/(`'\"=])rasora\s+")
# Only with Rasora in sight: users have tools of their own called nav.py.
APPEL_SCRIPT = re.compile(r"(?:^|[\s;&|/(`'\"=])(?:rasora|nav\.py)\s+")
RANG = {"allow": 0, "ask": 1, "deny": 2}
SEUL = re.compile(r"^\s*(~/\.rasora/bin/)?rasora\s+[^;&|`$<>\n]*$")
# Past these sizes the scan could outlast the hook's timeout, and a hook that times out lets
# the call through. So it asks instead.
LONGUEUR_MAX, APPELS_MAX = 64_000, 50
ACTIONS = ("click", "clic", "select", "menu", "fill", "champ", "open", "ouvrir", "js")
FICHIERS = ("Read", "Grep", "Glob", "Write", "Edit", "NotebookEdit")
ECRITURE = ("Write", "Edit", "NotebookEdit")


def decider(nom, e):
    """Rend (decision, raison) ou None."""
    outil = nom.rsplit("__", 1)[-1]
    if nom in FICHIERS:
        chemin = " ".join(str(e.get(k, "")) for k in ("file_path", "notebook_path", "path", "pattern"))
        if SECRETS.search(chemin):
            return "deny", "This file holds live sessions."
        if nom in ECRITURE:
            if INTOUCHABLE.search(chemin):
                return "deny", "Rasora's own files, including its guard, can't be changed from here."
            texte = str(e.get("content", "")) + str(e.get("new_string", ""))
            if "settings" in chemin and REGLAGES_CLAUDE.search(texte):
                return "ask", "Change which hooks or plugins Claude Code runs?"
        return None
    if nom == "Bash":
        return bash(e.get("command", ""))
    return action(outil, e)


def action(outil, e):
    if outil == "browser_open":
        raison = refus_url(e.get("url", ""))
        if raison:
            return "deny", raison
    elif outil == "session_login":
        return "ask", f"Open a window so the user signs in to {e.get('url', '')[:60]}?"
    elif outil == "browser_click" and RISQUE.search(e.get("text", "")):
        return "ask", f"Click \"{e.get('text', '')[:60]}\" with the user's account?"
    elif outil == "browser_select" and RISQUE.search(e.get("option", "")):
        return "ask", f"Select \"{e.get('option', '')[:60]}\"?"
    elif outil == "browser_fill" and CHAMP.search(e.get("label", "")):
        return "ask", f"Fill the sensitive field \"{e.get('label', '')[:60]}\"?"
    elif outil == "browser_js":
        code = e.get("code", "")
        if VOLE.search(code):
            return "deny", "Reading cookies or storage from a page is not allowed."
        if RISQUE.search(code) or SORTIE.search(code):
            return "ask", "Run this script in a signed-in page?"
    return "allow", "Ordinary Rasora action."


def port_reel(cmd):
    """The port in use, for a user who chose one outside the usual range."""
    try:
        with open(os.path.expanduser("~/.rasora/port"), encoding="utf-8") as f:
            port = f.read().strip()
    except OSError:
        return False
    return bool(port.isdigit() and re.search(HOTES_LOCAUX + ":" + port + r"\b", cmd, re.I))


def appels(cmd):
    """Every rasora call in a shell command, however it is chained or nested.

    A scan rather than a parse: `a; b`, `a && b`, `$(a)`, backticks and `bash -c "a"` all
    land here, because each occurrence of the word is read on its own.
    """
    for m in (APPEL_SCRIPT if "rasora" in cmd.lower() else APPEL).finditer(cmd):
        reste = cmd[m.end():]
        try:
            lex = shlex.shlex(reste, posix=True, punctuation_chars=";&|()<>`")
            lex.whitespace = " \t"
            lex.whitespace_split = True
            lex.commenters = ""
            mots = []
            for mot in lex:
                if mot == "\n" or set(mot) <= set(";&|()<>`"):
                    break
                mots.append(mot)
        except ValueError:               # a quote closes outside: `bash -c "rasora click Pay"`
            ligne = re.split(r"[;&|\n`)]", reste, maxsplit=1)[0]
            mots = [x.strip("\"'") for x in ligne.split()]
        if mots:
            yield mots[0], mots[1:]


def appel(sous, a):
    """The verdict for one call. Arguments are joined: their order must not hide a word."""
    if sous in REGLAGES:
        return "ask", f"Run `rasora {sous}`?"
    if sous == "js" and a:
        return action("browser_js", {"code": " ".join(a)})
    if sous in ("click", "clic") and a:
        return action("browser_click", {"text": " ".join(a)})
    if sous in ("select", "menu") and a:
        return action("browser_select", {"option": " ".join(a)})
    if sous in ("fill", "champ") and len(a) >= 2:
        return action("browser_fill", {"label": " ".join(a[:-1])})
    if sous in ("open", "ouvrir") and a:
        return action("browser_open", {"url": a[0]})
    return "allow", "Ordinary Rasora command."


def bash(cmd):
    if SECRETS.search(cmd) or BACKDOOR.search(cmd) or port_reel(cmd):
        return "deny", "Direct access to sessions or the browser port is not allowed."
    if INTOUCHABLE.search(cmd) and MODIFIE.search(cmd):
        return "deny", "Rasora's own files, including its guard, can't be changed from here."
    if DESACTIVE.search(cmd) and "rasora" in cmd:
        return "ask", "Turn Rasora and its guard off?"
    # Empty quotes and stray backslashes vanish when the shell runs the command.
    sans_masque = re.sub(r"\"\"|''|\\(?=\w)", "", cmd)
    if len(sans_masque) > LONGUEUR_MAX and "rasora" in sans_masque:
        return "ask", "This command is too long to check. Run it?"
    if len(APPEL.findall(sans_masque)) > APPELS_MAX:
        return "ask", "This command has too many rasora calls to check. Run it?"
    trouves = list(appels(cmd)) + (list(appels(sans_masque)) if sans_masque != cmd else [])
    if not trouves:
        return None
    verdicts = [appel(s, a) for s, a in trouves]
    # A value built by the shell can't be read here, so it can't be called harmless.
    if re.search(r"[$`]", cmd) and any(s in ACTIONS for s, _ in trouves):
        verdicts.append(("ask", "Run this command? Part of it is only known once it runs."))
    pire = max(verdicts, key=lambda v: RANG[v[0]])    # the strictest answer wins
    if pire[0] != "allow":
        return pire
    # Only a lone rasora command is auto-approved, never one chained to something else.
    return pire if SEUL.match(cmd) else None


def est_connexion(e):
    """Exempt only when the sign-in is all there is: never `rasora login x; rasora click Pay`."""
    cmd = (e.get("tool_input") or {}).get("command", "")
    if e.get("tool_name", "").endswith("__session_login"):
        return True
    if SEUL.match(cmd) is None:
        return False
    trouves = list(appels(cmd))
    return len(trouves) == 1 and trouves[0][0] == "login"


def main():
    try:
        e = json.load(sys.stdin)
    except Exception:
        return
    nom, entree = e.get("tool_name", ""), e.get("tool_input") or {}
    try:
        r = decider(nom, entree)
    except Exception:
        # A crafted value must not switch the guard off for the rest of the command.
        r = None
        if "rasora" in nom or "rasora" in str(entree):
            r = "ask", "The guard could not read this call. Run it?"
    if not r:
        return
    decision, raison = r
    # With permission checks switched off, "ask" may never reach a human: refuse instead,
    # and let Claude ask in the conversation.
    if decision == "ask" and e.get("permission_mode") == "bypassPermissions":
        # A sign-in window only shows a page to the user: it can't act on their behalf.
        if est_connexion(e):
            return
        decision, raison = "deny", raison + " Ask the user in the conversation first."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": raison}}))


if __name__ == "__main__":
    main()
