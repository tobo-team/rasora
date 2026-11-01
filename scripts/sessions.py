#!/usr/bin/env python3
"""Which sites are signed in inside Rasora's own Chrome.

  sessions.py etat [site ...]    test each site, SIGNED IN or SIGNED OUT

A dead session is never repaired from another browser: the user signs in again with
`rasora login`.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

PORT = int(os.environ.get("CDP_PORT", "9333"))
ICI = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(ICI, "sessions.json")
SAUVEGARDES = os.path.expanduser("~/.rasora/sessions")
JOURNAL = os.path.join(SAUVEGARDES, "sessions.log")


def note(msg):
    ligne = time.strftime("%Y-%m-%d %H:%M") + "  " + msg
    print(msg)
    os.makedirs(SAUVEGARDES, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def table():
    if not os.path.exists(TABLE):
        return {}
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


def main():
    if not bot_vivant():
        print("browser is off, nothing to check")
        return
    conf_all, noms = table(), sys.argv[2:]
    cibles = {k: v for k, v in conf_all.items() if not noms or k in noms}
    if not cibles:
        print("  no site yet. Run: rasora login <url>")
        return
    onglet = Onglet()
    try:
        for nom, conf in cibles.items():
            try:
                ok, comment = tester(onglet, nom, conf)
            except Exception as e:
                ok, comment = False, f"probe failed ({type(e).__name__})"
            suffixe = f"  [{comment}]" if comment else ""
            print(f"  {nom:18} {'SIGNED IN' if ok else 'SIGNED OUT'}{suffixe}")
    finally:
        onglet.fermer()


if __name__ == "__main__":
    main()
