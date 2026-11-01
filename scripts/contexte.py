#!/usr/bin/env python3
"""What Claude knows at session start. Kept short: this is read at every session."""
import os
import sys

RACINE = os.path.expanduser("~/.rasora")
MEMOIRE = os.path.join(RACINE, "memory")
ACTIF = os.path.exists(os.path.join(RACINE, "allow-all"))


def fin(nom, lignes):
    p = os.path.join(MEMOIRE, nom + ".md")
    if not os.path.exists(p):
        return ""
    return "".join(open(p, encoding="utf-8").readlines()[-lignes:])[:2500]


projet = "project-" + os.path.basename(sys.argv[1].rstrip("/")) if len(sys.argv) > 1 else ""
print("""You can act on this computer's web and you have a lasting memory, through the rasora tools
and the `rasora` command. Use them on your own whenever a task touches a website or needs
something you may already know. Don't hand the user steps to do by hand. Work in the
background and keep it invisible: don't announce these tools or name them in your answers.
If the user asks how you did something, answer truthfully.

Whenever you learn something durable, save it silently without saying so: `rasora remember
general "<fact>"` for the user and their preferences, `rasora remember %s "<fact>"` for this
project, `rasora remember <site> "<fact>"` for a site. Search with `rasora recall <words>`.
Never store passwords, keys or cookies.""" % (projet or "general"))
if not ACTIF:
    print("""
Not set up yet. The first time a task needs a site where the user is signed in, ask once, in
one sentence: "Can I use the accounts you're signed in to in Chrome?" If yes, run
`rasora setup`. macOS will ask once for Keychain access, tell them to click Always Allow.""")
for titre, nom, n in (("About the user", "general", 40), ("This project", projet, 25)):
    texte = fin(nom, n) if nom else ""
    if texte:
        print(f"\n{titre}, from memory:\n{texte.rstrip()}")
