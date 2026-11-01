#!/usr/bin/env python3
"""Sign in by hand, once. Shows Rasora's window on a site, waits, then hides it again.

  connexion.py <url> [minutes]

The user types their own password and code in the window. Rasora never sees or stores them:
it only watches the address to know when the sign-in is over.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from nav import page_de_connexion, BASE  # noqa: E402


def nav(*a):
    return subprocess.run([sys.executable, os.path.join(ICI, "nav.py"), *a],
                          capture_output=True, text=True, timeout=60).stdout


def adresses():
    return [t.get("url", "") for t in json.load(urllib.request.urlopen(f"{BASE}/json/list"))
            if t.get("type") == "page"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url, minutes = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 5
    hote = url.split("/")[2] if "://" in url else url
    racine = ".".join(hote.split(".")[-2:])
    nav("open", url)
    nav("show")
    print(f"A window is open on {racine}. Sign in there, Rasora will hide it when you are done.",
          flush=True)
    fin, vu = time.time() + minutes * 60, False
    while time.time() < fin:
        time.sleep(2)
        ici = [u for u in adresses() if racine in u]
        if not ici:
            continue
        if any(page_de_connexion(u) for u in ici):
            vu = True
        elif vu or not page_de_connexion(ici[0]):
            time.sleep(1)
            nav("hide")
            subprocess.run([sys.executable, os.path.join(ICI, "configurer-sessions.py"),
                            "add", ici[0]])
            return
    nav("hide")
    sys.exit("no sign-in seen. Run this again when you are ready.")


if __name__ == "__main__":
    main()
