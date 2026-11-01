#!/usr/bin/env python3
"""Garde les sessions du navigateur bot vivantes, sans jamais deranger l utilisateur.

Pourquoi (22/08/2026) : une re-authentification demandee par Google a fait tomber
d'un coup la session Google ET la session admin Shopify du navigateur bot. Une
session en moins, c'est une voie de travail bloquee et un aller-retour vers
l utilisateur. Le Chrome reel personnel, lui, garde ses sessions : on va les chercher.

Le principe : le bot n'a jamais besoin de se connecter. Il emprunte les cookies
du profil Chrome qui porte deja le compte (table `sessions.json`), par CDP, sans
relancer quoi que ce soit et sans qu'un mot de passe circule.

  sessions.py etat [nom ...]      teste chaque session, VIVANTE ou MORTE
  sessions.py reparer [nom ...]   regreffe ce qui est mort, puis reteste
  sessions.py assurer <nom>       reparer une seule session, silencieux si OK
  sessions.py elaguer             teste tout, RETIRE de la table ce qui ne vit pas
  sessions.py profils             quel profil Chrome porte quel compte

Appele toutes les 20 minutes par launchd `com.neverlogout.sessions`. Aucun modele
n'est invoque : le cout est nul.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

PORT = int(os.environ.get("CDP_PORT", "9333"))
ICI = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(ICI, "sessions.json")
GREFFE = os.path.join(ICI, "cookies-vers-bot.py")
PY = os.path.join(ICI, ".venv-cdp", "bin", "python")
SAUVEGARDES = os.path.expanduser("~/.neverlogout/sessions")
JOURNAL = os.path.join(SAUVEGARDES, "sessions.log")
CHROME = os.path.expanduser("~/Library/Application Support/Google/Chrome")


def note(msg):
    ligne = time.strftime("%Y-%m-%d %H:%M") + "  " + msg
    print(msg)
    os.makedirs(SAUVEGARDES, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def table():
    if not os.path.exists(TABLE):
        sys.exit("no site allowed yet. Run: neverlogout allow <site>")
    return json.load(open(TABLE, encoding="utf-8"))


def pages():
    try:
        d = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/json/list", timeout=10))
    except Exception:
        return []
    return [t for t in d if t.get("type") == "page"]


def bot_vivant():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=5)
        return True
    except Exception:
        return False


class Onglet:
    """Un onglet de sonde, ouvert une fois et referme a la fin."""

    def __init__(self):
        import websocket  # noqa
        self.websocket = websocket
        self._ouvrir()

    def _ouvrir(self):
        websocket = self.websocket
        # `Target.createTarget` avec background=True, JAMAIS `/json/new` : l'appel
        # HTTP restaure et ramene la fenetre du navigateur bot DEVANT L'ECRAN DE
        # Ce script tourne toutes les 20 minutes sous launchd ; c'etait,
        # avec `Page.bringToFront` plus bas, la teleportation qui l'interrompait
        # pendant qu'il travaillait.
        self.id = None
        try:
            v = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/version", timeout=10))
            nav = websocket.create_connection(v["webSocketDebuggerUrl"], timeout=30)
            nav.send(json.dumps({"id": 1, "method": "Target.createTarget",
                                 "params": {"url": "about:blank", "background": True}}))
            while True:
                r = json.loads(nav.recv())
                if r.get("id") == 1:
                    self.id = r.get("result", {}).get("targetId")
                    break
            nav.close()
        except Exception:
            self.id = None
        if not self.id:                      # repli, si createTarget echoue
            req = urllib.request.Request(
                f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")
            self.id = json.load(urllib.request.urlopen(req, timeout=15))["id"]
        cible = None
        fin = time.time() + 5
        while time.time() < fin and not cible:
            cible = next((t for t in pages() if t["id"] == self.id), None)
            if not cible:
                time.sleep(0.05)
        if not cible:
            raise RuntimeError("probe tab did not open")
        self.ws = websocket.create_connection(cible["webSocketDebuggerUrl"], timeout=60)
        self.n = 0
        self.premier_plan()

    def premier_plan(self):
        """La page se croit visible et focalisee, sans qu'aucune fenetre bouge.
        Remplace `Page.bringToFront`, qui faisait surgir le navigateur bot."""
        try:
            self.cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
            self.cmd("Page.setWebLifecycleState", {"state": "active"})
        except Exception:
            pass

    def cmd(self, methode, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": methode,
                                 "params": params or {}}))
        fin = time.time() + 60
        while time.time() < fin:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.n:
                return r.get("result", {})
        return {}

    def texte(self, url, secondes=12):
        """Navigue et rend le texte de la page. Se rebranche si le process change.

        On sonde au lieu de dormir : six sites x 12 s d'attente fixe, c'etait plus
        d'une minute de sonde toutes les 20 minutes pour des pages pretes en deux
        secondes. On repart des que la page est chargee ET qu'elle a du texte, ou
        qu'elle a redirige vers une connexion (auquel cas inutile d'attendre).
        """
        try:
            self.cmd("Page.navigate", {"url": url})
        except Exception:
            try:
                self._rebrancher()
                self.cmd("Page.navigate", {"url": url})
            except Exception:
                return ""          # probe failed : traitee comme une session morte
        self.premier_plan()
        fin = time.time() + secondes
        dernier = ""
        while time.time() < fin:
            try:
                r = self.cmd("Runtime.evaluate", {
                    "expression": "JSON.stringify([document.readyState,"
                                  "document.body?(document.body.innerText||'').trim():''"
                                  ",location.href])",
                    "returnByValue": True})
                etat, corps, href = json.loads(
                    r.get("result", {}).get("value") or '["","",""]')
                dernier = (corps or "") + "\n" + (href or "")
                if etat == "complete" and (len(corps) > 40 or CONNEXION.search(href)):
                    time.sleep(0.4)      # laisse une redirection tardive se poser
                    r = self.cmd("Runtime.evaluate", {
                        "expression": "JSON.stringify([document.body?"
                                      "(document.body.innerText||'').trim():'',location.href])",
                        "returnByValue": True})
                    corps, href = json.loads(r.get("result", {}).get("value") or '["",""]')
                    return (corps or "") + "\n" + (href or "")
            except Exception:
                self._rebrancher()
            time.sleep(0.25)
        return dernier

    def url(self):
        for t in pages():
            if t["id"] == self.id:
                return t.get("url", "")
        return ""

    def _rebrancher(self):
        """Reprend la main sur l'onglet de sonde, quoi qu'il lui soit arrive.

        Mesure du 31/08/2026 sur un profil neuf : un onglet peut DISPARAITRE en
        cours de sonde (renderer tue, page qui se ferme elle-meme). L'ancienne
        version se contentait de chercher l'onglet dans la liste ; ne le trouvant
        plus, elle laissait une socket morte et la commande suivante remontait une
        trace d'erreur en pleine installation. On rouvre donc un onglet neuf.
        """
        for t in pages():
            if t["id"] == self.id:
                try:
                    self.ws = self.websocket.create_connection(
                        t["webSocketDebuggerUrl"], timeout=60)
                    self.n = 0
                    return
                except Exception:
                    break
        try:
            self.ws.close()
        except Exception:
            pass
        self._ouvrir()

    def fermer(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/close/{self.id}", timeout=10)
        except Exception:
            pass


# Une page de connexion n'est JAMAIS une session vivante, quel que soit le signe
# cherche. Mesure le 23/08/2026 : la sonde PostHog `/activity/explore` redirigee
# vers `/login?next=/project/250355/activity/explore` contenait le mot cherche
# DANS SON URL, et `texte()` colle l'URL a la fin du texte. La session etait donc
# annoncee VIVANTE sur un ecran de connexion, et le tableau de bord rendait des
# cases vides sans jamais dire pourquoi. On ecarte l'URL de connexion d'abord.
CONNEXION = re.compile(r"/(login|signin|sign-in|auth|accounts/login)\b", re.I)


def tester(onglet, nom, conf):
    """VIVANTE, MORTE, ou VIVANTE par presomption. Rend (bool, comment).

    Le signe seul ne suffit pas : le 23/08/2026, `myaccount.google.com` n'ecrivait
    plus l'adresse dans le texte de la page en 12 secondes, et une session
    parfaitement vivante etait declaree MORTE, ce qui declenche des greffes
    inutiles et finit par « l utilisateur doit se reconnecter » sans raison.

    Le signal qui ne ment pas est la REDIRECTION : un site qui ne nous connait
    plus renvoie vers sa page de connexion. On tranche donc dans cet ordre :
      1. redirige vers une page de connexion  -> MORTE, c'est certain ;
      2. le signe est dans la page            -> VIVANTE, c'est certain ;
      3. reste sur le domaine sonde           -> VIVANTE par presomption, dit tel quel.
    """
    txt = onglet.texte(conf["sonde"])
    derniere = txt.strip().split("\n")[-1] if txt.strip() else ""
    if CONNEXION.search(derniere):
        return False, "login page"
    if conf.get("signe") and conf["signe"].lower() in txt.lower():
        return True, ""
    hote = urllib.parse.urlparse(conf["sonde"]).netloc.split(".")[-2:]
    if derniere and ".".join(hote) in derniere:
        return True, "presumed: no redirect to login"
    return False, "no proof of login"


def greffer(profil, conf):
    cmd = [PY, GREFFE, profil] + conf["domaines"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.expanduser("~"))
    sortie = (r.stdout or "") + (r.stderr or "")
    poses = sortie.strip().split("\n")[0] if sortie.strip() else "rien"
    return r.returncode == 0, poses


def profils_candidats(domaines, limite=4):
    """Les profils Chrome qui portent le plus de cookies pour ces domaines.

    On ne fait pas confiance au profil ecrit dans la table : l utilisateur se
    reconnecte parfois ailleurs, et c'est justement ce qu'on ne veut plus
    avoir a lui demander.
    """
    import shutil
    import sqlite3
    import tempfile
    racines = {d.lstrip("*.").lower() for d in domaines if "." in d.lstrip("*.")}
    if not racines:
        return []
    # exact domain or subdomain: a loose LIKE '%x%' matched every host with an x in it
    ou = " OR ".join("host_key = ? OR host_key = ? OR host_key LIKE ?" for _ in racines)
    valeurs = [v for r in sorted(racines) for v in (r, "." + r, "%." + r)]
    scores = []
    for prof in sorted(os.listdir(CHROME)):
        src = os.path.join(CHROME, prof, "Cookies")
        if not os.path.exists(src):
            continue
        tmp = tempfile.mkdtemp()
        copie = os.path.join(tmp, "Cookies")
        try:
            shutil.copy2(src, copie)
            for suffixe in ("-wal", "-shm"):
                if os.path.exists(src + suffixe):
                    shutil.copy2(src + suffixe, copie + suffixe)
            con = sqlite3.connect(f"file:{copie}?mode=ro", uri=True)
            n = con.execute("SELECT count(*) FROM cookies WHERE " + ou, valeurs).fetchone()[0]
            con.close()
            if n:
                scores.append((n, prof))
        except Exception:
            pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    scores.sort(reverse=True)
    return [prof for _, prof in scores[:limite]]


def oublier(domaines):
    """Delete from the bot every cookie of these domains. Rend le nombre efface."""
    import websocket
    ws_url = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/json/version", timeout=10))["webSocketDebuggerUrl"]
    ws = websocket.create_connection(ws_url, timeout=30)
    ws.send(json.dumps({"id": 1, "method": "Storage.getCookies", "params": {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            break
    ws.close()
    racines = {d.lstrip("*.") for d in domaines}

    def vise(hote):
        hote = hote.lstrip(".")
        return any(hote == x or hote.endswith("." + x) for x in racines)

    cibles = [c for c in r["result"]["cookies"] if vise(c["domain"])]
    if cibles:
        onglet = Onglet()
        try:
            for c in cibles:
                onglet.cmd("Network.deleteCookies", {"name": c["name"], "domain": c["domain"],
                                                     "path": c.get("path", "/")})
        finally:
            onglet.fermer()
    return len(cibles)


def profils():
    d = json.load(open(os.path.join(CHROME, "Local State"), encoding="utf-8"))
    for k, v in sorted(d.get("profile", {}).get("info_cache", {}).items()):
        if v.get("user_name"):
            print(f"  {k:12} {v.get('user_name')}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "etat"
    noms = sys.argv[2:]

    if action == "profils":
        return profils()

    if not bot_vivant():
        note("browser is off. Run: neverlogout start")
        sys.exit(1)

    conf_all = table()
    if action == "greffer":
        # First visit to a site: copy now. A probe would see a public page, call the
        # session alive and copy nothing.
        for nom in noms:
            if nom in conf_all:
                print(f"  {nom}: {greffer(conf_all[nom]['profil'], conf_all[nom])[1]}")
        return

    # A site added on first visit is not probed every 20 minutes: it heals itself
    # the next time a page lands on its login screen. Tests stay cheap that way.
    cibles = {k: v for k, v in conf_all.items()
              if k in noms or (not noms and not v.get("lazy"))}
    if not cibles and not noms:
        print("  nothing to check")
        return
    if not cibles:
        sys.exit(f"unknown session. Known: {', '.join(conf_all)}")

    onglet = Onglet()
    try:
        morts = []
        for nom, conf in cibles.items():
            try:
                ok, comment = tester(onglet, nom, conf)
            except Exception as e:
                ok, comment = False, f"probe failed ({type(e).__name__})"
            if action in ("etat", "elaguer"):
                suffixe = f"  [{comment}]" if comment else ""
                print(f"  {nom:10} {'ALIVE' if ok else 'DEAD'}  ({conf['compte']}){suffixe}")
            if not ok:
                morts.append((nom, conf))

        if action == "etat":
            return

        if action == "elaguer":
            # Une session qu'aucun profil Chrome ne porte n'a rien a faire dans la
            # table : elle ferait travailler le gardien toutes les 20 minutes pour
            # rien et afficherait une fausse alerte a chaque etat. On la retire ;
            # `configurer-sessions.py` la remettra le jour ou le compte existe.
            for nom, _ in morts:
                conf_all.pop(nom, None)
            json.dump(conf_all, open(TABLE, "w", encoding="utf-8"),
                      indent=2, ensure_ascii=False)
            if morts:
                note("removed (not signed in in Chrome): "
                     + ", ".join(n for n, _ in morts))
            print(f"  {len(conf_all)} sessions kept: {', '.join(conf_all)}")
            return

        for nom, conf in morts:
            candidats = [conf["profil"]] + [p for p in profils_candidats(conf["domaines"])
                                            if p != conf["profil"]]
            restauree = None
            for profil in candidats:
                fait, detail = greffer(profil, conf)
                if not fait:
                    continue
                time.sleep(2)
                try:
                    revivante = tester(onglet, nom, conf)[0]
                except Exception:
                    revivante = False
                if revivante:
                    restauree = (profil, detail)
                    break
            if restauree:
                profil, detail = restauree
                note(f"{nom} : session restored from {profil} ({detail})")
                if profil != conf["profil"]:
                    conf_all[nom]["profil"] = profil
                    json.dump(conf_all, open(TABLE, "w", encoding="utf-8"),
                              indent=2, ensure_ascii=False)
                    note(f"{nom} : table now points to {profil}")
            else:
                note(f"{nom} : not signed in. No Chrome profile "
                     f"({', '.join(candidats)}) holds this session. Sign in once to "
                     f"{nom} in your everyday Chrome, repair then resumes by itself.")
        if action == "reparer" and not morts:
            print("  all sessions are alive")
    finally:
        onglet.fermer()


if __name__ == "__main__":
    main()
