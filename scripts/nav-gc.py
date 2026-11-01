#!/usr/bin/env python3
"""
nav-gc.py - le ramasse-miettes d'onglets du navigateur bot.

POURQUOI CE FICHIER EXISTE (22/08/2026)
Mesure du jour : 98 onglets ouverts sur le port 9333, 16 Go de RAM, 20 Go de swap
occupes, 993 Mo de disque libre. Le Mac ramait au point que l utilisateur ne pouvait plus
travailler pendant que les sessions tournaient. Chaque session ouvre des onglets pour
mesurer une page, personne ne les referme, et ils vivent des jours.

Ce script tourne toutes les 5 minutes, SANS MODELE, et ferme ce qui traine.

CE QU'IL NE FERME JAMAIS
  - le port 9222, c'est le Chrome personnel personnel. Ce script ne parle qu'au 9333.
  - un onglet dont l'URL est dans `~/.neverlogout/state/onglets-garder.txt`.
  - le dernier onglet : Chrome se fermerait, et avec lui les sessions connectees.
  - un onglet dont l'URL a change depuis le dernier passage : il sert, son
    compteur repart a zero.

COMMENT IL SAIT QU'UN ONGLET EST VIEUX
CDP ne publie aucune date de derniere interaction. On tient donc notre propre
journal : a chaque passage on note (targetId, url). Un onglet dont le couple n'a pas
bouge depuis plus de DELAI minutes est considere comme abandonne. Une navigation
remet le compteur a zero, ce qui est exactement le signal « quelqu'un s'en sert ».

  nav-gc.py            ferme ce qui a depasse le delai
  nav-gc.py voir       liste ce qui serait ferme, sans rien fermer
  nav-gc.py garder <motif>   ajoute un motif a la liste blanche
  nav-gc.py maintenant [n]   ne garde que les n onglets les plus recents, tout de suite
"""
import json, os, re, sys, time, urllib.request

PORT = 9333
DELAI_MIN = int(os.environ.get("NAV_GC_DELAI", "30"))
# Une reservation @voie protege un onglet, mais pas eternellement : la session qui
# l'a prise meurt sans toujours appeler `nav.py fermer`. Mesure du 27/08/2026 :
# 185 onglets reserves, dont 57 pour la seule voie @mbn, les plus vieux de 40 h,
# 14,7 Go de RAM et 27 Go de swap. Passe ce delai, la reservation ne vaut plus rien
# et l'onglet retombe dans le regime commun.
RESERVE_MIN = int(os.environ.get("NAV_GC_RESERVE", "45"))
ETAT = os.path.expanduser("~/.neverlogout/state/onglets.json")
# Journal tenu par nav.py : quel onglet a servi, quand, et a quelle voie de
# travail il a ete reserve. Sans lui, une session qui lit et clique dans une
# application sans jamais changer d'URL (Shopify, Runway) voyait son onglet
# ferme sous ses doigts au bout de 30 minutes.
ACTIFS = os.path.expanduser("~/.neverlogout/state/onglets-actifs.json")
BLANCHE = os.path.expanduser("~/.neverlogout/state/onglets-garder.txt")
PLANCHER = 1  # on laisse toujours vivre au moins un onglet
# PLAFOND PAR DOMAINE (29/08/2026). Mesure du jour : 82 onglets dont 33 sur le seul
# monbienneuf.vercel.app, 11,8 Go de swap sur 12 disponibles, le Mac chauffait et
# se dechargeait. Aucune des regles precedentes ne les attrapait : ni liste blanche,
# ni reservation @voie, ni delai (une session qui teste 33 pages les ouvre en 5 min,
# ils sont tous « neufs »). La regle qui manquait ne regarde ni l'age ni le
# proprietaire : on ne garde JAMAIS plus de N onglets sur un meme domaine, on garde
# les N derniers servis. Une session ne regarde qu'une page a la fois.
PLAFOND_DOM = int(os.environ.get("NAV_GC_PLAFOND_DOM", "2"))
PLAFOND_TOTAL = int(os.environ.get("NAV_GC_PLAFOND", "30"))


def liste():
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=4)
        return [t for t in json.load(r) if t.get("type") == "page"]
    except Exception:
        return []


def fermer(tid):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/close/{tid}", timeout=4).read()
        return True
    except Exception:
        return False


def actifs():
    try:
        return json.load(open(ACTIFS, encoding="utf-8"))
    except Exception:
        return {}


def blanche():
    """Les motifs a ne jamais fermer. Une ligne = un bout d'URL, # pour commenter."""
    if not os.path.exists(BLANCHE):
        os.makedirs(os.path.dirname(BLANCHE), exist_ok=True)
        open(BLANCHE, "w").write(
            "# Un motif d'URL par ligne : tout onglet qui le contient survit au menage.\n"
            "# Y mettre les pages qui portent une session longue a rouvrir.\n"
            "accounts.google.com\n"
            ""
        )
    return [l.strip() for l in open(BLANCHE)
            if l.strip() and not l.startswith("#")]


def domaine(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else (url or "")[:40]


def etat():
    if os.path.exists(ETAT):
        try:
            return json.load(open(ETAT))
        except Exception:
            pass
    return {}


def sauver(e):
    os.makedirs(os.path.dirname(ETAT), exist_ok=True)
    json.dump(e, open(ETAT, "w"), indent=1)


def passe(sec=False):
    pages = liste()
    if not pages:
        print("browser not reachable, nothing to do")
        return
    garder = blanche()
    vu = etat()
    sert = actifs()
    maintenant = time.time()
    neuf, vieux, proteges = {}, [], {}
    reserves = {}

    for p in pages:
        tid, url = p["id"], p.get("url", "")
        ancien = vu.get(tid)
        if ancien and ancien.get("url") == url:
            depuis = ancien["depuis"]          # meme onglet, meme page : il vieillit
        else:
            depuis = maintenant                # nouveau, ou il a navigue : il rajeunit
        # une commande nav.py sur cet onglet vaut une navigation : il sert
        depuis = max(depuis, sert.get(tid, {}).get("vu", 0))
        neuf[tid] = {"url": url, "depuis": depuis}

        # Un onglet DONNE a une voie de travail appartient a une session : on ne le
        # ferme jamais, meme silencieux. C'est elle qui decide, avec `nav.py fermer`.
        info = sert.get(tid, {})
        voie = info.get("voie")
        if voie and maintenant - info.get("vu", 0) <= RESERVE_MIN * 60:
            reserves.setdefault(voie, []).append((tid, url, info.get("vu", 0)))
            continue

        if any(m in url for m in garder):
            proteges.setdefault(domaine(url), []).append((tid, url, depuis))
            continue
        if maintenant - depuis > DELAI_MIN * 60:
            vieux.append((tid, url, (maintenant - depuis) / 60))

    # UN SEUL ONGLET PAR SITE PROTEGE. Proteger « instagram.com » ne doit pas vouloir
    # dire garder les douze onglets Instagram : la session vit dans les cookies du
    # profil, pas dans l'onglet. On garde le plus recent de chaque domaine protege et
    # on ferme ses doublons, meme s'ils n'ont pas atteint le delai.
    for dom, lot in proteges.items():
        if len(lot) > 1:
            lot.sort(key=lambda x: x[2])          # du plus ancien au plus recent
            for tid, url, depuis in lot[:-1]:
                vieux.append((tid, url, (maintenant - depuis) / 60))

    # UNE VOIE = UN ONGLET. Une session qui mesure vingt pages d'un site en reserve
    # vingt : elle n'en regarde qu'un a la fois. On garde le dernier servi.
    for voie, lot in reserves.items():
        if len(lot) > 1:
            lot.sort(key=lambda x: x[2])
            for tid, url, vu in lot[:-1]:
                vieux.append((tid, url, (maintenant - vu) / 60))
            del lot[:-1]

    # PLAFOND PAR DOMAINE, puis PLAFOND TOTAL. Ces deux regles passent apres toutes
    # les autres et ne respectent ni liste blanche ni reservation : ce sont les seules
    # qui bornent la consommation quoi qu'il arrive.
    condamnes = {t for t, _, _ in vieux}
    restants = [p for p in pages if p["id"] not in condamnes]

    par_dom = {}
    for p in restants:
        par_dom.setdefault(domaine(p.get("url", "")), []).append(p)
    for dom, lot in par_dom.items():
        if len(lot) <= PLAFOND_DOM:
            continue
        lot.sort(key=lambda p: max(sert.get(p["id"], {}).get("vu", 0),
                                   neuf.get(p["id"], {}).get("depuis", 0)))
        for p in lot[:-PLAFOND_DOM]:
            vieux.append((p["id"], p.get("url", ""), 0))
            condamnes.add(p["id"])

    restants = [p for p in pages if p["id"] not in condamnes]
    if len(restants) > PLAFOND_TOTAL:
        restants.sort(key=lambda p: max(sert.get(p["id"], {}).get("vu", 0),
                                        neuf.get(p["id"], {}).get("depuis", 0)))
        for p in restants[:-PLAFOND_TOTAL]:
            vieux.append((p["id"], p.get("url", ""), 0))

    # on ne descend jamais sous le plancher, sinon Chrome se ferme
    survivants = len(pages) - len(vieux)
    if survivants < PLANCHER:
        vieux = vieux[: max(0, len(vieux) - (PLANCHER - survivants))]

    if reserves:
        print("  reserves : " + ", ".join(f"@{v}" for v in sorted(reserves)))
    if not vieux:
        print(f"{len(pages)} onglet(s), aucun au-dela de {DELAI_MIN} min")
        sauver(neuf)
        return

    for tid, url, age in vieux:
        if sec:
            print(f"  fermerait ({age:.0f} min)  {url[:100]}")
        else:
            if fermer(tid):
                neuf.pop(tid, None)
                print(f"  ferme ({age:.0f} min)  {url[:100]}")

    if not sec:
        sauver(neuf)
        # onglets-actifs.json garde une ligne par onglet jamais reference : on le
        # ramene aux onglets qui existent encore, sinon il grossit indefiniment.
        vivants = {t["id"] for t in liste()}
        if sert:
            elague = {k: v for k, v in sert.items() if k in vivants}
            if len(elague) != len(sert):
                json.dump(elague, open(ACTIFS, "w"), indent=1)
        print(f"{len(vieux)} ferme(s), {len(vivants)} restant(s)")


def maintenant_(n):
    """Coupe franche : on ne garde que les n derniers onglets, liste blanche exclue.
    Sert quand le navigateur a deja derape et qu'attendre le delai n'a plus de sens."""
    pages = liste()
    garder = blanche()
    sert = actifs()
    import time as _t
    maintenant = _t.time()
    proteges, autres, gardes, voies = {}, [], [], {}
    for p in pages:
        u = p.get("url", "")
        info = sert.get(p["id"], {})
        # Une reservation ne vaut que si elle est fraiche, et une voie ne garde
        # qu'un onglet : le dernier servi. Le reste est du residu de session morte.
        if info.get("voie") and maintenant - info.get("vu", 0) <= RESERVE_MIN * 60:
            voies.setdefault(info["voie"], []).append((p, info.get("vu", 0)))
            continue
        if any(m in u for m in garder):
            proteges.setdefault(domaine(u), []).append(p)
        else:
            autres.append(p)
    a_fermer = autres[:-n] if n > 0 else list(autres)
    for voie, lot in voies.items():
        lot.sort(key=lambda x: x[1])
        gardes.append(lot[-1][0])
        a_fermer.extend(q for q, _ in lot[:-1])
    for dom, lot in proteges.items():
        gardes.append(lot[-1])
        a_fermer.extend(lot[:-1])
    for p in a_fermer:
        if fermer(p["id"]):
            print(f"  ferme  {p.get('url','')[:100]}")
    print(f"{len(a_fermer)} ferme(s), {len(liste())} restant(s) "
          f"(dont {len(gardes)} session(s) gardee(s) : "
          f"{', '.join(sorted(proteges))})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        passe()
    elif a[0] == "voir":
        passe(sec=True)
    elif a[0] == "garder" and len(a) > 1:
        blanche()
        open(BLANCHE, "a").write(a[1] + "\n")
        print(f"« {a[1] } » ne sera plus ferme")
    elif a[0] == "maintenant":
        maintenant_(int(a[1]) if len(a) > 1 else 5)
    else:
        print(__doc__)
