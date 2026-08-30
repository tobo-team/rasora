#!/usr/bin/env python3
"""configurer-sessions.py - ecrit sessions.json tout seul, en lisant le Chrome local.

Pourquoi : la table des sessions est la SEULE chose personnelle du systeme (quel
profil Chrome porte quel compte, sur quels domaines, et comment verifier qu'on est
connecte). La faire remplir a la main, c'est la garantie qu'elle sera fausse.

Ici on la deduit : on lit `Local State` pour connaitre les profils et leurs comptes,
puis on compte les cookies de chaque site dans chaque profil. Un site n'entre dans la
table que si un profil porte vraiment ses cookies. Rien ne sort de la machine.

  configurer-sessions.py            ecrit sessions.json a cote de ce fichier
  configurer-sessions.py --montrer  affiche ce qu'il trouverait, sans rien ecrire
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from sessions import profils_candidats  # noqa: E402  (meme dossier)

CHROME = os.path.expanduser("~/Library/Application Support/Google/Chrome")
TABLE = os.path.join(ICI, "sessions.json")

# Les sites qu'on sait verifier. `signe` vide = on tranche sur la redirection vers
# la page de connexion, ce que `sessions.py tester` sait faire. "@" = l'adresse du
# compte Google du profil, remplacee a la volee.
RECETTES = {
    # Deux mesures du 31/08/2026, sur un profil de bot neuf, qui expliquent ces
    # listes courtes :
    #  - pas d'entree "google" a part : `myaccount.google.com` renvoie vers sa page
    #    vitrine meme avec SID et SAPISID greffes (controle d'integrite d'appareil),
    #    et on declarait MORTE une session qui ouvre Gmail sans broncher ;
    #  - ne PAS greffer `accounts.google.com` : en l'ajoutant, gmail et drive sont
    #    passes de VIVANTE a « page de connexion ». Les cookies du contexte d'auth
    #    rendent l'etat incoherent et Google redemande une connexion. `.google.com`
    #    suffit, et il couvre deja `accounts.google.com` pour la regreffe
    #    automatique de nav.py (le domaine parent l'englobe).
    "gmail": {
        "domaines": [".google.com", "mail.google.com"],
        "sonde": "https://mail.google.com/mail/u/0/", "signe": "@"},
    "drive": {
        "domaines": [".google.com", "drive.google.com", "docs.google.com"],
        "sonde": "https://drive.google.com/drive/my-drive", "signe": "@"},
    "youtube": {
        "domaines": [".youtube.com", "www.youtube.com", ".googleusercontent.com"],
        "sonde": "https://www.youtube.com/account", "signe": ""},
    "github": {
        "domaines": [".github.com", "github.com"],
        "sonde": "https://github.com/settings/profile", "signe": ""},
    "shopify": {
        "domaines": [".shopify.com", "admin.shopify.com", "accounts.shopify.com",
                     ".myshopify.com"],
        "sonde": "https://admin.shopify.com/", "signe": ""},
    "notion": {
        "domaines": [".notion.so", "www.notion.so"],
        "sonde": "https://www.notion.so/", "signe": ""},
    "x": {
        "domaines": [".x.com", ".twitter.com"],
        "sonde": "https://x.com/home", "signe": ""},
    "instagram": {
        "domaines": [".instagram.com", "www.instagram.com"],
        "sonde": "https://www.instagram.com/", "signe": ""},
    "tiktok": {
        "domaines": [".tiktok.com", "www.tiktok.com"],
        "sonde": "https://www.tiktok.com/foryou", "signe": ""},
    "linkedin": {
        "domaines": [".linkedin.com", "www.linkedin.com"],
        "sonde": "https://www.linkedin.com/feed/", "signe": ""},
    "canva": {
        "domaines": [".canva.com", "www.canva.com"],
        "sonde": "https://www.canva.com/projects", "signe": ""},
    "figma": {
        "domaines": [".figma.com", "www.figma.com"],
        "sonde": "https://www.figma.com/files", "signe": ""},
    "vercel": {
        "domaines": [".vercel.com", "vercel.com"],
        "sonde": "https://vercel.com/dashboard", "signe": ""},
}


def comptes():
    """{profil: adresse} d'apres Local State. Un profil sans compte n'y est pas."""
    chemin = os.path.join(CHROME, "Local State")
    if not os.path.exists(chemin):
        return {}
    d = json.load(open(chemin, encoding="utf-8"))
    return {k: v["user_name"]
            for k, v in d.get("profile", {}).get("info_cache", {}).items()
            if v.get("user_name")}


def construire():
    qui = comptes()
    table = {}
    for nom, r in RECETTES.items():
        candidats = profils_candidats(r["domaines"], limite=1)
        if not candidats:
            continue
        profil = candidats[0]
        compte = qui.get(profil, profil)
        signe = compte if r["signe"] == "@" else r["signe"]
        # un signe "@" sans compte Google connu ne prouve rien : on retombe sur
        # la detection par redirection.
        if r["signe"] == "@" and "@" not in compte:
            signe = ""
        table[nom] = {"profil": profil, "compte": compte,
                      "domaines": r["domaines"], "sonde": r["sonde"], "signe": signe}
    return table


def main():
    if not os.path.isdir(CHROME):
        sys.exit("Chrome introuvable. Installe Google Chrome et connecte-toi une "
                 "fois a tes comptes, puis relance.")
    table = construire()
    if not table:
        sys.exit("aucune session trouvee dans ton Chrome. Connecte-toi au moins a "
                 "un compte Google dans Chrome, puis relance ce script.")

    if "--montrer" in sys.argv:
        for nom, c in table.items():
            print(f"  {nom:10} {c['profil']:12} {c['compte']}")
        return

    # on ne detruit jamais une table existante : on complete ce qui manque.
    ancienne = {}
    if os.path.exists(TABLE):
        try:
            ancienne = json.load(open(TABLE, encoding="utf-8"))
        except Exception:
            ancienne = {}
    fusion = dict(table)
    fusion.update(ancienne)
    json.dump(fusion, open(TABLE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for nom, c in fusion.items():
        marque = "  " if nom in ancienne else "+ "
        print(f"{marque}{nom:10} {c['profil']:12} {c['compte']}")
    print(f"\n{len(fusion)} sessions dans {TABLE}")


if __name__ == "__main__":
    main()
