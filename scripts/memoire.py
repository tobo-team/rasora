#!/usr/bin/env python3
"""Plain-file memory: what the agent learned, per site and in general.

  memoire.py save <site|general> <text>    add a dated line
  memoire.py show <site|general|url>       print what is known
  memoire.py search <words...>             lines containing all these words

Files live in ~/.rasora/memory, one Markdown file per site. No model, no index,
no network, so reading it costs nothing. The user can open and edit every file.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensibles import hote_de, racine  # noqa: E402

RACINE = os.path.expanduser("~/.rasora/memory")
A_RETENIR = re.compile(r"retiens|souviens[- ]toi|garde (ca|ça|le|la) en t[eê]te|en t[eê]te pour|"
                       r"n'oublie pas|je pr[eé]f[eè]re|remember|keep in mind|i prefer|"
                       r"from now on|[àa] partir de maintenant", re.I)
SECRET = re.compile(r"sk[-_][a-z0-9_-]{12}|rk_live_|gh[pousr]_[a-z0-9]{12}|github_pat_|glpat-|"
                    r"akia[0-9a-z]{12}|xox[abprs]-|aiza[0-9a-z_-]{20}|ya29\.|npm_[a-z0-9]{20}|"
                    r"eyj[\w-]{8,}\.eyj|-----begin|password|mot de passe|\bmdp\b|bearer |"
                    r"(api[_ -]?key|secret|token)\s*[:=]|\b(?:\d[ -]?){13,19}\b", re.I)


def cle(nom):
    """A site name from a URL, a host or a word: https://app.foo.com/x -> foo.com"""
    nom = nom.strip().lower()
    if nom.startswith("project-"):
        return re.sub(r"[^a-z0-9._-]", "-", nom)
    hote = hote_de(nom) or ""
    return re.sub(r"[^a-z0-9._-]", "-", racine(hote) or hote).strip(".") or "general"


def chemin(nom):
    return os.path.join(RACINE, cle(nom) + ".md")


def save(nom, texte):
    if SECRET.search(texte):
        sys.exit("not saved: this looks like a password or a key")
    os.makedirs(RACINE, mode=0o700, exist_ok=True)
    with open(chemin(nom), "a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%Y-%m-%d')}: {' '.join(texte.split())}\n")
    print(f"remembered for {cle(nom)}")


def journal(projet, texte):
    """One line per user message. Things that look like keys or card numbers are not written."""
    if SECRET.search(texte):
        return
    dossier = os.path.join(RACINE, "journal")
    os.makedirs(dossier, mode=0o700, exist_ok=True)
    with open(os.path.join(dossier, cle(projet) + ".md"), "a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')}: {' '.join(texte.split())[:300]}\n")


def show(nom):
    if os.path.exists(chemin(nom)):
        print(f"WHAT YOU ALREADY LEARNED ON {cle(nom)} (notes, check them):")
        print(open(chemin(nom), encoding="utf-8").read().rstrip())


def search(mots):
    if not os.path.isdir(RACINE):
        print("nothing remembered yet")
        return
    mots = [m.lower() for m in mots]
    for f in sorted(os.listdir(RACINE)):
        if not f.endswith(".md"):
            continue
        for ligne in open(os.path.join(RACINE, f), encoding="utf-8"):
            if all(m in ligne.lower() for m in mots):
                print(f"{f[:-3]}: {ligne.rstrip()}")
    journal = os.path.join(RACINE, "journal")
    if os.path.isdir(journal):
        for f in sorted(os.listdir(journal)):
            for ligne in open(os.path.join(journal, f), encoding="utf-8"):
                if all(m in ligne.lower() for m in mots):
                    print(f"journal {f[:-3]}: {ligne.rstrip()[:200]}")


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "save":
        save(a[1], " ".join(a[2:]))
    elif len(a) == 2 and a[0] == "show":
        show(a[1])
    elif len(a) >= 2 and a[0] == "search":
        search(a[1:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
