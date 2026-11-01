#!/usr/bin/env python3
"""Decide which sites the agent may use. Nothing is allowed by default.

  configurer-sessions.py list            sites found in Chrome, and which are allowed
  configurer-sessions.py allow a b       allow sites, by name or domain (foo.com)
  configurer-sessions.py allow --all     everywhere: every site you are signed in to
  configurer-sessions.py deny a b        forbid sites and delete their cookies from the bot
  configurer-sessions.py deny --all      back to nothing allowed
  configurer-sessions.py ask             ask once, then site by site if needed
  configurer-sessions.py ensure <url>    in "everywhere" mode, add this site on first visit

`list` only counts cookies per profile. It never decrypts anything. Cookies are
decrypted later, for allowed sites only, by cookies-vers-bot.py.
"""
import json
import os
import sys
import urllib.parse

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from sessions import profils_candidats, oublier, bot_vivant  # noqa: E402
from sensibles import sensible  # noqa: E402

CHROME = os.path.expanduser("~/Library/Application Support/Google/Chrome")
TABLE = os.path.join(ICI, "sessions.json")
PARTOUT = os.path.join(os.path.dirname(ICI), "allow-all")

# `signe` empty = decide from the redirect to the login page. "@" = the Google
# address of the profile.
RECETTES = {
    # Do not add accounts.google.com: it made Gmail and Drive fall back to the login
    # page. `.google.com` is enough. There is no plain "google" entry either, because
    # myaccount.google.com redirects to its landing page even with a valid session.
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
    """{profile: address} from Local State."""
    chemin = os.path.join(CHROME, "Local State")
    if not os.path.exists(chemin):
        return {}
    d = json.load(open(chemin, encoding="utf-8"))
    return {k: v["user_name"]
            for k, v in d.get("profile", {}).get("info_cache", {}).items()
            if v.get("user_name")}


def trouves():
    """Sites that really have cookies in a Chrome profile. Reads counts only."""
    qui = comptes()
    table = {}
    for nom, r in RECETTES.items():
        candidats = profils_candidats(r["domaines"], limite=1)
        if not candidats:
            continue
        profil = candidats[0]
        compte = qui.get(profil, profil)
        signe = compte if r["signe"] == "@" else r["signe"]
        # "@" without a known Google address proves nothing: fall back to the redirect.
        if r["signe"] == "@" and "@" not in compte:
            signe = ""
        table[nom] = {"profil": profil, "compte": compte,
                      "domaines": r["domaines"], "sonde": r["sonde"], "signe": signe}
    return table


def domaine(texte):
    """foo.com from a URL or a host. Two labels: good enough, not a public-suffix list."""
    texte = texte.strip().lower()
    hote = urllib.parse.urlparse(texte).netloc if "://" in texte else texte
    morceaux = hote.split("/")[0].split(":")[0].split(".")
    return ".".join(morceaux[-2:]) if len(morceaux) >= 2 else ""


def entree_libre(site):
    """A table entry for any domain with cookies in Chrome, or None."""
    domaines = ["*." + site]
    candidats = profils_candidats(domaines, limite=1)
    if not candidats:
        return None
    profil = candidats[0]
    return {"profil": profil, "compte": comptes().get(profil, profil), "domaines": domaines,
            "sonde": f"https://{site}/", "signe": "", "lazy": True}


def lire_table():
    if os.path.exists(TABLE):
        try:
            return json.load(open(TABLE, encoding="utf-8"))
        except ValueError:
            pass
    return {}


def ecrire_table(t):
    fd = os.open(TABLE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(t, f, indent=2, ensure_ascii=False)


def lister():
    table, vus = lire_table(), trouves()
    if not vus and not table:
        print("no supported site found in your Chrome")
        return
    for nom in sorted(set(vus) | set(table)):
        c = table.get(nom) or vus[nom]
        print(f"  {nom:10} {'allowed' if nom in table else 'not allowed':12} {c['compte']}")


def permettre(noms):
    vus, table = trouves(), lire_table()
    if noms == ["--all"]:
        open(PARTOUT, "w").close()
        print("  everywhere: sites you are signed in to are added on first visit.")
        print("  Banks, payment, crypto, password managers and government sites stay out.")
        noms = sorted(vus)
    for nom in noms:
        if nom in table:
            print(f"  {nom}: already allowed")
        elif nom not in RECETTES and "." in nom:
            site = domaine(nom)
            c = entree_libre(site) if site else None
            if c:
                table[site] = c
                print(f"  {site}: allowed ({c['compte']})")
                if sensible(site):
                    print("  warning: this site holds money or identity. "
                          "An agent can be tricked: deny it when you are done.")
            else:
                print(f"  {nom}: not signed in in Chrome, sign in once there first")
        elif nom not in RECETTES:
            print(f"  {nom}: unknown site. Use a domain like foo.com, or one of: "
                  f"{', '.join(sorted(RECETTES))}")
        elif nom not in vus:
            print(f"  {nom}: not signed in in Chrome, sign in once there first")
        else:
            table[nom] = vus[nom]
            print(f"  {nom}: allowed ({vus[nom]['compte']})")
    ecrire_table(table)


def interdire(noms):
    table = lire_table()
    if noms == ["--all"]:
        if os.path.exists(PARTOUT):
            os.remove(PARTOUT)
        noms = sorted(table)
    for nom in noms:
        conf = table.pop(nom, None)
        if conf is None:
            print(f"  {nom}: was not allowed")
            continue
        # Gmail and Drive share .google.com: keep what another allowed site still needs.
        gardes = {d for c in table.values() for d in c["domaines"]}
        a_effacer = [d for d in conf["domaines"] if d not in gardes]
        n = oublier(a_effacer) if a_effacer and bot_vivant() else 0
        print(f"  {nom}: denied, {n} cookies deleted from the bot")
    ecrire_table(table)


def assurer_url(url):
    """Everywhere mode: first visit to a site adds it. Prints its name if added."""
    if not os.path.exists(PARTOUT):
        return
    site, table = domaine(url), lire_table()
    if not site or sensible(url):
        return
    couvert = any(site == d.lstrip("*.") or site.endswith("." + d.lstrip("*."))
                  for c in table.values() for d in c["domaines"])
    if couvert:
        return
    c = entree_libre(site)
    if c:
        table[site] = c
        ecrire_table(table)
        print(site)


def demander():
    """One question for everything, then one per site. Default no."""
    vus = trouves()
    if not vus:
        print("  no supported site found in your Chrome")
        return
    try:
        tty = open("/dev/tty")
    except OSError:
        print("  no terminal to ask in. Later, run: rasora allow <site>")
        return
    print("  Let the agent use every account you are signed in to in Chrome? It can then")
    print(f"  act on any site as you. Found: {', '.join(vus)}, and more on first visit.")
    print("  [y/N] ", end="", flush=True)
    if tty.readline().strip().lower() in ("y", "yes"):
        permettre(["--all"])
        return
    print("\n  Then choose site by site. Default is no.\n")
    choix = []
    for nom, c in vus.items():
        print(f"  {nom} ({c['compte']}) [y/N] ", end="", flush=True)
        if tty.readline().strip().lower() in ("y", "yes"):
            choix.append(nom)
    print()
    permettre(choix)


def main():
    if not os.path.isdir(CHROME):
        sys.exit("Chrome data not found. Open Chrome once, sign in, then try again.")
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    noms = sys.argv[2:]
    if action == "list":
        lister()
    elif action == "allow" and noms:
        permettre(noms)
    elif action == "deny" and noms:
        interdire(noms)
    elif action == "ask":
        demander()
    elif action == "ensure" and noms:
        assurer_url(noms[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
