#!/usr/bin/env python3
"""Sign in by hand, once. Shows a window on the current desktop, waits, then hides it.

  connexion.py <url> [minutes]

The user types their own password and code in the window. Rasora never sees or stores them:
it only watches the address to know when the sign-in is over.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from nav import BASE, DRAPEAU, fenetre, navigateur, page_de_connexion  # noqa: E402

MUR = re.compile(r"/(authwall|checkpoint|challenge|uas/)", re.I)


def nav(*a):
    return subprocess.run([sys.executable, os.path.join(ICI, "nav.py"), *a],
                          capture_output=True, text=True, timeout=60).stdout


def masquer(action):
    subprocess.run([sys.executable, os.path.join(ICI, "masquer.py"), action],
                   capture_output=True, text=True, timeout=30)


def app_devant():
    """The app the user is in, so it gets the focus back afterwards."""
    try:
        front = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True).stdout.strip()
        info = subprocess.run(["lsappinfo", "info", "-only", "pid", front],
                              capture_output=True, text=True).stdout
        return int(re.search(r"(\d+)", info)[1])
    except (OSError, TypeError, ValueError):
        return None


def rendre(pid):
    if pid:
        subprocess.run(["osascript", "-e", 'tell application "System Events" to set frontmost of '
                        f"(first application process whose unix id is {pid}) to true"],
                       capture_output=True, timeout=10)


def ouvrir_fenetre(url):
    """A new window opens on the desktop in use. Showing an old one would drag the user to
    whichever desktop it sits on."""
    # The guardians leave the browser alone once this flag is gone: remove it first, or
    # they treat the window as an intrusion and hide it again.
    if os.path.exists(DRAPEAU):
        os.remove(DRAPEAU)
    masquer("afficher")
    o = navigateur()
    tid = o.call("Target.createTarget", {"url": url, "newWindow": True})["targetId"]
    time.sleep(.6)
    w = fenetre(o, tid)
    if w is not None:
        o.call("Browser.setWindowBounds", {"windowId": w, "bounds": {"windowState": "normal"}})
        o.call("Browser.setWindowBounds", {"windowId": w, "bounds": {
            "left": 140, "top": 90, "width": 1080, "height": 780}})
    masquer("devant")
    return tid


def adresse(tid):
    for t in json.load(urllib.request.urlopen(f"{BASE}/json/list")):
        if t.get("id") == tid:
            return t.get("url", "")
    return None


def fermer(tid):
    try:
        urllib.request.urlopen(f"{BASE}/json/close/{tid}", timeout=5)
    except OSError:
        pass


def attendre(tid, fin, depart):
    """A page that isn't a sign-in page proves nothing until a sign-in page was seen: starting
    on a site's home page used to close the window before the user could do anything."""
    vu, dernier = page_de_connexion(depart) or bool(MUR.search(depart)), None
    while time.time() < fin:
        time.sleep(1.5)
        u = adresse(tid)
        if u is None:                    # the user closed the window
            return None if vu else dernier
        if u.startswith("http"):
            if page_de_connexion(u) or MUR.search(u):
                vu = True
            elif vu:
                return u
            else:
                dernier = u
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url, minutes = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 5
    avant = app_devant()
    tid = ouvrir_fenetre(url)
    print("A window is open on your screen. Sign in there: it hides itself when you are done, "
          "or close it yourself.\n"
          "If Chrome offers to save your password, click Save: it can then reconnect by itself.",
          flush=True)
    try:
        fini = attendre(tid, time.time() + minutes * 60, url)
    finally:
        fermer(tid)
        nav("hide")
        rendre(avant)
    if not fini:
        sys.exit("no sign-in seen. Run this again when you are ready.")
    subprocess.run([sys.executable, os.path.join(ICI, "configurer-sessions.py"), "add", fini, url])


if __name__ == "__main__":
    main()
