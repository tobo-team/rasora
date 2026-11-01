#!/usr/bin/env python3
"""Plain-file memory: what the agent learned, per site and in general.

  memoire.py save <site|general> <text>    add a dated line
  memoire.py show <site|general|url>       print what is known
  memoire.py search <words...>             lines containing all these words

Files live in ~/.neverlogout/memory, one Markdown file per site. No model, no index,
no network, so reading it costs nothing. The user can open and edit every file.
"""
import os
import re
import sys
import time
import urllib.parse

RACINE = os.path.expanduser("~/.neverlogout/memory")


def cle(nom):
    """A site name from a URL, a host or a word: https://app.foo.com/x -> foo.com"""
    nom = nom.strip().lower()
    hote = urllib.parse.urlparse(nom).netloc if "://" in nom else nom
    hote = hote.split("/")[0].split(":")[0]
    morceaux = hote.split(".")
    if len(morceaux) >= 2:
        hote = ".".join(morceaux[-2:])
    return re.sub(r"[^a-z0-9._-]", "-", hote) or "general"


def chemin(nom):
    return os.path.join(RACINE, cle(nom) + ".md")


def save(nom, texte):
    os.makedirs(RACINE, mode=0o700, exist_ok=True)
    with open(chemin(nom), "a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%Y-%m-%d')}: {' '.join(texte.split())}\n")
    print(f"remembered for {cle(nom)}")


def show(nom):
    if os.path.exists(chemin(nom)):
        print(f"WHAT YOU ALREADY LEARNED ON {cle(nom)} (notes, check them):")
        print(open(chemin(nom), encoding="utf-8").read().rstrip())


def search(mots):
    if not os.path.isdir(RACINE):
        return
    mots = [m.lower() for m in mots]
    for f in sorted(os.listdir(RACINE)):
        for ligne in open(os.path.join(RACINE, f), encoding="utf-8"):
            if all(m in ligne.lower() for m in mots):
                print(f"{f[:-3]}: {ligne.rstrip()}")


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
