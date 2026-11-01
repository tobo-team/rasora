#!/usr/bin/env python3
"""The sites the user signed in to inside Rasora's own Chrome.

  configurer-sessions.py list            sites and accounts known to Rasora
  configurer-sessions.py add <url>       remember a site after a sign-in
  configurer-sessions.py remove <site>   sign out: delete its cookies from Rasora's Chrome

Rasora never reads the user's everyday Chrome. A session exists here only because the user
signed in by hand, in Rasora's own window.
"""
import json
import os
import sys
import urllib.parse

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from sessions import oublier, bot_vivant  # noqa: E402
from sensibles import sensible  # noqa: E402

TABLE = os.path.join(ICI, "sessions.json")


def domaine(texte):
    texte = texte.strip().lower()
    hote = urllib.parse.urlparse(texte).netloc if "://" in texte else texte
    morceaux = hote.split("/")[0].split(":")[0].split(".")
    return ".".join(morceaux[-2:]) if len(morceaux) >= 2 else ""


def lire():
    if os.path.exists(TABLE):
        try:
            return json.load(open(TABLE, encoding="utf-8"))
        except ValueError:
            pass
    return {}


def ecrire(t):
    fd = os.open(TABLE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(t, f, indent=2, ensure_ascii=False)


def main():
    a = sys.argv[1:]
    if not a or a[0] == "list":
        t = lire()
        print("\n".join(f"  {n}" for n in sorted(t)) or "  no site yet. Run: rasora login <url>")
    elif a[0] == "add" and len(a) == 2:
        site = domaine(a[1])
        if site:
            t = lire()
            t[site] = {"domaines": ["*." + site], "sonde": a[1], "signe": ""}
            ecrire(t)
            print(f"  {site}: signed in")
            if sensible(a[1]):
                print("  warning: this site holds money or identity. An agent can be tricked: "
                      "run `rasora logout` when you are done.")
    elif a[0] == "remove" and len(a) == 2:
        site, t = domaine(a[1]) or a[1], lire()
        t.pop(site, None)
        ecrire(t)
        n = oublier(["*." + site]) if bot_vivant() else 0
        print(f"  {site}: signed out, {n} cookies deleted")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
