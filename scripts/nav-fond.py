#!/usr/bin/env python3
"""nav-fond.py - le gardien qui maintient le navigateur bot DERRIERE, en permanence.

POURQUOI CE FICHIER EXISTE (24/08/2026)
On a banni `Page.bringToFront`, `/json/activate` et `/json/new` de tous nos scripts, et
la fenetre du navigateur bot revenait quand meme devant l utilisateur. Mesure : entre deux
verifications, sans qu'aucun script ne tourne, elle est passee de -1160,1071 (hors ecran)
a -381,421 (819 px en plein milieu de l'ecran). macOS repositionne les fenetres hors champ
tout seul : reveil de veille, changement de resolution, branchement d'un ecran, Mission
Control. Aucune discipline dans le code ne peut couvrir ca.

D'ou ce gardien : il ne fait qu'une chose, toutes les DELAI secondes, sans modele et sans
cout : si une fenetre du navigateur bot mord sur l'ecran, il la repousse.

CE QU'IL NE FAIT PAS
  - il ne touche jamais au Chrome personnel personnel (aucun CDP dessus, port 457/9222) ;
  - il se tait quand le mode discret est leve (`nav.py montrer` pour un login a la main,
    qui efface `~/.rasora/chrome-profile/.discret`) : sinon il repousserait la fenetre pendant
    que l utilisateur tape son mot de passe ;
  - il ne touche pas a une fenetre minimisee, ni a une fenetre plein ecran.

  nav-fond.py            tourne en boucle (c'est ce que lance launchd)
  nav-fond.py une-fois   un seul passage, pour verifier
  nav-fond.py voir       dit ou sont les fenetres, sans rien bouger
"""
import json
import os
import sys
import time
import urllib.request

import websocket

# 0,2 s : c'est la duree pendant laquelle l utilisateur peut VOIR la fenetre surgir. A
# 1,5 s le saut restait visible (mesure du 24/08/2026, fenetre apparue a 0,212).
# Ce n'est pas cher parce qu'on ne redemande pas la liste des onglets a chaque
# passage : les identifiants de fenetre sont en cache, un passage = une lecture
# de bounds par fenetre, soit deux appels.
DELAI = float(os.environ.get("NAV_FOND_DELAI", "0.2"))
RAFRAICHIR = 3.0        # secondes entre deux recalculs de la liste des fenetres
COIN = {"left": -5000, "top": 5000, "width": 1200, "height": 900}
MARGE = 100          # tolerance autour du repere, en px
JOURNAL = os.path.expanduser("~/.rasora/bin/nav-fond.log")
# Battement de coeur : tant qu'il est frais, nav.py ne verifie plus les fenetres a
# chaque clic (c'est deja fait ici, toutes les DELAI secondes).
COEUR = os.path.expanduser("~/.rasora/state/nav-fond.coeur")

# port -> drapeau qui autorise le gardien. Absent = mode discret leve, on se tait.
PORTS = {
    int(os.environ.get("CDP_PORT", "9333")): os.path.expanduser("~/.rasora/chrome-profile/.discret"),
    9334: os.path.expanduser("~/.chrome-perso/.discret"),
}


def note(msg):
    ligne = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    print(ligne, flush=True)
    try:
        if os.path.exists(JOURNAL) and os.path.getsize(JOURNAL) > 400_000:
            os.replace(JOURNAL, JOURNAL + ".1")
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass


def repere(drapeau):
    """La position hors ecran reellement obtenue la derniere fois. macOS clampe :
    on demande -5000,5000, il rend par exemple -1160,1071."""
    try:
        d = json.load(open(drapeau, encoding="utf-8"))
        return int(d["left"]), int(d["top"])
    except Exception:
        return None


def ecrire_repere(drapeau, b):
    try:
        json.dump({"left": int(b.get("left", 0)), "top": int(b.get("top", 0))},
                  open(drapeau, "w", encoding="utf-8"))
    except Exception:
        pass


class Pont:
    """Connexion au niveau navigateur, gardee ouverte entre deux passages."""

    def __init__(self, port):
        self.port = port
        self.ws = None
        self.n = 0
        self.fenetres_connues = []
        self.prochain_recalcul = 0

    def brancher(self):
        u = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/json/version", timeout=3))["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(u, timeout=10, suppress_origin=True)
        self.n = 0

    def call(self, m, p=None):
        if self.ws is None:
            self.brancher()
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": m, "params": p or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.n:
                return r.get("result", {})

    def _recalculer(self):
        """Quelles fenetres existent. Coute une liste d'onglets, donc on l'espace."""
        vus = []
        cibles = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/json/list", timeout=3))
        for t in cibles:
            if t.get("type") != "page":
                continue
            try:
                w = self.call("Browser.getWindowForTarget",
                              {"targetId": t["id"]}).get("windowId")
                if w is not None and w not in vus:
                    vus.append(w)
            except Exception:
                self.ws = None
                raise
        self.fenetres_connues = vus
        self.prochain_recalcul = time.time() + RAFRAICHIR

    def fenetres(self):
        if time.time() > getattr(self, "prochain_recalcul", 0):
            self._recalculer()
        out = []
        for w in list(self.fenetres_connues):
            try:
                out.append((w, self.call("Browser.getWindowBounds",
                                         {"windowId": w}).get("bounds", {})))
            except Exception:
                self.prochain_recalcul = 0        # fenetre fermee : on recalcule
        return out


def devant(b, rep):
    """Vrai si cette fenetre mord sur l'ecran de l'utilisateur."""
    if b.get("windowState") in ("minimized", "fullscreen"):
        return False
    if rep is None:
        return True
    return abs(b.get("left", 0) - rep[0]) > MARGE or abs(b.get("top", 0) - rep[1]) > MARGE


def passe(ponts, bruyant=False, bouger=True):
    bouges = 0
    for port, drapeau in PORTS.items():
        if not os.path.exists(drapeau):
            continue                     # mode discret leve : on ne fait rien
        rep = repere(drapeau)
        try:
            for w, b in ponts[port].fenetres():
                if bruyant:
                    note(f"port {port} fenetre {w} {b.get('left')},{b.get('top')} "
                         f"{b.get('windowState')} -> "
                         + ("DEVANT" if devant(b, rep) else "au fond"))
                if not bouger or not devant(b, rep):
                    continue
                ponts[port].call("Browser.setWindowBounds",
                                 {"windowId": w, "bounds": dict(COIN)})
                nb = ponts[port].call("Browser.getWindowBounds",
                                      {"windowId": w}).get("bounds", {})
                ecrire_repere(drapeau, nb)
                bouges += 1
                note(f"port {port} : fenetre revenue a {b.get('left')},{b.get('top')}, "
                     f"repoussee a {nb.get('left')},{nb.get('top')}")
        except Exception:
            ponts[port].ws = None        # navigateur eteint ou redemarre
    return bouges


def main():
    quoi = sys.argv[1] if len(sys.argv) > 1 else "boucle"
    ponts = {p: Pont(p) for p in PORTS}
    if quoi == "voir":
        passe(ponts, bruyant=True, bouger=False)
        return
    if quoi == "une-fois":
        n = passe(ponts, bruyant=True)
        print(f"{n} fenetre(s) repoussee(s)")
        return
    note(f"gardien demarre (toutes les {DELAI}s, ports {', '.join(map(str, PORTS))})")
    os.makedirs(os.path.dirname(COEUR), exist_ok=True)
    prochain_masquage = 0
    while True:
        try:
            passe(ponts)
            open(COEUR, "w").write(str(int(time.time())))
            # Seconde barriere, toutes les 30 s : si une app de travail s'est
            # demasquee sans passer par une activation (l'espion `focus-fond` ne
            # verrait rien), on la remasque. Coute un osascript par demi-minute.
            if time.time() > prochain_masquage:
                prochain_masquage = time.time() + 30
                import subprocess
                r = subprocess.run([os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "masquer.py")],
                                   capture_output=True, text=True, timeout=30)
                for l in (r.stdout or "").splitlines():
                    if "ECHEC" in l:
                        note("masquage refuse : " + l.strip())
        except Exception as e:
            note("erreur ignoree : " + str(e)[:120])
        time.sleep(DELAI)


if __name__ == "__main__":
    main()
