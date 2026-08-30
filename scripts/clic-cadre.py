#!/usr/bin/env python3
"""Cliquer un bouton d'application embarquee dans l'admin Shopify.

Pourquoi (22/08/2026) : les apps de l'admin (Google & YouTube, Pinterest, Meta)
vivent dans une iframe d'un AUTRE domaine, et leurs boutons sont des composants
Polaris `<s-button>` dont le vrai `<button>` est dans un shadow root. Consequence :
`nav.py clic` ne les voit pas ("PAS TROUVE"), et un clic souris envoye a la page
principale ne les atteint pas non plus. Trois installations d'app ont ete perdues
la-dessus avant d'ecrire ce fichier.

Ce qui marche : s'attacher au target de l'iframe (Target.setAutoAttach flatten),
chercher le texte dans TOUS les shadow roots, prendre le noeud le plus PROFOND
qui porte ce texte, puis appeler `.click()` sur le vrai bouton du shadow root.

  clic-cadre.py <motif-onglet> <motif-cadre> "<texte>" [--lister] [--rang N]

`--rang N` quand plusieurs boutons portent le meme texte (deux « Associer »
dans l'onboarding Google) : 0 est le premier dans l'ordre du document.

Exemples :
  clic-cadre.py apps/google channel-app.google "J'accepte"
  clic-cadre.py pinterest-4 pintergration "Terminer la configuration"
  clic-cadre.py apps/google channel-app.google "" --lister   # ce qui est cliquable
"""
import json
import os
import sys
import time
import urllib.request

import websocket

PORT = int(os.environ.get("CDP_PORT", "9333"))


def pages():
    d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=10))
    return [t for t in d if t.get("type") == "page"]


CHERCHE = r"""
(() => {
  const t = %s;
  const lister = %s;
  const rang = %s;
  const boutons = [];
  const parcours = (racine) => {
    for (const e of racine.querySelectorAll('*')) {
      if (e.shadowRoot) parcours(e.shadowRoot);
      const tag = e.tagName;
      if (/^(S-BUTTON|BUTTON|A|S-LINK)$/.test(tag)) boutons.push(e);
    }
  };
  parcours(document);
  const texte = (e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim();
  if (lister) return boutons.map(e => e.tagName + ' : ' + texte(e).slice(0, 60)).slice(0, 60);

  // le bon noeud est le plus COURT qui contient le texte : un conteneur
  // contient aussi le texte de tous ses enfants, et c'est lui qu'on cliquait.
  const candidats = boutons
    .map(e => ({e, txt: texte(e)}))
    .filter(o => o.txt.includes(t))
    .sort((a, b) => a.txt.length - b.txt.length);
  if (!candidats.length) return {err: 'introuvable'};

  const cible = (candidats[rang] || candidats[0]).e;
  let reel = cible;
  if (cible.shadowRoot) {
    const b = cible.shadowRoot.querySelector('button, a');
    if (b) reel = b;
  }
  reel.scrollIntoView({block: 'center'});
  const r = reel.getBoundingClientRect();
  reel.click();
  if (reel !== cible) cible.click();
  return {tag: cible.tagName, texte: candidats[0].txt.slice(0, 60),
          x: r.x + r.width / 2, y: r.y + r.height / 2, candidats: candidats.length};
})()
"""


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    motif, cadre, texte = sys.argv[1], sys.argv[2], sys.argv[3]
    lister = "--lister" in sys.argv

    onglet = next((x for x in pages() if motif in x.get("url", "")), None)
    if not onglet:
        sys.exit(f"aucun onglet ne contient '{motif}'")

    ws = websocket.create_connection(onglet["webSocketDebuggerUrl"], timeout=60)
    n = [0]
    sessions = {}

    def envoi(methode, params=None, sess=None):
        n[0] += 1
        msg = {"id": n[0], "method": methode, "params": params or {}}
        if sess:
            msg["sessionId"] = sess
        ws.send(json.dumps(msg))
        fin = time.time() + 45
        while time.time() < fin:
            r = json.loads(ws.recv())
            if r.get("method") == "Target.attachedToTarget":
                sessions[r["params"]["sessionId"]] = r["params"]["targetInfo"].get("url", "")
            if r.get("id") == n[0]:
                if "error" in r:
                    print("  erreur", methode, r["error"].get("message"))
                return r.get("result", {})
        return {}

    # Pas de `Page.bringToFront` : il ramenait la fenetre du navigateur bot devant
    # l'ecran de l'utilisateur. Ces deux commandes donnent a la page le meme etat
    # (visible, focalisee) sans deplacer quoi que ce soit.
    envoi("Emulation.setFocusEmulationEnabled", {"enabled": True})
    envoi("Page.setWebLifecycleState", {"state": "active"})
    envoi("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False,
                                   "flatten": True})
    time.sleep(3)
    envoi("Runtime.evaluate", {"expression": "1", "returnByValue": True})
    time.sleep(2)

    sid = next((k for k, v in sessions.items() if cadre in v), None)
    if not sid:
        print("cadres attaches :", {v[:70] for v in sessions.values()})
        sys.exit(f"aucun cadre ne contient '{cadre}'")

    rang = 0
    if "--rang" in sys.argv:
        rang = int(sys.argv[sys.argv.index("--rang") + 1])
    js = CHERCHE % (json.dumps(texte), "true" if lister else "false", rang)
    r = envoi("Runtime.evaluate", {"expression": js, "returnByValue": True}, sess=sid)
    v = r.get("result", {}).get("value")
    if lister:
        for ligne in v or []:
            print(" ", ligne)
    else:
        print(v)
    ws.close()


if __name__ == "__main__":
    main()
