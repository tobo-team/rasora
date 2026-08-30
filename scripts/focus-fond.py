#!/usr/bin/env python3
"""focus-fond.py - reprend le premier plan aux navigateurs de travail, et dit qui l'a pris.

POURQUOI CE FICHIER EXISTE (24/08/2026)
Apres avoir banni `bringToFront` de tous les scripts et pose `nav-fond.py`, qui repousse
toute fenetre revenue a l'ecran, l'utilisateur etait TOUJOURS teleporte, et le journal du
gardien restait vide : aucune fenetre n'etait revenue. Ce n'etait donc plus la fenetre,
c'etait le FOCUS. Sur macOS une app peut passer devant sans qu'aucune fenetre bouge : le
clavier part chez elle, l'espace change, et ce que l'utilisateur regardait disparait.

Ce script fait deux choses, toutes les 0,4 s, sans modele :
  1. il NOMME l'app qui prend le premier plan (journal), donc on ne devine plus ;
  2. si c'est un de nos navigateurs de travail, il rend le premier plan a l'app
     que l'utilisateur utilisait juste avant.

Il respecte le mode discret : `nav.py montrer` efface le drapeau pour un login a la main,
et le gardien se tait aussitot sur ce navigateur.

  focus-fond.py          boucle (ce que lance launchd)
  focus-fond.py voir     dit qui est devant, et qui sont les navigateurs surveilles
"""
import os
import re
import subprocess
import sys
import threading
import time

import objc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masquer import masquer                     # noqa: E402
from AppKit import NSRunningApplication, NSWorkspace
from Foundation import NSObject, NSRunLoop

DELAI = float(os.environ.get("FOCUS_FOND_DELAI", "0.4"))
JOURNAL = os.path.expanduser("~/.claude/scripts/focus-fond.log")

# On ne surveille QUE de vrais navigateurs, jamais un process quelconque : la
# premiere version cherchait le mot « gstack » dans toute la ligne de commande et
# ramassait les soixante process des sessions Claude. Le Chrome PERSONNEL personnel
# (aucune de ces marques) n'est jamais surveille.
NAVIGATEUR = re.compile(r"MacOS/(Google Chrome for Testing|Google Chrome|Chromium)\b")
DISCRET_BOT = os.path.expanduser("~/.bot-navigateur/.discret")
DISCRET_CLONE = os.path.expanduser("~/.chrome-perso/.discret")


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


def surveilles():
    """pid -> drapeau, pour les navigateurs de TRAVAIL lances en ce moment."""
    out = subprocess.run(["ps", "-Ao", "pid,args"], capture_output=True, text=True).stdout
    trouve = {}
    for ligne in out.splitlines():
        if "Helper" in ligne or not NAVIGATEUR.search(ligne):
            continue
        bas = ligne.lower()
        if ".bot-navigateur" in bas:
            drapeau = DISCRET_BOT
        elif ".chrome-perso" in bas:
            drapeau = DISCRET_CLONE
        elif "chrome for testing" in bas or "chromium" in bas or "gstack" in bas:
            drapeau = DISCRET_BOT          # le Chromium de gstack surgit aussi
        else:
            continue                       # le Chrome personnel personnel
        try:
            trouve[int(ligne.split()[0])] = drapeau
        except ValueError:
            pass
    return trouve


# A qui rendre le premier plan quand on demarre alors qu'un navigateur de travail
# l'a deja pris : on ne sait pas ou etait l'utilisateur, on vise ce qui lui sert.
REPLIS = ("Terminal", "iTerm2", "Claude", "Code", "Ghostty", "Finder")


def repli(espace):
    apps = {a.localizedName(): a.processIdentifier() for a in espace.runningApplications()
            if a.activationPolicy() == 0}
    for nom in REPLIS:
        if nom in apps:
            return apps[nom]
    return None


def rendre(pid):
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app is None:
        return False
    return bool(app.activateWithOptions_(1 << 1))   # IgnoringOtherApps


def remasquer_au_fond(pid, nom):
    """Hors de la classe : PyObjC transforme toute methode en selecteur Objective-C,
    et `_remasquer(self, pid, nom)` devient un selecteur sans argument, ce qui empeche
    la classe de se construire (BadPrototypeError, paye le 24/08/2026)."""
    try:
        note(f"  {nom} ({pid}) : {'remasque' if masquer(pid) else 'MASQUAGE REFUSE'}")
    except Exception as e:
        note("  masquage impossible : " + str(e)[:120])


class Ecouteur(NSObject):
    """Reagit a la notification macOS d'activation d'app. Zero sondage.

    La premiere version demandait 2,5 fois par seconde qui etait devant : 31 % de CPU
    en continu (mesure du 24/08/2026). macOS publie l'evenement, il suffit de s'y
    abonner : le processus dort le reste du temps.
    """

    def init(self):
        self = objc.super(Ecouteur, self).init()
        self.bots = surveilles()
        self.prochain_ps = time.time() + 30
        self.dernier_bon = None
        self.reprises = []
        self.silence_jusqu_a = 0
        return self

    def appActivee_(self, notif):
        try:
            app = notif.userInfo()["NSWorkspaceApplicationKey"]
            pid, nom = app.processIdentifier(), app.localizedName()
            if time.time() > self.prochain_ps or pid not in self.bots:
                self.bots = surveilles()
                self.prochain_ps = time.time() + 30
            if pid not in self.bots:
                self.dernier_bon = pid
                note(f"devant : {nom} ({pid})")
                return
            note(f"devant : {nom} ({pid})  [NAVIGATEUR DE TRAVAIL]")
            if not os.path.exists(self.bots[pid]):
                return                       # mode discret leve : l'utilisateur l'a voulu
            # LA vraie correction : on ne se contente pas de rendre le focus, on
            # REMASQUE l'application. Une app masquee n'a pas de fenetre affichable,
            # donc macOS ne peut plus la mettre devant l'utilisateur. Tant qu'elle reste
            # masquee, cette ligne ne s'execute jamais.
            #
            # Dans un FIL a part : osascript met parfois plusieurs secondes a
            # repondre depuis launchd, et cette methode tourne sur la boucle
            # d'evenements de macOS. La bloquer, c'est rater les activations
            # suivantes (mesure du 24/08/2026 : 4 s de retard).
            threading.Thread(target=remasquer_au_fond, args=(pid, nom),
                             daemon=True).start()
            maintenant = time.time()
            if maintenant < self.silence_jusqu_a:
                return
            self.reprises = [t for t in self.reprises if maintenant - t < 120]
            # ANTI-PING-PONG : rendre le premier plan peut declencher un aller-retour
            # sans fin. Au-dela de six reprises en deux minutes, on se tait dix minutes
            # et on l'ecrit : un journal exploitable vaut mieux qu'un clignotement.
            if len(self.reprises) >= 6:
                self.silence_jusqu_a = maintenant + 600
                self.reprises = []
                note(f"  {nom} ({pid}) reprend le premier plan en boucle : j'arrete "
                     f"de me battre 10 min, j'observe.")
                return
            if not self.dernier_bon or self.dernier_bon == pid:
                self.dernier_bon = repli(NSWorkspace.sharedWorkspace())
            if self.dernier_bon and self.dernier_bon != pid:
                ok = rendre(self.dernier_bon)
                self.reprises.append(maintenant)
                note(f"  premier plan repris par {nom} ({pid}), rendu a "
                     f"{self.dernier_bon} : {'ok' if ok else 'echec'}")
        except Exception as e:
            note("erreur ignoree : " + str(e)[:120])


def main():
    espace = NSWorkspace.sharedWorkspace()
    bots = surveilles()
    if len(sys.argv) > 1 and sys.argv[1] == "voir":
        f = espace.frontmostApplication()
        print("devant :", f.localizedName(), f.processIdentifier())
        for pid, drapeau in bots.items():
            print("  surveille :", pid,
                  "drapeau" if os.path.exists(drapeau) else "DRAPEAU LEVE")
        return

    note(f"espion demarre (evenementiel, {len(bots)} navigateurs surveilles)")
    ecouteur = Ecouteur.alloc().init()
    f0 = espace.frontmostApplication()
    if f0 is not None:
        ecouteur.dernier_bon = (f0.processIdentifier()
                                if f0.processIdentifier() not in bots else repli(espace))
        note(f"devant : {f0.localizedName()} ({f0.processIdentifier()})")
    espace.notificationCenter().addObserver_selector_name_object_(
        ecouteur, "appActivee:", "NSWorkspaceDidActivateApplicationNotification", None)
    NSRunLoop.currentRunLoop().run()


if __name__ == "__main__":
    main()
