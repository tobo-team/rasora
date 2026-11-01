#!/usr/bin/env python3
"""nav.py - piloter un onglet du navigateur bot, par TEXTE et non par coordonnees.

Pourquoi ce fichier existe (16/08/2026) : les scripts d'avant ouvraient un onglet
neuf a chaque appel et le fermaient, donc on perdait la page a chaque etape et on
ne pouvait pas enchainer "ouvrir -> cliquer -> lire". Et cliquer en x/y casse des
qu'un bandeau bouge de 20 px. Ici on garde l'onglet, on le retrouve par un morceau
d'URL, et on clique sur du TEXTE VISIBLE.

Revision 16/08/2026 (ce qu'on a pris a Claude in Chrome, sans payer les captures) :
  - `elements` : l'inventaire de ce qui est cliquable AVANT de deviner un texte.
  - `attendre` : on attend une condition au lieu de dormir un nombre fixe de secondes.
  - `console`  : erreurs JS et reponses HTTP >= 400, pour la QA des sites clients.
  - `photo --sur` : cadrer une section au lieu de capturer 6000 px de page.
  - plus aucun sleep fixe dans `ouvrir` et `clic` : on sonde readyState.

Port par defaut 9333 = navigateur bot (profil ~/.rasora/chrome-profile), jamais le Chrome
personnel. Surcharger avec CDP_PORT (9222 = vrai Chrome via cdp-chrome.sh).

Usage :
  nav.py ouvrir <url> [timeout] [--voie <nom>]   ouvre un onglet et le GARDE ouvert
  nav.py etat [motif-url]              url + titre + connecte? de l'onglet
  nav.py lire [motif-url] [n]          innerText, n caracteres (defaut 4000)
  nav.py elements [motif-url]          inventaire boutons / liens / champs / menus
  nav.py attendre <motif-url> "<texte>" [timeout]   attend que le texte apparaisse
  nav.py clic <motif-url> "<texte>"    clique le 1er element dont le texte contient <texte>
  nav.py champ <motif-url> "<label>" "<valeur>"   remplit un champ (placeholder/name/label)
  nav.py menu <motif-url> "<label>" "<option>"    choisit dans un <select>
  nav.py touche <motif-url> <Enter|Escape|Tab>
  nav.py js <motif-url> "<expr>"       evalue du JS et rend le resultat
  nav.py console [motif-url] [secondes] [--recharger]   erreurs JS + HTTP >= 400
  nav.py photo <motif-url> <nom> [--sur "<texte>"]      capture /tmp/<nom>.png
  nav.py cadres <motif-url>            liste les iframes de la page, avec leur index
  nav.py google                        quel compte Google porte le profil du bot
  nav.py onglets                       liste les onglets : #id, @voie, age, url
  nav.py reserver <motif-url> <voie>   donne cet onglet a une voie de travail
  nav.py fermer <motif-url>
  nav.py discret                       repousse TOUTES ses fenetres hors ecran
  nav.py montrer                       les ramene, pour un login fait a la main

IFRAMES : un paiement, un captcha, un widget vivent dans une iframe et sont donc
invisibles depuis la page. `cadres` les liste ; ensuite `--cadre <n>` (ou un bout
d'URL) marche sur lire, elements, clic, champ, menu, attendre et js :
  nav.py cadres "checkout"
  nav.py elements "checkout" --cadre stripe
  nav.py champ "checkout" --cadre stripe "Numero de carte" "4242..."

Le navigateur bot travaille MASQUE par defaut : il ne doit jamais surgir par-dessus
l'ecran de l'utilisateur. On ne le montre que pour un login, et on remasque juste apres.

DESIGNER UN ONGLET, du plus sur au plus souple :
  #a1b2c3    son identifiant court, affiche par `nav.py onglets` ; ne bouge jamais.
  @shopify   sa voie, si elle a ete reservee (`nav.py reserver "admin.shopify" shopify`).
  shopify    un bout d'URL ; a egalite c'est le plus recemment utilise qui gagne.
Vide = l'onglet actif. Plusieurs sessions en parallele : chacune reserve sa voie une
fois, puis ne vise plus que @sa-voie. Un onglet ainsi tenu n'est jamais ferme par le
ramasse-miettes tant qu'une session s'en sert.

Le navigateur ne revient JAMAIS devant : plus aucun `Page.bringToFront`, l'onglet se
croit au premier plan (Emulation.setFocusEmulationEnabled) sans qu'une fenetre bouge.
Sur une page de connexion, on demande a l utilisateur de se connecter : rasora login.
"""
import base64, json, os, re, sys, time, urllib.parse, urllib.request, websocket

PORT = int(os.environ.get("CDP_PORT", "9333"))
BASE = f"http://127.0.0.1:{PORT}"


def onglets():
    return [t for t in json.load(urllib.request.urlopen(f"{BASE}/json/list"))
            if t.get("type") == "page"]


def navigateur():
    """Connexion au niveau NAVIGATEUR (pas a une page), pour gerer la fenetre."""
    u = json.load(urllib.request.urlopen(f"{BASE}/json/version"))["webSocketDebuggerUrl"]
    return Onglet({"webSocketDebuggerUrl": u})


def fenetre(o, tid):
    r = o.call("Browser.getWindowForTarget", {"targetId": tid})
    return r.get("windowId")


# Drapeau du mode discret. Il sert a REAPPLIQUER la discretion toute seule : une
# popup de connexion (« Continuer avec Google ») ouvre une NOUVELLE fenetre, qui
# nait au milieu de l'ecran de l'utilisateur meme quand les autres sont hors champ.
DRAPEAU = os.path.expanduser("~/.rasora/chrome-profile/.discret")


def _fenetres(o):
    """(windowId, bounds) de chaque fenetre du navigateur, une seule fois chacune.

    Tout passe par la connexion NAVIGATEUR : `Browser.getWindowForTarget` accepte
    un targetId, donc on n'ouvre pas un websocket par onglet. L'ancienne version
    en ouvrait un par onglet a chaque clic : avec douze onglets, douze poignees
    de main pour deplacer une fenetre qui n'avait pas bouge.
    """
    out, vus = [], set()
    for ong in onglets():
        try:
            w = fenetre(o, ong["id"])
            if w is None or w in vus:
                continue
            vus.add(w)
            b = o.call("Browser.getWindowBounds", {"windowId": w}).get("bounds", {})
            out.append((w, b))
        except Exception:
            pass
    return out


def _repere_lire():
    """La position hors ecran REELLE, mesuree la derniere fois qu'on a masque.

    macOS refuse de sortir completement une fenetre de l'ecran : on demande
    (-5000, 5000), il rend par exemple (-1160, 1071), un carre de 40 px en bas a
    gauche. Cette position clampee est notre repere : une fenetre qui s'en ecarte
    est revenue devant l utilisateur, et elle seule doit etre repoussee.
    """
    try:
        d = json.load(open(DRAPEAU, encoding="utf-8"))
        return int(d["left"]), int(d["top"])
    except Exception:
        return None


def _repere_ecrire(b):
    try:
        json.dump({"left": int(b.get("left", 0)), "top": int(b.get("top", 0))},
                  open(DRAPEAU, "w", encoding="utf-8"))
    except Exception:
        pass


def a_l_ecran(b):
    """Vrai si cette fenetre est revenue mordre sur l'ecran de l'utilisateur."""
    if b.get("windowState") in ("minimized", "fullscreen"):
        return b.get("windowState") == "fullscreen"
    rep = _repere_lire()
    if rep is None:                      # pas encore de repere : tout est suspect
        return True
    return (abs(b.get("left", 0) - rep[0]) > 100
            or abs(b.get("top", 0) - rep[1]) > 100)


def placer_fenetres(o, mode):
    """Deplace les fenetres du navigateur bot. Rend le nombre de fenetres bougees.

    En mode discret on ne REECRIT que ce qui est revenu a l'ecran. C'est la
    difference qui compte : ecrire les bounds d'une fenetre, meme pour la
    remettre la ou elle est deja, la fait remonter au premier plan sur macOS.
    """
    coin = {"left": -5000, "top": 5000} if mode == "discret" else {"left": 60, "top": 60}
    bouges = 0
    for w, b in _fenetres(o):
        if mode == "discret" and not a_l_ecran(b):
            continue                      # deja hors champ : on n'y touche pas
        try:
            if b.get("windowState") != "normal":
                o.call("Browser.setWindowBounds",
                       {"windowId": w, "bounds": {"windowState": "normal"}})
            o.call("Browser.setWindowBounds",
                   {"windowId": w, "bounds": dict(coin, width=1200, height=900)})
            bouges += 1
            if mode == "discret":
                # verification positive : on relit ou macOS a REELLEMENT pose la
                # fenetre, et ca devient le repere du prochain passage.
                nb = o.call("Browser.getWindowBounds", {"windowId": w}).get("bounds", {})
                _repere_ecrire(nb)
        except Exception:
            pass
    return bouges


COEUR = os.path.expanduser("~/.rasora/state/nav-fond.coeur")


def rester_discret(o=None):
    """A appeler apres toute action qui peut ouvrir une fenetre (clic, touche).

    Si le gardien `nav-fond.py` bat (launchd `com.rasora.nav-fond`), il regarde les
    fenetres toutes les 1,5 s et fait ce travail mieux que nous : on ne paie pas
    une connexion navigateur a chaque clic pour refaire la meme chose. Sinon on
    verifie soi-meme, en lecture seule, et on n'ecrit que si une fenetre est
    revenue a l'ecran.
    """
    try:
        if time.time() - os.path.getmtime(COEUR) < 10:
            return 0
    except Exception:
        pass
    if not os.path.exists(DRAPEAU):
        return 0
    try:
        return placer_fenetres(navigateur(), "discret")
    except Exception:
        return 0


# ------------------------------------------------- onglets donnes aux sessions
#
# POURQUOI (24/08/2026). Plusieurs sessions travaillent en parallele et chacune a
# « son » onglet. Deux problemes payes :
#   1. `trouver()` prenait le PREMIER onglet dont l'URL contient le motif, et
#      l'ordre de /json/list suit l'activite : avec deux onglets Shopify, une
#      session mesurait l'un et modifiait l'autre.
#   2. le ramasse-miettes ferme un onglet qui n'a pas navigue depuis 30 min. Une
#      session qui lit et clique dans une application (Shopify, Runway) sans
#      changer d'URL voyait son onglet disparaitre sous ses doigts.
# On tient donc un journal : quel onglet sert, a quelle voie, et quand.
JOURNAL = os.path.expanduser("~/.rasora/state/onglets-actifs.json")


def journal_lire():
    try:
        return json.load(open(JOURNAL, encoding="utf-8"))
    except Exception:
        return {}


def journal_ecrire(d):
    try:
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        tmp = JOURNAL + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        os.replace(tmp, JOURNAL)        # atomique : plusieurs sessions ecrivent
    except Exception:
        pass


def toucher(tid, url="", voie=None, vivants=None):
    """Dit au ramasse-miettes que cet onglet SERT, meme sans navigation."""
    d = journal_lire()
    e = d.get(tid, {})
    e["vu"] = int(time.time())
    if url:
        e["url"] = url[:200]
    if voie:
        e["voie"] = voie
    d[tid] = e
    if vivants is not None:             # on oublie les onglets fermes
        d = {k: v for k, v in d.items() if k in vivants}
    journal_ecrire(d)


def purger(vivants):
    """Oublie les onglets fermes, sans rien toucher d'autre."""
    d = journal_lire()
    n = {k: v for k, v in d.items() if k in vivants}
    if len(n) != len(d):
        journal_ecrire(n)


def court(tid):
    return "#" + tid[:6].lower()


def trouver(motif=""):
    """L'onglet vise. Trois facons de le designer, de la plus sure a la plus souple :

      #a1b2c3   son identifiant court, celui qu'affiche `nav.py onglets`
      @shopify  la voie a laquelle il a ete reserve (`nav.py reserver`)
      shopify   un bout d'URL ; a egalite, le plus recemment utilise gagne
    """
    ts = onglets()
    if not ts:
        sys.exit("no open tab, run: (~/.rasora/bin/navigateur-bot.sh)")
    if not motif:
        return ts[0]

    if motif.startswith("#"):
        c = [t for t in ts if t["id"].lower().startswith(motif[1:].lower())]
        if not c:
            sys.exit(f"no tab {motif}. Open tabs:\n" + _liste_courte(ts))
        return c[0]

    if motif.startswith("@"):
        voie = motif[1:].lower()
        j = journal_lire()
        for t in ts:
            if (j.get(t["id"], {}).get("voie") or "").lower() == voie:
                return t
        sys.exit(f"no tab reserved for lane '{voie}'. "
                 f"La reserver : nav.py reserver <motif-url> {voie}\n" + _liste_courte(ts))

    c = [t for t in ts if motif.lower() in t.get("url", "").lower()]
    if not c:
        sys.exit(f"no tab contains '{motif}'. Open tabs:\n" + _liste_courte(ts))
    if len(c) > 1:
        # A egalite on prend celui dont on s'est servi en dernier, pas le premier
        # de la liste : /json/list est ordonne par activite du navigateur, donc il
        # designait tantot l'un tantot l'autre et on croyait le correctif casse.
        j = journal_lire()
        c.sort(key=lambda t: j.get(t["id"], {}).get("vu", 0), reverse=True)
        voie = j.get(c[0]["id"], {}).get("voie")
        print(f"NOTE {len(c)} tabs match '{motif}', using {court(c[0]['id'])}"
              + (f" (voie {voie})" if voie else " (le plus recemment utilise)")
              + ". Viser sans ambiguite : " + court(c[0]["id"]), file=sys.stderr)
    return c[0]


def _liste_courte(ts):
    j = journal_lire()
    out = []
    for t in ts:
        v = j.get(t["id"], {}).get("voie")
        out.append("  %s %s %s" % (court(t["id"]), ("@" + v).ljust(12) if v else " " * 12,
                                   (t.get("url") or "")[:100]))
    return "\n".join(out)


# ------------------------------------------------------------ sessions de site
# Une page de connexion se reconnait a son CHEMIN (/login, /signin...) ou a son
# HOTE (accounts.shopify.com, auth.runwayml.com). Mesure du 24/08/2026 : le chemin
# seul laissait passer `accounts.shopify.com/store-login`, donc la session Shopify
# tombee ne se reparait pas et remontait jusqu'a l utilisateur.
CONNEXION = re.compile(
    r"(^|/)(login|log-in|store-login|signin|sign-in|sign_in|auth|authenticate|"
    r"interaction|logout|sessions/new|users/sign_in)\b", re.I)
HOTE_CONNEXION = re.compile(r"^(accounts?|auth|authenticate|login|signin|id)\.", re.I)


def echec_chargement(o):
    """Vrai si l'onglet affiche une page d'erreur de Chrome.

    Mesure du 24/08/2026 : `ouvrir` a rendu « PRET en 2.4s » sur un
    `chrome-error://chromewebdata/` (echec reseau). La session suivante cherche
    alors des boutons sur une page qui n'existe pas, et conclut que le site a
    change. Une navigation ratee doit se dire, tout de suite.
    """
    try:
        return str(o.js("location.href") or "").startswith("chrome-error://")
    except Exception:
        return False


def page_de_connexion(url):
    u = urllib.parse.urlparse(url or "")
    return bool(CONNEXION.search(u.path or "") or HOTE_CONNEXION.match(u.netloc or ""))
TABLE_SESSIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.json")


def site_connu(url):
    """Le nom de session (sessions.json) qui couvre cette URL, s'il existe."""
    try:
        table = json.load(open(TABLE_SESSIONS, encoding="utf-8"))
    except Exception:
        return None
    hote = urllib.parse.urlparse(url or "").netloc.lower()
    if not hote:
        return None
    for nom, conf in table.items():
        for d in conf.get("domaines", []):
            d = d.lstrip("*.").lower()
            if hote == d or hote.endswith("." + d):
                return nom
    return None


def soigner(url):
    """On a sign-in page: tell the agent to ask the user to sign in. Always returns None."""
    if not page_de_connexion(url):
        return None
    nom = site_connu(url) or url
    print(f"SESSION {nom} SIGNED OUT. If the fields are already filled in, click the sign-in "
          f"button. Otherwise ask the user, then run: rasora login {url[:80]}")
    return None


class Onglet:
    def __init__(self, t, premier_plan=True):
        self.t = t
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"],
                                              timeout=90, suppress_origin=True)
        self.i = 0
        self.evts = []          # evenements CDP recus pendant qu'on attendait une reponse
        if premier_plan and "/page/" in (t.get("webSocketDebuggerUrl") or ""):
            self.au_premier_plan()

    def au_premier_plan(self):
        """Fait croire a la page qu'elle est visible et focalisee, sans toucher a
        la fenetre. C'est LE remplacant de `Page.bringToFront`.

        Mesure du 24/08/2026 sur un onglet du navigateur bot, fenetre hors ecran :
        `document.visibilityState` valait 'hidden' et `document.hasFocus()` false.
        Une page cachee met ses minuteurs en veille, ne charge pas ce qui est
        differe et ne positionne pas ce qui est anime : les clics tombaient a
        cote et les lectures rendaient une page a moitie vide. D'ou le reflexe
        `bringToFront` d'avant, qui ramenait la fenetre DEVANT L'ECRAN DE L'UTILISATEUR.
        Ces deux commandes donnent le meme resultat sans rien deplacer :
        visibilityState repasse a 'visible', hasFocus a true, la fenetre ne bouge pas.
        """
        try:
            self.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
            self.call("Page.setWebLifecycleState", {"state": "active"})
        except Exception:
            pass

    def call(self, m, p=None, timeout=None):
        self.i += 1
        n = self.i
        if timeout:
            self.ws.settimeout(timeout)
        self.ws.send(json.dumps({"id": n, "method": m, "params": p or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == n:
                if timeout:
                    self.ws.settimeout(90)
                if "error" in r:
                    return {"_erreur": r["error"]}
                return r.get("result", {})
            if "method" in r:
                self.evts.append(r)

    def frames(self):
        """Liste des cadres de la page : le document principal puis les iframes.

        Chaque entree porte l'offset de l'iframe dans la page, indispensable pour
        cliquer : a l'interieur d'un cadre les coordonnees repartent de zero, alors
        que l'evenement souris, lui, s'envoie dans le repere de la fenetre.
        """
        self.call("Page.enable")
        arbre = self.call("Page.getFrameTree").get("frameTree", {})
        out = [{"id": arbre.get("frame", {}).get("id"),
                "url": arbre.get("frame", {}).get("url", ""), "dx": 0, "dy": 0}]
        for enfant in arbre.get("childFrames", []) or []:
            f = enfant.get("frame", {})
            out.append({"id": f.get("id"), "url": f.get("url", ""), "dx": 0, "dy": 0})
        # Les iframes d'un AUTRE domaine (Stripe, un captcha) tournent dans un
        # processus separe : elles n'apparaissent pas dans le frameTree de la page,
        # mais comme des cibles a part entiere, avec leur propre websocket.
        for t in json.load(urllib.request.urlopen(f"{BASE}/json/list")):
            if t.get("type") == "iframe" and t.get("webSocketDebuggerUrl"):
                out.append({"id": t["id"], "url": t.get("url", ""), "dx": 0, "dy": 0,
                            "ws": t["webSocketDebuggerUrl"]})
        # offsets, lus depuis le document principal
        rects = self.js("[...document.querySelectorAll('iframe')].map(f=>{"
                        "const r=f.getBoundingClientRect();"
                        "return [f.src||'', r.left, r.top]})") or []
        for c in out[1:]:
            for src, x, y in rects:
                if src and (src == c["url"] or src.rstrip('/') == c["url"].rstrip('/')):
                    c["dx"], c["dy"] = x, y
                    break
            else:
                i = out.index(c) - 1
                if i < len(rects):
                    c["dx"], c["dy"] = rects[i][1], rects[i][2]
        return out

    def contexte(self, frame_id):
        """Un monde isole dans le cadre vise : donne acces a son DOM, meme
        quand le cadre vient d'un autre domaine (Stripe, un captcha, un widget)."""
        r = self.call("Page.createIsolatedWorld",
                      {"frameId": frame_id, "grantUniveralAccess": True})
        return r.get("executionContextId")

    def js(self, expr, ctx=None):
        p = {"expression": expr, "returnByValue": True, "awaitPromise": True}
        if ctx:
            p["contextId"] = ctx
        r = self.call("Runtime.evaluate", p)
        if r.get("_erreur"):
            return "ERREUR " + json.dumps(r["_erreur"])[:200]
        if r.get("exceptionDetails"):
            return "ERREUR JS " + json.dumps(r["exceptionDetails"])[:250]
        return r.get("result", {}).get("value")

    def ecouter(self, secondes):
        """Collecte les evenements CDP pendant N secondes, sans rien envoyer."""
        fin = time.time() + secondes
        self.ws.settimeout(0.4)
        try:
            while time.time() < fin:
                try:
                    r = json.loads(self.ws.recv())
                except websocket.WebSocketTimeoutException:
                    continue
                if "method" in r:
                    self.evts.append(r)
        finally:
            self.ws.settimeout(90)

    def pret(self, timeout=15, plancher=0.0):
        """Attend que la page soit reellement utilisable.

        readyState='complete' seul ne suffit pas : un onglet neuf est 'complete'
        sur son document vide AVANT que la navigation commence, et on repartait
        avec un titre vide. On exige donc aussi un <body> non vide.
        `plancher` = duree minimale, pour laisser une navigation demarrer apres
        un clic (l'ancienne page est encore 'complete' pendant un instant).
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            r = self.js("({e:document.readyState,n:document.body?"
                        "(document.body.innerText||document.body.textContent||'')"
                        ".trim().length:0})")
            ecoule = time.time() - t0
            # Le seuil de contenu evite de repartir sur un document vide ; mais une
            # page qui se vide legitimement (une popup de connexion qui se referme)
            # ne doit pas nous faire attendre le timeout entier.
            assez = r.get("n", 0) > 30 if isinstance(r, dict) else False
            if (isinstance(r, dict) and r.get("e") == "complete"
                    and (assez or ecoule > 2) and ecoule >= plancher):
                time.sleep(0.15)          # laisse le rendu se poser
                return round(time.time() - t0, 1)
            time.sleep(0.1)
        return round(time.time() - t0, 1)


# ---------------------------------------------------------------- JS injecte

# Briques communes : visibilite et libelle d'un element.
JS_UTILS = r"""
  const norm = s => (s||'').replace(/\s+/g,' ').trim();
  const vis = e => {
    const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    const st = getComputedStyle(e);
    return st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
  };
  // innerText d'abord (il respecte ce qui est visible), textContent en repli :
  // hors ecran, Chrome ne calcule pas toujours le rendu des applications tres
  // dynamiques et innerText revient VIDE. Sur Gmail, plus rien n'etait cliquable.
  const nom = e => norm(e.innerText) || norm(e.textContent) || norm(e.value) ||
      norm(e.getAttribute('aria-label')) || norm(e.getAttribute('title')) ||
      norm(e.getAttribute('alt')) ||
      norm((e.querySelector('img,svg') || {}).getAttribute
           ? e.querySelector('img,svg').getAttribute('alt') : '');
"""

# Cliquer sur du texte visible. On remonte au plus petit element cliquable
# qui contient le texte, on le fait defiler dans la vue, puis on envoie un vrai
# clic souris aux coordonnees de son centre : un .click() JS est ignore par
# beaucoup de sites (Alibaba, Shopify), un evenement souris ne l'est pas.
JS_CIBLE = r"""
(() => {
  const cible = %s, rang = %s;
""" + JS_UTILS + r"""
  const bas = s => norm(s).toLowerCase();
  const veut = bas(cible);
  const sel = 'button,a,[role=button],[role=link],[role=tab],input[type=submit],input[type=button],div[class*=btn],div[class*=button],span[class*=btn],label';
  let els = [...document.querySelectorAll(sel)].filter(e => vis(e) && bas(nom(e)).includes(veut) && nom(e));
  if (!els.length) return {ok:false, vus:[...document.querySelectorAll(sel)]
      .filter(vis).map(nom).filter(Boolean).slice(0,25)};
  els.sort((a,b) => (a.getBoundingClientRect().width*a.getBoundingClientRect().height)
                  - (b.getBoundingClientRect().width*b.getBoundingClientRect().height));
  if (rang >= els.length) return {ok:false, epuise:true, total:els.length};
  const e = els[rang];
  // On MARQUE la cible et on lance le defilement, sans lire les coordonnees ici :
  // sur un site a smooth scroll (Lenis, scroll-behavior:smooth) le defilement est
  // anime, donc un rect lu maintenant est faux et on cliquerait dans le vide.
  document.querySelectorAll('[data-nav-cible]').forEach(x=>x.removeAttribute('data-nav-cible'));
  e.setAttribute('data-nav-cible','1');
  e.scrollIntoView({block:'center', behavior:'instant'});
  return {ok:true, texte:nom(e).slice(0,60), total:els.length};
})()
"""

# Lu APRES stabilisation du defilement : coordonnees reelles au moment du clic.
JS_CIBLE_RECT = r"""
(() => {
  const e = document.querySelector('[data-nav-cible]');
  if (!e) return {ok:false};
  const r = e.getBoundingClientRect();
  e.removeAttribute('data-nav-cible');
  e.setAttribute('data-nav-replie','1');   // retrouver la cible si le clic reste sans effet
  const dansVue = r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth;
  // Qui recevra reellement le clic a cet endroit ? Un bandeau cookies, une modale
  // ou un calque invisible s'intercalent souvent : le clic part, rien ne se passe,
  // et sans cette verification l'echec est silencieux.
  let recoit = null, intercepte = false;
  if (dansVue) {
    const au = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
    if (au) {
      recoit = au.tagName.toLowerCase() + (au.className ?
               '.' + (au.className||'').toString().split(' ')[0] : '');
      intercepte = !(au === e || e.contains(au) || au.contains(e));
    }
  }
  // x/y = repere de la VUE, pour l'evenement souris.
  // gauche/haut = repere du DOCUMENT, pour le clip de Page.captureScreenshot.
  return {ok:true, x:r.left + r.width/2, y:r.top + r.height/2,
          gauche:r.left + scrollX, haut:r.top + scrollY,
          w:r.width, h:r.height, dansVue, recoit, intercepte};
})()
"""

# L'inventaire : ce que Claude in Chrome donne via un snapshot d'accessibilite,
# mais en texte compact. Les boutons en icone (croix, panier) remontent par
# aria-label / title / alt, que le clic par texte seul ratait completement.
JS_ELEMENTS = r"""
(() => {
""" + JS_UTILS + r"""
  const court = s => s.length > 55 ? s.slice(0,55) + '…' : s;
  const uniq = arr => {
    const vus = new Set(), out = [];
    for (const x of arr) { if (!vus.has(x)) { vus.add(x); out.push(x); } }
    return out;
  };
  const marque = e => norm(e.innerText) ? '' : ' [icone]';

  const boutons = uniq([...document.querySelectorAll(
      'button,[role=button],input[type=submit],input[type=button],div[class*=btn],div[class*=button]')]
      .filter(e => vis(e) && nom(e)).map(e => court(nom(e)) + marque(e))).slice(0,40);

  const liens = uniq([...document.querySelectorAll('a[href]')]
      .filter(e => vis(e) && nom(e))
      .map(e => {
        let h = e.getAttribute('href') || '';
        try { h = new URL(e.href).pathname + new URL(e.href).search; } catch(_) {}
        return court(nom(e)) + ' (' + court(h) + ')';
      })).slice(0,40);

  const champs = [...document.querySelectorAll('input,textarea')]
      .filter(e => vis(e) && !['submit','button','hidden'].includes(e.type))
      .map(e => (e.placeholder || e.name || e.id ||
                 e.getAttribute('aria-label') ||
                 (e.labels && e.labels[0] ? norm(e.labels[0].innerText) : '') || '?')
                + ' [' + (e.type || 'text') + ']').slice(0,25);

  const menus = [...document.querySelectorAll('select')].filter(vis).map(e =>
      (e.name || e.id || e.getAttribute('aria-label') || '?') + ' : ' +
      [...e.options].map(o => norm(o.text)).slice(0,8).join(' | '));

  const cadres = [...document.querySelectorAll('iframe')].filter(vis)
      .map(f => { try { return new URL(f.src).host; } catch(_) { return '(sans src)'; } });

  return {boutons, liens, champs, menus, cadres:uniq(cadres).slice(0,6)};
})()
"""

JS_CHAMP = r"""
(() => {
  const cible = %s, valeur = %s;
  const norm = s => (s||'').replace(/\s+/g,' ').trim().toLowerCase();
  const veut = norm(cible);
  const champs = [...document.querySelectorAll('input,textarea')].filter(e=>{
    const r = e.getBoundingClientRect();
    return r.width>4 && r.height>4;
  });
  let e = champs.find(c => [c.placeholder, c.name, c.id, c.getAttribute('aria-label'),
      (c.labels && c.labels[0] && c.labels[0].innerText)].some(v => norm(v).includes(veut)));
  if (!e) return {ok:false, vus:champs.map(c=>c.placeholder||c.name||c.id).filter(Boolean).slice(0,20)};
  e.scrollIntoView({block:'center', behavior:'instant'});
  e.focus();
  const set = Object.getOwnPropertyDescriptor(
      e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;
  set.call(e, valeur);
  e.dispatchEvent(new Event('input',{bubbles:true}));
  e.dispatchEvent(new Event('change',{bubbles:true}));
  return {ok:true, champ:(e.placeholder||e.name||e.id||'').slice(0,50)};
})()
"""

JS_MENU = r"""
(() => {
  const cible = %s, valeur = %s;
  const norm = s => (s||'').replace(/\s+/g,' ').trim().toLowerCase();
  const sels = [...document.querySelectorAll('select')];
  const e = sels.find(s => [s.name, s.id, s.getAttribute('aria-label'),
      (s.labels && s.labels[0] && s.labels[0].innerText)].some(v => norm(v).includes(norm(cible))))
      || (sels.length === 1 ? sels[0] : null);
  if (!e) return {ok:false, vus:sels.map(s => s.name||s.id||'?')};
  const o = [...e.options].find(o => norm(o.text).includes(norm(valeur))
                                  || norm(o.value).includes(norm(valeur)));
  if (!o) return {ok:false, options:[...e.options].map(o=>o.text.trim()).slice(0,20)};
  e.value = o.value;
  e.dispatchEvent(new Event('input',{bubbles:true}));
  e.dispatchEvent(new Event('change',{bubbles:true}));
  return {ok:true, menu:(e.name||e.id||'?'), choisi:o.text.trim()};
})()
"""

JS_CONNECTE = r"""
(() => {
  const t = document.body.innerText;
  const dehors = /(sign in|se connecter|log in|connectez-vous|inscription)/i.test(t.slice(0,3000));
  const dedans = /(mon compte|my account|se deconnecter|sign out|log out|deconnexion|messages)/i.test(t);
  return {dedans, dehors};
})()
"""

# Cadrage d'une capture : on MARQUE l'element et on l'amene dans la vue.
# Les coordonnees sont relues apres coup par JS_CIBLE_RECT, une fois le
# defilement stabilise. On ne calcule pas "rect + scrollY" : sur un site qui
# defile un conteneur interne, scrollY vaut 0 et le clip tombait hors du
# document, ce qui rendait une image blanche.
JS_RECT = r"""
(() => {
  const cible = %s, rang = %s;
""" + JS_UTILS + r"""
  const bas = s => norm(s).toLowerCase();
  // On ecarte la navigation : un sommaire ou un menu reprend les memes libelles
  // que les sections, et on cadrait le lien du menu au lieu de la section visee.
  const els = [...document.querySelectorAll('*')].filter(e => vis(e)
      && bas(nom(e)).includes(bas(cible))
      && !e.closest('nav,aside,[role=navigation]'));
  if (!els.length || rang >= els.length) return {ok:false};
  els.sort((a,b) => (a.getBoundingClientRect().width*a.getBoundingClientRect().height)
                  - (b.getBoundingClientRect().width*b.getBoundingClientRect().height));
  const e = els[rang];
  document.querySelectorAll('[data-nav-cible]').forEach(x=>x.removeAttribute('data-nav-cible'));
  e.setAttribute('data-nav-cible','1');
  e.scrollIntoView({block:'center', behavior:'instant'});
  return {ok:true, total:els.length,
          quoi:e.tagName.toLowerCase() + (e.className ? '.' + (e.className||'').toString().split(' ')[0] : '')};
})()
"""


def stabiliser_cible(o, timeout=2.0, ctx=None):
    """Attend que la cible marquee ne bouge plus, puis rend son rect.

    On surveille la CIBLE et pas `scrollY` : le site client ne defile pas la
    fenetre mais un `div.page-wrapper` interne, donc scrollY vaut 0 en
    permanence et ne dit rien. Le rect de l'element, lui, bouge dans tous les
    cas (fenetre, conteneur interne, Lenis en transform).
    """
    t0 = time.time()
    dernier, stables = None, 0
    while time.time() - t0 < timeout:
        r = o.js("(()=>{const e=document.querySelector('[data-nav-cible]');if(!e)return null;"
                 "const r=e.getBoundingClientRect();"
                 "return [Math.round(r.left),Math.round(r.top)]})()", ctx)
        if r is None:
            return
        if r == dernier:
            stables += 1
            if stables >= 2:
                break
        else:
            stables = 0
        dernier = r
        time.sleep(0.06)
    time.sleep(0.06)


def clic_souris(o, x, y):
    """Vrai clic souris. `buttons` est indispensable : c'est le bitmask des
    boutons enfonces, et sans lui les frameworks qui ecoutent pointerdown /
    pointerup ignorent l'evenement en silence. Le thema de le site client etait
    dans ce cas : le clic tombait au bon endroit et il ne se passait rien."""
    o.call("Input.dispatchMouseEvent",
           {"type": "mouseMoved", "x": x, "y": y, "buttons": 0})
    time.sleep(0.04)
    o.call("Input.dispatchMouseEvent",
           {"type": "mousePressed", "x": x, "y": y,
            "button": "left", "buttons": 1, "clickCount": 1})
    time.sleep(0.03)
    o.call("Input.dispatchMouseEvent",
           {"type": "mouseReleased", "x": x, "y": y,
            "button": "left", "buttons": 0, "clickCount": 1})
    time.sleep(0.03)


OPTIONS_A_VALEUR = ("--cadre", "--sur", "--rang", "--voie")
OPTIONS_SEULES = ("--recharger",)


def positionnels(args):
    """Retire les options, pour que les arguments gardent leur place.

    Sans ca, `champ x --cadre 1 "Numero" "4242"` faisait lire "--cadre" comme
    nom de champ et "1" comme valeur : la commande echouait sans rien dire de
    clair. Les options restent lisibles a part, dans la liste brute.
    """
    pos, i = [], 0
    while i < len(args):
        if args[i] in OPTIONS_A_VALEUR:
            i += 2
        elif args[i] in OPTIONS_SEULES:
            i += 1
        else:
            pos.append(args[i])
            i += 1
    return pos


def choisir_cadre(o, args):
    """Rend (onglet_ou_executer_le_js, contextId, dx, dy) pour l'option --cadre.

    `--cadre 1` vise par index (celui qu'affiche `cadres`), `--cadre stripe`
    vise par un bout d'URL. Deux cas :
      - iframe du meme domaine : on reste sur la page et on ouvre un monde isole ;
      - iframe d'un autre domaine : elle a sa propre cible, on s'y connecte.
    Dans les deux cas le CLIC SOURIS reste envoye a la page principale, avec
    l'offset de l'iframe : c'est la fenetre qui recoit les evenements souris.
    """
    if "--cadre" not in args:
        return o, None, 0, 0
    quoi = args[args.index("--cadre") + 1]
    fs = o.frames()
    if quoi.isdigit():
        i = int(quoi)
        if i >= len(fs):
            sys.exit(f"frame {i} not found ({len(fs) - 1} iframe(s))")
        c = fs[i]
    else:
        c = next((f for f in fs[1:] if quoi.lower() in (f["url"] or "").lower()), None)
        if not c:
            sys.exit("no frame contains '%s'. Seen:\n%s" %
                     (quoi, "\n".join("  %d %s" % (n, f["url"][:90])
                                      for n, f in enumerate(fs))))
    if c.get("ws"):
        return Onglet({"webSocketDebuggerUrl": c["ws"]}), None, c["dx"], c["dy"]
    ctx = o.contexte(c["id"])
    if not ctx:
        sys.exit("frame not reachable")
    return o, ctx, c["dx"], c["dy"]


def bloc(titre, lignes):
    if not lignes:
        return
    print(f"{titre} ({len(lignes)})")
    for l in lignes:
        print("  " + l)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    # English command names. The French ones keep working.
    ALIAS = {"open": "ouvrir", "status": "etat", "read": "lire", "wait": "attendre",
             "click": "clic", "fill": "champ", "select": "menu", "press": "touche",
             "tabs": "onglets", "reserve": "reserver", "screenshot": "photo",
             "frames": "cadres", "hide": "discret", "show": "montrer", "close": "fermer"}
    sys.argv[1] = ALIAS.get(sys.argv[1], sys.argv[1])
    cmd = sys.argv[1]
    brut = sys.argv[2:]          # options comprises
    a = positionnels(brut)      # arguments a leur place, options retirees

    if cmd == "google":
        # Quel compte Google porte le profil du bot. La session vit dans
        # ~/.rasora/chrome-profile : une fois connectee, elle tient, et tout site qui
        # propose « Continuer avec Google » se connecte sans mot de passe.
        tid = navigateur().call("Target.createTarget", {
            "url": "https://myaccount.google.com/", "background": True}).get("targetId")
        time.sleep(0.6)
        ong = [x for x in onglets() if x["id"] == tid][0]
        o = Onglet(ong)
        o.pret(20)
        txt = o.js("document.body.innerText") or ""
        mails = []
        for m in __import__("re").findall(r"[\w.%+-]+@[\w.-]+\.\w+", txt):
            if m not in mails:
                mails.append(m)
        connecte = "connexion" not in (o.js("location.href") or "").lower()
        print("ACCOUNT:", ", ".join(mails) if mails else "(no email found)")
        print("STATE  :", "signed in" if connecte and mails else "NOT signed in")
        if not (connecte and mails):
            print("Pour connecter : nav.py montrer, l utilisateur se connecte a la main,\n"
                  "puis nav.py discret. La session tient ensuite dans ~/.rasora/chrome-profile.")
        urllib.request.urlopen(f"{BASE}/json/close/{tid}").read()
        return

    if cmd == "eteindre":
        # Empty tabs first: nothing to reload at the next start, only the sign-ins remain.
        o = navigateur()
        ts = onglets()
        for t in ts[1:]:
            o.call("Target.closeTarget", {"targetId": t["id"]})
        if ts:
            Onglet(ts[0]).call("Page.navigate", {"url": "about:blank"})
            time.sleep(.3)
        o.call("Browser.close")
        return

    if cmd == "onglets":
        ts = onglets()
        j = journal_lire()
        for t in ts:
            e = j.get(t["id"], {})
            voie = ("@" + e["voie"]) if e.get("voie") else ""
            age = ""
            if e.get("vu"):
                age = f"{int((time.time() - e['vu']) / 60)}min"
            print(f"{court(t['id'])} {voie:12} {age:>6}  "
                  f"{t.get('title','')[:38]:40} {t.get('url','')[:90]}")
        purger({x["id"] for x in ts})
        return

    if cmd == "reserver":
        # « cet onglet est a cette voie » : plus d'ambiguite entre sessions, et le
        # ramasse-miettes ne le fermera plus jamais.
        t = trouver(a[0])
        voie = a[1]
        toucher(t["id"], t.get("url", ""), voie=voie,
                vivants={x["id"] for x in onglets()})
        print(f"{court(t['id'])} reserved for lane @{voie}  {t.get('url','')[:90]}")
        print(f"Commands can now target @{voie} instead of part of a URL.")
        return

    if cmd == "ouvrir":
        url = a[0]
        timeout = int(a[1]) if len(a) > 1 else 15
        # `background: True` : l'onglet s'ouvre SANS ramener la fenetre devant.
        # L'ancien appel HTTP /json/new restaurait et repositionnait la fenetre a
        # chaque ouverture, ce qui faisait surgir le navigateur bot par-dessus
        # l'ecran de l'utilisateur. On garde /json/new en repli.
        tid = None
        try:
            tid = navigateur().call(
                "Target.createTarget", {"url": url, "background": True}).get("targetId")
        except Exception:
            pass
        if not tid:
            req = urllib.request.Request(
                f"{BASE}/json/new?" + urllib.parse.quote(url, safe=':/?=&%#'), method="PUT")
            tid = json.load(urllib.request.urlopen(req))["id"]
        # On attend que la cible EXISTE, au lieu de dormir 0,6 s a l'aveugle :
        # elle apparait en general en moins de 100 ms.
        t = None
        t0 = time.time()
        while time.time() - t0 < 5:
            t = next((x for x in onglets() if x["id"] == tid), None)
            if t:
                break
            time.sleep(0.05)
        if not t:
            sys.exit("the tab did not open")
        o = Onglet(t)
        att = o.pret(timeout)
        if echec_chargement(o):
            o.call("Page.navigate", {"url": url})     # un seul nouvel essai
            att = o.pret(timeout)
            if echec_chargement(o):
                # on ne laisse pas trainer un onglet d'erreur : le prochain
                # `nav.py lire <motif>` tomberait dessus
                try:
                    urllib.request.urlopen(f"{BASE}/json/close/{tid}").read()
                except Exception:
                    pass
                print(f"LOAD FAILED after 2 tries: {url}")
                print("The page does not exist, the network dropped, or the site refused us. "
                      "Onglet referme.")
                sys.exit(1)
        t = next(x for x in onglets() if x["id"] == tid)
        url_finale = t.get("url", "")
        # Une session tombee ne doit plus remonter jusqu'a l utilisateur : on regreffe
        # et on rouvre la meme page une fois.
        if soigner(url_finale):
            o.call("Page.navigate", {"url": url})
            att = o.pret(timeout)
            t = next(x for x in onglets() if x["id"] == tid)
            url_finale = t.get("url", "")
            print("SESSION REPAIRED" if not page_de_connexion(url_finale) else
                  "STILL SIGNED OUT: run `rasora show` and sign in by hand a la "
                  "main, puis nav.py discret")
        voie = brut[brut.index("--voie") + 1] if "--voie" in brut else None
        toucher(tid, url_finale, voie=voie, vivants={x["id"] for x in onglets()})
        print("URL:", url_finale[:130])
        print("TITLE:", t.get("title", "")[:100])
        n = rester_discret()
        print(f"READY in {att}s  {court(tid)}" + (f" @{voie}" if voie else "")
              + ("  (fenetre repoussee hors ecran)" if n else ""))
        return

    motif = a[0] if a else ""
    t = trouver(motif)
    toucher(t["id"], t.get("url", ""))
    o = Onglet(t)
    oc, ctx, dx, dy = choisir_cadre(o, brut)   # oc = la ou on lit le DOM

    if cmd == "etat":
        print("URL:", t.get("url", "")[:130])
        print("TITLE:", t.get("title", "")[:100])
        print("SESSION:", json.dumps(o.js(JS_CONNECTE)))
        # `etat` est la commande de diagnostic : si la page est un ecran de
        # connexion d'un site connu, on repare au lieu de le signaler a l utilisateur.
        url = o.js("location.href") or t.get("url", "")
        if soigner(url):
            o.call("Page.reload")
            o.pret(20)
            neuve = o.js("location.href") or ""
            print("URL AFTER REPAIR:", neuve[:130])
            if page_de_connexion(neuve):
                print("STILL SIGNED OUT: run `rasora show` and sign in by hand "
                      "a la main, puis nav.py discret")

    elif cmd == "lire":
        n = int(a[1]) if len(a) > 1 else 4000
        if echec_chargement(o):
            sys.exit("PAGE ERROR (chrome-error): navigation failed, "
                     "rien a lire. Refaire `nav.py ouvrir`.")
        print((oc.js("document.body.innerText || document.body.textContent", ctx)
               or "")[:n])

    elif cmd == "elements":
        r = oc.js(JS_ELEMENTS, ctx)
        if not isinstance(r, dict):
            sys.exit(str(r)[:400])
        bloc("BOUTONS", r["boutons"])
        bloc("LIENS", r["liens"])
        bloc("CHAMPS", r["champs"])
        bloc("MENUS", r["menus"])
        bloc("IFRAMES", r["cadres"])
        if not any(r.values()):
            print("PAGE ERROR (chrome-error): navigation failed"
                  if echec_chargement(o) else
                  "aucun element interactif visible (page vide, ou tout est en iframe)")

    elif cmd == "attendre":
        texte, timeout = a[1], (int(a[2]) if len(a) > 2 else 20)
        t0 = time.time()
        while time.time() - t0 < timeout:
            corps = oc.js("document.body.innerText || document.body.textContent",
                          ctx) or ""
            if texte.lower() in corps.lower():
                print(f"SEEN '{texte}' after {round(time.time()-t0,1)}s")
                print("URL:", o.js("location.href")[:130])
                return
            time.sleep(0.3)
        print(f"PAS SEEN '{texte}' after {timeout}s")
        print("URL:", o.js("location.href")[:130])
        sys.exit(1)

    elif cmd == "clic":
        # Plusieurs elements peuvent porter le meme libelle. On prend le plus
        # petit, mais s'il reste hors de la vue apres defilement on passe au
        # suivant : sur une fiche produit Shopify, le premier « Ajouter au
        # panier » est celui de la barre sticky, masquee hors ecran par design.
        r = pos = None
        # Borne de temps : sur un theme anime (GSAP), chaque candidat coute
        # jusqu'a 3 s de stabilisation et il y en a 8 : on passait une demi-minute
        # a chercher un bouton deja trouve au premier essai. On garde le meilleur
        # candidat vu quand la borne tombe.
        fin_recherche = time.time() + 6
        for rang in range(8):
            if rang and time.time() > fin_recherche:
                print(f"NOTE search capped at 6 s, clicking candidate {rang - 1}")
                break
            r = oc.js(JS_CIBLE % (json.dumps(a[1]), rang), ctx)
            if not isinstance(r, dict) or not r.get("ok"):
                if rang == 0:
                    print("NOT FOUND.", json.dumps(r, ensure_ascii=False)[:600])
                    sys.exit(1)
                break
            stabiliser_cible(oc, ctx=ctx)
            p = oc.js(JS_CIBLE_RECT, ctx)
            if isinstance(p, dict) and p.get("ok"):
                pos = p
                if p["dansVue"]:
                    break
        if pos is None:
            sys.exit("target lost after scrolling")
        if not pos["dansVue"]:
            print("WARNING target out of view after scrolling, click uncertain")
        if pos.get("intercepte"):
            print(f"WARNING <{pos.get('recoit')}> covers the target: the click will land"
                  " dessus. Fermer le bandeau/la modale d'abord.")
        avant_url = oc.js("location.href", ctx)
        clic_souris(o, pos["x"] + dx, pos["y"] + dy)
        # au lieu d'un sleep(3) aveugle. Plancher 0.8s : si le clic navigue,
        # l'ancienne page est encore 'complete' pendant un court instant.
        att = o.pret(8, plancher=0.8)
        # Repli mesure le 16/08/2026 : sur un lien <a> ordinaire, l'evenement
        # souris arrive au bon endroit (elementFromPoint le confirme) sans
        # declencher la navigation native. Verifie sur une page SANS aucun JS,
        # fenetre visible comme hors ecran : ce n'est ni un overlay, ni le site,
        # ni le mode discret. On tente donc un vrai clic d'abord, fidele a ce que
        # ferait un humain, puis on retombe sur .click() si rien n'a bouge.
        replie = ""
        # On ne compare QUE l'URL : sur un site vivant, la taille du DOM bouge
        # en permanence (animations, minuteurs), donc la comparer empechait le
        # repli de se declencher.
        if oc.js("location.href", ctx) == avant_url:
            bouge = oc.js("(()=>{const e=document.querySelector('[data-nav-replie]');"
                          "if(!e)return false;e.removeAttribute('data-nav-replie');"
                          "e.click();return true})()", ctx)
            if bouge:
                att = o.pret(8, plancher=0.5)
                replie = " (repli .click())"
        rester_discret(o)   # une popup de connexion nait au milieu de l'ecran
        print(f"CLICK on '{r['texte']}' | ready in {att}s{replie}")
        apres = o.js("location.href") or ""
        print("URL:", apres[:130])
        # On ne regreffe pas au milieu d'un enchainement (on perdrait le formulaire
        # en cours), mais on nomme la panne et sa reparation en une ligne.
        if page_de_connexion(apres) and site_connu(apres):
            print(f"SESSION {site_connu(apres)} DOWN: "
                  f"rasora login {site_connu(apres)}, then click again")

    elif cmd == "champ":
        print(json.dumps(oc.js(JS_CHAMP % (json.dumps(a[1]), json.dumps(a[2])), ctx),
                         ensure_ascii=False)[:400])

    elif cmd == "menu":
        print(json.dumps(oc.js(JS_MENU % (json.dumps(a[1]), json.dumps(a[2])), ctx),
                         ensure_ascii=False)[:400])

    elif cmd == "touche":
        k = a[1]
        code = {"Enter": 13, "Escape": 27, "Tab": 9}.get(k, 13)
        for ty in ("keyDown", "keyUp"):
            o.call("Input.dispatchKeyEvent", {"type": ty, "key": k, "code": k,
                                              "windowsVirtualKeyCode": code,
                                              "nativeVirtualKeyCode": code})
        att = o.pret(8)
        rester_discret(o)
        print("KEY", k, f"| ready in {att}s | URL:", o.js("location.href")[:120])

    elif cmd == "js":
        print(json.dumps(oc.js(a[1], ctx), ensure_ascii=False)[:4000])

    elif cmd == "console":
        secondes = 6
        for x in a[1:]:
            if x.isdigit():
                secondes = int(x)
        o.call("Runtime.enable")
        o.call("Log.enable")
        o.call("Network.enable")
        if "--recharger" in brut:
            o.call("Page.enable")
            o.call("Page.reload")
        o.ecouter(secondes)

        erreurs, http = [], []
        for e in o.evts:
            m, p = e["method"], e.get("params", {})
            if m == "Runtime.exceptionThrown":
                d = p.get("exceptionDetails", {})
                erreurs.append("JS " + (d.get("exception", {}).get("description")
                                        or d.get("text", ""))[:200])
            elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "warning"):
                txt = " ".join(str(x.get("value", x.get("description", "")))
                               for x in p.get("args", []))[:200]
                erreurs.append(p["type"].upper() + " " + txt)
            elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
                erreurs.append("LOG " + p["entry"].get("text", "")[:200])
            elif m == "Network.responseReceived":
                r = p.get("response", {})
                if r.get("status", 0) >= 400:
                    http.append(f"{r['status']} {r.get('url','')[:110]}")
            elif m == "Network.loadingFailed" and not p.get("canceled"):
                http.append("ECHEC " + (p.get("errorText") or "")[:60])

        bloc("ERREURS", list(dict.fromkeys(erreurs))[:20])
        bloc("HTTP >= 400", list(dict.fromkeys(http))[:20])
        if not erreurs and not http:
            print(f"nothing in {secondes}s of listening" +
                  (" (avec rechargement)" if "--recharger" in brut else
                   " (sans rechargement : ajouter --recharger pour voir le chargement)"))

    elif cmd == "photo":
        o.call("Page.enable")
        clip = None
        au_dela, recadre = True, None
        if "--sur" in brut:
            cible = brut[brut.index("--sur") + 1]
            # Plusieurs elements portent souvent le meme libelle (le bouton ET la
            # barre sticky, la section ET son entree de sommaire). On prend le plus
            # petit qui tombe dans la vue, on AFFICHE lequel, et `--rang N` permet
            # de viser un autre candidat sans deviner.
            depart = int(brut[brut.index("--rang") + 1]) if "--rang" in brut else 0
            garde = None
            fin_recherche = time.time() + 6      # meme borne que pour le clic
            for rang in range(depart, depart + 10):
                if rang > depart and time.time() > fin_recherche:
                    print("NOTE framing capped at 6 s, keeping best candidate")
                    break
                r = o.js(JS_RECT % (json.dumps(cible), rang))
                if not isinstance(r, dict) or not r.get("ok"):
                    break
                stabiliser_cible(o)
                p = o.js(JS_CIBLE_RECT)
                if isinstance(p, dict) and p.get("ok"):
                    garde = p
                    garde["quoi"], garde["rang"] = r.get("quoi", "?"), rang
                    garde["total"] = r.get("total", 1)
                    if p["dansVue"]:
                        break
            if garde:
                # On capture la VUE puis on recadre en Python, au lieu de passer un
                # `clip` a Chrome. Le clip de CDP est en coordonnees DOCUMENT, et
                # celles-ci ne veulent rien dire pour un element dans un conteneur
                # sticky ou fixed (le sommaire lateral de Wikipedia) : le cadrage
                # tombait sur une zone vide. Les coordonnees de la vue, elles, sont
                # justes partout. Le recadrage local ne coute rien ; ce qui compte,
                # c'est la taille de l'image qu'on finit par regarder.
                m = 40
                recadre = (max(0, garde["x"] - garde["w"] / 2 - m),
                           max(0, garde["y"] - garde["h"] / 2 - m),
                           garde["w"] + 2 * m, garde["h"] + 2 * m)
                au_dela, clip = False, False   # capture de la vue, sans clip
                print(f"framed on <{garde['quoi']}> (candidate {garde['rang']} of "
                      f"{garde['total']}, --rang N pour en viser un autre)")
                if not garde["dansVue"]:
                    print("WARNING element out of view, framing is approximate")
            else:
                print("framing failed, full capture")
        if clip is None:
            # hauteur du vrai conteneur de defilement : sur un thema qui defile un
            # div interne, document.body.scrollHeight vaut la hauteur de la fenetre
            # et on ne capturait qu'un ecran.
            h = o.js("Math.max(document.body.scrollHeight, ...[...document.querySelectorAll('*')]"
                     ".filter(e=>e.scrollHeight>e.clientHeight+50).map(e=>e.scrollHeight), 0)") or 2000
            clip = {"x": 0, "y": 0, "width": 1440, "height": min(h, 6000), "scale": 0.6}
        opts = {"format": "png", "captureBeyondViewport": au_dela}
        if clip:
            opts["clip"] = clip
        # Timeout court et un seul nouvel essai. Mesure du 24/08/2026 : pendant la
        # transition masquer/montrer, une capture peut ne jamais repondre, et la
        # session restait bloquee 90 s sur un ecran fige.
        try:
            res = o.call("Page.captureScreenshot", opts, timeout=25)
        except Exception:
            o = Onglet(trouver(motif))          # on se rebranche
            o.call("Page.enable")
            try:
                res = o.call("Page.captureScreenshot", opts, timeout=25)
            except Exception:
                sys.exit("capture failed: rendering not responding (2 tries). "
                         "Recharger la page, ou capturer une section avec --sur.")
        if res.get("_erreur"):
            sys.exit("capture failed: " + json.dumps(res["_erreur"])[:200])
        p = f"/tmp/{a[1]}.png"
        brut = base64.b64decode(res["data"])
        if recadre:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(brut))
            # La capture est en pixels DEVICE : sur un ecran Retina elle vaut le
            # double des coordonnees CSS, et un recadrage non converti tombait a
            # cote (on cadrait le sommaire au lieu du titre vise).
            r = o.js("devicePixelRatio") or 1
            x, y, w, h = (v * r for v in recadre)
            im.crop((int(x), int(y), int(min(x + w, im.width)),
                     int(min(y + h, im.height)))).save(p)
        else:
            open(p, "wb").write(brut)
        from PIL import Image as _I
        with _I.open(p) as im:
            print(p, f"({im.width}x{im.height})")

    elif cmd == "cadres":
        fs = o.frames()
        print("0  (main page)  " + (fs[0]["url"] or "")[:90])
        for n, f in enumerate(fs[1:], 1):
            print(f"{n}  offset {int(f['dx'])},{int(f['dy'])}  " + (f["url"] or "")[:90])
        if len(fs) == 1:
            print("no iframe")
        else:
            print("\nTo act inside: add --cadre <n> or --cadre <part-of-url>")

    elif cmd in ("discret", "montrer"):
        # Ne touche QUE le navigateur bot : tout passe par le port 9333, jamais par
        # un osascript sur "Google Chrome", qui masquerait aussi les fenetres
        # personnelles personnel.
        #
        # Hors ecran, et surtout pas `minimized` : une fenetre minimisee passe en
        # visibilityState 'hidden' et Chrome met son rendu en veille. Sur un theme
        # anime (GSAP) les elements ne sont plus positionnes et le clic ne
        # trouve plus rien. macOS refuse de sortir totalement une fenetre de
        # l'ecran : il reste un carre d'environ 40 px en bas a gauche.
        # Le vrai levier est au niveau de l'APPLICATION : une app masquee n'a pas
        # de fenetre affichable, donc macOS ne peut plus la poser devant l utilisateur.
        # La position hors ecran ne sert plus que de seconde barriere.
        ici = os.path.dirname(os.path.abspath(__file__))
        try:
            r = __import__("subprocess").run(
                [sys.executable, os.path.join(ici, "masquer.py"),
                 "montrer" if cmd == "montrer" else "masquer"],
                capture_output=True, text=True, timeout=30)
            for l in (r.stdout or "").strip().split("\n"):
                if l.strip():
                    print(l.rstrip())
        except Exception as e:
            print("hide failed:", str(e)[:100])
        n = placer_fenetres(o, cmd)
        if cmd == "discret":
            print(f"app hidden, {n} window(s) moved (port {PORT}). "
                  "Clics, lecture et captures continuent de fonctionner : la page se "
                  "croit visible et focalisee (emulation), et elle l'est pour le site.")
        else:
            if os.path.exists(DRAPEAU):
                os.remove(DRAPEAU)
            print(f"{n} window(s) on screen (sign in by hand). "
                  "Repasser en `discret` juste apres.")

    elif cmd == "fermer":
        urllib.request.urlopen(f"{BASE}/json/close/{t['id']}").read()
        # la voie est liberee avec l'onglet ; on l'exclut a la main, la fermeture
        # cote Chrome est asynchrone et il figure encore dans /json/list
        purger({x["id"] for x in onglets()} - {t["id"]})
        print("closed", court(t["id"]))

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
