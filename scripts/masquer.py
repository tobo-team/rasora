#!/usr/bin/env python3
"""masquer.py - masque ou montre un navigateur de travail, au niveau de l'APPLICATION.

POURQUOI (24/08/2026, apres trois tentatives qui n'ont pas suffi)
Repousser la fenetre hors ecran ne tient pas : macOS la ramene. Reprendre le focus
apres coup ne tient pas non plus : on court derriere, et l utilisateur voit quand meme la
page apparaitre. La cause est plus haut : tant que ce Chrome est une application de
premier plan avec une fenetre, macOS a le droit de la lui donner.

Masquer l'APPLICATION (le « Hide » du menu Pomme) supprime le probleme a la racine :
plus de fenetre affichable, donc plus rien a montrer a l utilisateur, et macOS ne donne pas
le premier plan a une app masquee.

Mesure faite avant d'adopter la methode, navigateur masque :
  - `elements` rend bien les 9 boutons de la page ;
  - `document.visibilityState` = 'visible', `hasFocus()` = true (emulation) ;
  - une capture rend une vraie image (1728x7200, 357 teintes) ;
  - un clic passe en 1,47 s, contre 2,08 s fenetre affichee.
Tout fonctionne, et plus vite.

`NSRunningApplication.hide()` de PyObjC rend False et ne fait rien depuis un process
de fond : seul System Events y arrive. C'est pour ca qu'on passe par osascript.

  masquer.py                 masque le navigateur bot et le clone
  masquer.py montrer         les rend visibles (login a la main)
  masquer.py etat            dit qui est masque
"""
import os
import subprocess
import sys

# Chemins relatifs a la maison de celui qui installe : rien en dur.
MARQUES = tuple("user-data-dir=" + os.path.expanduser(d)
                for d in ("~/.neverlogout/chrome-profile", "~/.neverlogout/chrome-profile"))


def pids():
    out = subprocess.run(["ps", "-Ao", "pid,args"], capture_output=True, text=True).stdout
    trouve = []
    for ligne in out.splitlines():
        if "Helper" in ligne or "MacOS/Google Chrome" not in ligne:
            continue
        if any(m in ligne for m in MARQUES):
            try:
                trouve.append(int(ligne.split()[0]))
            except ValueError:
                pass
    return trouve


def osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return (r.stdout or r.stderr).strip()


def visible(pid, quoi):
    return osa(f'tell application "System Events" to set visible of '
               f'(first application process whose unix id is {pid}) to {quoi}')


def etat(pid):
    return osa(f'tell application "System Events" to get visible of '
               f'(first application process whose unix id is {pid})')


def masquer(pid):
    """Rend True si l'app est masquee apres l'appel."""
    if etat(pid) == "false":
        return True                      # deja masquee : on ne fait rien
    visible(pid, "false")
    return etat(pid) == "false"


def main():
    quoi = sys.argv[1] if len(sys.argv) > 1 else "masquer"
    ps = pids()
    if not ps:
        print("aucun navigateur de travail lance")
        return 1
    for pid in ps:
        if quoi == "montrer":
            visible(pid, "true")
            osa(f'tell application "System Events" to set frontmost of '
                f'(first application process whose unix id is {pid}) to true')
            print(f"  {pid} : visible")
        elif quoi == "etat":
            print(f"  {pid} : {'masque' if etat(pid) == 'false' else 'VISIBLE'}")
        else:
            print(f"  {pid} : {'masque' if masquer(pid) else 'ECHEC DU MASQUAGE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
