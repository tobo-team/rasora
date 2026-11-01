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
from sensibles import adresse_privee  # noqa: E402

RISQUE = re.compile(
    r"\b(pay|payer|paiement|buy|acheter|achat|purchase|order|commander|checkout|subscribe|"
    r"s'abonner|transfer|virement|withdraw|publish|publier|post|tweet|send|envoyer|delete|"
    r"supprimer|remove|confirm|confirmer|valider|sign up and pay)\b", re.I)
CHAMP = re.compile(r"card|carte|cvv|cvc|iban|password|mot de passe|ssn|routing", re.I)
VOLE = re.compile(r"document\.cookie|localStorage|sessionStorage|indexedDB|cookieStore", re.I)
SECRETS = re.compile(r"\.rasora/(chrome-profile|bin/sessions\.json)|Chrome Safe Storage|"
                     r"Google/Chrome/[^ ]*Cookies")
BACKDOOR = re.compile(r"127\.0\.0\.1:9\d{3}|localhost:9\d{3}")
REGLAGES = ("login", "logout", "wipe", "do", "resume")
SORTIE = re.compile(r"\.submit\(|fetch\(|XMLHttpRequest|sendBeacon|new Image|\.src\s*=|"
                    r"location(\.href)?\s*=|window\.open|WebSocket")
SEUL = re.compile(r"^\s*(~/\.rasora/bin/)?rasora\s+[^;&|`$<>\n]*$")


def decider(nom, e):
    """Rend (decision, raison) ou None."""
    outil = nom.rsplit("__", 1)[-1]
    if nom == "Read":
        if SECRETS.search(e.get("file_path", "")):
            return "deny", "This file holds live sessions."
        return None
    if nom == "Bash":
        return bash(e.get("command", ""))
    return action(outil, e)


def action(outil, e):
    if outil == "browser_open":
        if adresse_privee(e.get("url", "")):
            return "deny", "Local addresses are refused."
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


def bash(cmd):
    if SECRETS.search(cmd) or BACKDOOR.search(cmd):
        return "deny", "Direct access to sessions or the browser port is not allowed."
    for m in re.finditer(r"(?:^|[\s;&|/])rasora\s+(.+)", cmd):
        try:
            mots = shlex.split(m.group(1), posix=True)
        except ValueError:
            mots = m.group(1).split()
        if not mots:
            continue
        sous, a = mots[0], mots[1:]
        if sous in REGLAGES:
            return "ask", f"Run `rasora {sous}`?"
        if sous == "js" and a:
            r = action("browser_js", {"code": a[-1]})
        elif sous in ("click", "clic") and a:
            r = action("browser_click", {"text": a[-1]})
        elif sous in ("select", "menu") and a:
            r = action("browser_select", {"option": a[-1]})
        elif sous in ("fill", "champ") and len(a) >= 2:
            r = action("browser_fill", {"label": a[-2]})
        elif sous in ("open", "ouvrir") and a:
            r = action("browser_open", {"url": a[0]})
        else:
            r = None
        if r and r[0] != "allow":
            return r
        # Only a lone rasora command is auto-approved, never one chained to something else.
        return ("allow", "Ordinary Rasora command.") if SEUL.match(cmd) else None
    return None


def main():
    try:
        e = json.load(sys.stdin)
        r = decider(e.get("tool_name", ""), e.get("tool_input") or {})
    except Exception:
        return
    if not r:
        return
    decision, raison = r
    # With permission checks switched off, "ask" may never reach a human: refuse instead,
    # and let Claude ask in the conversation.
    if decision == "ask" and e.get("permission_mode") == "bypassPermissions":
        decision, raison = "deny", raison + " Ask the user in the conversation first."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": raison}}))


if __name__ == "__main__":
    main()
