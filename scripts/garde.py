#!/usr/bin/env python3
"""PreToolUse guard. It runs outside the model, so text on a page can't talk it out of it.

  ask   a human confirms: payments, publishing, deleting, messages, changing what is allowed
  deny  never: reading cookies or the Chrome key, reaching local addresses

Anything else passes silently. A broken guard must not break the user's other work, so
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
SECRETS = re.compile(r"\.rasora/(\.chrome-key|chrome-profile|bin/sessions\.json)|Chrome Safe Storage")
BACKDOOR = re.compile(r"cookies-vers-bot|127\.0\.0\.1:9\d{3}|localhost:9\d{3}")
REGLAGES = ("allow", "deny", "setup", "wipe", "do", "resume")


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
        if RISQUE.search(code) or re.search(r"\.submit\(|fetch\(|XMLHttpRequest|sendBeacon", code):
            return "ask", "Run this script in a signed-in page?"
    return None


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
        if sous in ("nav.py", "js") and a:
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
        if r:
            return r
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
