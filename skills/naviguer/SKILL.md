---
name: naviguer
description: Agir sur un site web à la place de l'utilisateur (se connecter, cliquer, remplir, lire une page protégée, envoyer un message) avec le navigateur bot et `nav.py`. Utiliser dès qu'une tâche demande autre chose que lire une page publique, et avant de rendre un message « à copier-coller » : c'est le signe qu'on n'a pas essayé d'agir.
---

# Naviguer et agir à la place de l'utilisateur

Un Chrome dédié, déjà connecté aux comptes de l'utilisateur, piloté par texte et non par
coordonnées, qui travaille masqué pendant qu'il fait autre chose.

## La règle qui compte

**Avant de dire « voici le message à envoyer », vérifier l'état de session.** Un tour de
`sessions.py etat` coûte trois secondes et transforme un copier-coller en action faite.
Presque toujours, le compte est déjà branché et il ne manque qu'un clic.

## Les deux navigateurs, à ne jamais confondre

| | Port | Profil | Pour quoi |
|---|---|---|---|
| **navigateur bot** | **9333** | `~/.bot-navigateur` | tout notre travail. Isolé, ne touche jamais aux onglets de l'utilisateur |
| Chrome personnel | — | ses comptes | on n'y touche pas. On lui emprunte seulement ses cookies, par `sessions.py` |

```bash
~/.claude/scripts/navigateur-bot.sh --etat     # pret sur 9333 / eteint
~/.claude/scripts/navigateur-bot.sh            # le lance, masqué
```

Aucun `--enable-automation`, donc `navigator.webdriver` reste `false` et Cloudflare ne
voit pas d'automatisation. C'est ce qui le distingue d'un Chromium de test, bloqué par
construction.

## Raccourci utilisé partout dans cette fiche

```bash
P="$HOME/.claude/scripts/.venv-cdp/bin/python"; S="$HOME/.claude/scripts/nav.py"
```

## Règle non négociable : il travaille hors de l'écran

**Le navigateur bot ne doit jamais surgir devant l'utilisateur ni lui prendre le focus.**
Il travaille pendant que l'utilisateur fait autre chose. Une fenêtre qui saute au premier
plan à chaque `ouvrir`, c'est une interruption toutes les dix secondes.

`navigateur-bot.sh` le lance déjà masqué. Rien à faire dans le cas normal.

```bash
$P $S discret     # le repousse hors écran (il reste entièrement pilotable)
$P $S montrer     # le ramène, UNIQUEMENT pour un login tapé à la main
```

Trois choses à respecter :

1. **Après un `montrer`, toujours refaire `discret`** dès que le login est fini.
2. **Ne jamais masquer via `osascript` sur « Google Chrome »** : c'est le même nom de
   processus que le Chrome personnel, on masquerait ses propres fenêtres. Tout passe par
   le port 9333, qui ne désigne que le navigateur bot.
3. **Ne jamais utiliser `windowState: minimized`.** Une fenêtre minimisée passe en
   `visibilityState: hidden` et Chrome met son rendu en veille : sur un site animé, les
   éléments ne sont plus positionnés et le clic ne trouve plus rien. Masqué ou hors
   écran, le rendu continue normalement.

### Interdits absolus : ce qui téléporte l'utilisateur

Trois appels ramènent la fenêtre devant lui et changent son onglet actif, en plein
travail. Ils sont bannis de tous les scripts :

| Interdit | À la place |
|---|---|
| `Page.bringToFront` | `Emulation.setFocusEmulationEnabled {enabled:true}` + `Page.setWebLifecycleState {state:"active"}` |
| `/json/activate/<id>` | rien : l'onglet n'a pas besoin d'être actif |
| `/json/new?url` (HTTP) | `Target.createTarget {url, background:true}` |

Mesuré : fenêtre hors écran, `document.visibilityState` valait `hidden` et
`document.hasFocus()` `false`, donc les pages animées ne positionnaient plus rien et les
clics tombaient à côté. Les deux commandes d'émulation rendent exactement le même état
(`visible`, `hasFocus true`) **sans déplacer une seule fenêtre**. Bonus : la page ne se
croit plus cachée, donc elle charge normalement. La sonde des sessions est passée de 72 s
à 29 s.

### La règle mère : l'application est MASQUÉE, pas seulement hors écran

Tant que ce Chrome est une application de premier plan avec une fenêtre, macOS a le droit
de la poser devant l'utilisateur, et il le fait quand son app active change. Personne
n'appelle rien : c'est macOS. `masquer.py` masque donc l'APPLICATION (le « Masquer » du
menu Pomme). Une app masquée n'a pas de fenêtre affichable et ne reçoit pas le premier
plan.

```bash
~/.claude/scripts/masquer.py            # masque (idempotent)
~/.claude/scripts/masquer.py etat       # qui est masqué
~/.claude/scripts/masquer.py montrer    # login à la main
```

Tout fonctionne masqué, **et plus vite** : `elements` rend ses boutons, une capture rend
une vraie image, un clic tombe à 1,47 s contre 2,08 s fenêtre affichée.

### Les gardiens (launchd, aucun modèle appelé, coût nul)

| | Rôle | Journal |
|---|---|---|
| `com.navbot.nav-fond` | toute fenêtre du bot revenue à l'écran est repoussée, en continu | `~/.claude/etat/com.navbot.nav-fond.log` |
| `com.navbot.focus-fond` | événementiel : si le navigateur bot passe devant, il le remasque et rend le premier plan à l'app où on était | `~/.claude/etat/com.navbot.focus-fond.log` |
| `com.navbot.sessions` | toutes les 20 min, regreffe les sessions mortes | `~/.claude/sessions/sessions.log` |
| `com.navbot.nav-gc` | toutes les 5 min, ferme les onglets inactifs depuis 30 min | `~/.claude/etat/com.navbot.nav-gc.log` |

**Quand l'utilisateur dit « ça m'a téléporté », lire `com.navbot.focus-fond.log` à l'heure
dite : il nomme l'app fautive.** On ne devine pas.

Conséquence du ramasse-miettes : on ne laisse pas une page ouverte « pour plus tard », on
la rouvre. Un onglet réservé à une voie (`--voie`) n'est jamais fermé automatiquement.

## L'outil : nav.py

Il **garde l'onglet ouvert** entre deux appels et retrouve la page par un bout d'URL, ce
qui permet d'enchaîner ouvrir → cliquer → lire.

```bash
$P $S onglets                              # ce qui est ouvert : #id, @voie, âge, url
$P $S ouvrir "https://..." 15              # 15 = timeout MAX, pas une attente fixe
$P $S etat "gmail"                         # url, titre, connecté ?
$P $S elements "gmail"                     # inventaire : boutons / liens / champs / menus
$P $S lire "gmail" 3000                    # innerText, 3000 caractères
$P $S clic "gmail" "Envoyer"               # par TEXTE VISIBLE, jamais en x/y
$P $S champ "gmail" "Objet" "Bonjour"      # placeholder / name / label
$P $S menu "site" "quantité" "50"          # <select>
$P $S attendre "site" "Message envoyé" 20  # attend un texte, jamais un sleep
$P $S touche "site" Enter                  # Enter / Escape / Tab
$P $S js "site" "document.title"           # évalue du JS
$P $S console "site" 8 --recharger         # erreurs JS + HTTP >= 400 (QA)
$P $S photo "site" nom --sur "Envoyer"     # capture /tmp/nom.png, cadrée sur la section
$P $S cadres "checkout"                    # liste les iframes
$P $S fermer "site"
```

**Désigner un onglet**, du plus sûr au plus souple : `#a1b2c3` (identifiant court, ne
bouge jamais), `@voie` (si réservée), ou un bout d'URL. Vide = l'onglet actif. À égalité
sur un bout d'URL, c'est l'onglet le plus récemment utilisé qui gagne.

```bash
$P $S ouvrir "https://..." 20 --voie mails   # ouvre ET réserve
$P $S reserver "gmail" mails                 # ou réserve un onglet déjà là
$P $S lire @mails 3000
```

Plusieurs sessions en parallèle : chacune réserve sa voie une fois, puis ne vise plus que
`@sa-voie`. Le nom de la voie = la ressource touchée, pas le sujet.

### Commencer par `elements`, pas par `clic`

Deviner un libellé puis échouer coûte un tour à chaque page inconnue. `elements` donne
l'inventaire pour ~400 tokens, et fait remonter les **boutons en icône** (croix, panier,
zoom) via `aria-label` et `title`, invisibles au clic par texte seul.

**Pourquoi le clic passe par du texte et pas par des coordonnées** : un bandeau qui bouge
de 20 px casse un clic en x/y, et il casse en silence. `nav.py clic` trouve le plus petit
élément visible contenant le texte, le fait défiler au centre, puis envoie un **vrai
événement souris**. Un `.click()` en JS est ignoré par beaucoup de sites (Shopify,
Alibaba) ; un événement souris ne l'est pas. Quand la cible n'est pas trouvée, le script
rend la liste des textes cliquables qu'il a vus : c'est là qu'on lit le vrai libellé.

Quatre pièges qui cassaient en silence, tous corrigés dans `nav.py` :

1. *Le défilement animé* (`scroll-behavior: smooth`) : les coordonnées lues juste après
   `scrollIntoView` sont celles d'avant l'animation.
2. *Le conteneur de défilement interne* : beaucoup de thèmes ne font pas défiler la
   fenêtre mais un `div`, donc `scrollY` vaut 0 en permanence. On surveille la cible.
3. *Le même libellé plusieurs fois* : deux « Ajouter au panier », celui du formulaire et
   celui d'une barre sticky masquée. `clic` essaie plusieurs candidats et garde le premier
   réellement dans la vue ; `photo --sur` dit lequel il a retenu, `--rang N` vise le
   suivant.
4. *L'écran Retina* : la capture est en pixels device, le double des coordonnées CSS.
   C'est `devicePixelRatio` qui fait le pont.

**Une page qui n'a pas chargé le dit.** `ouvrir` détecte `chrome-error://`, retente une
fois, puis referme l'onglet et sort en erreur, au lieu d'annoncer « PRET » sur une page
morte.

## Les iframes : paiement, captcha, widget

Un tunnel de paiement, un captcha, un bouton PayPal ne sont **pas dans la page** : ils
vivent dans une iframe, et `elements` sur la page ne les voit pas.

```bash
$P $S cadres "checkout"                                  # liste, avec un index par cadre
$P $S elements "checkout" --cadre 1
$P $S elements "checkout" --cadre stripe                 # ou par un bout d'URL
$P $S champ "checkout" --cadre stripe "Numero de carte" "4242..."
```

`--cadre` marche sur `lire`, `elements`, `clic`, `champ`, `menu`, `attendre` et `js`. Le
clic souris part toujours vers la page principale avec l'offset de l'iframe ajouté : c'est
la fenêtre qui reçoit les événements souris, pas le cadre.

## Les sessions : elles se réparent toutes seules

Le bot n'a jamais besoin de se connecter. Il **emprunte les cookies** du profil Chrome qui
porte déjà le compte, par CDP, sans mot de passe et sans rien relancer.

```bash
$P ~/.claude/scripts/sessions.py etat            # VIVANTE / MORTE, site par site
$P ~/.claude/scripts/sessions.py reparer         # regreffe ce qui est mort
$P ~/.claude/scripts/sessions.py assurer google  # une seule, silencieux si OK
~/.claude/scripts/configurer-sessions.py         # redétecte les comptes du Chrome local
```

`ouvrir` et `etat` détectent une page de connexion sur un site connu de `sessions.json`,
regreffent la session et rouvrent la page. Rien ne remonte à l'utilisateur tant que la
greffe marche. Sur un `clic`, on ne regreffe pas au milieu d'un formulaire : la ligne
`SESSION <nom> TOMBEE` donne la commande à lancer.

**Une session marquée MORTE que la greffe ne restaure pas** veut dire une seule chose : ce
compte n'est connecté dans aucun profil du Chrome personnel. L'utilisateur s'y connecte
**une fois** dans son Chrome habituel, et la greffe repart seule.

## Se connecter : commencer par supposer que c'est déjà fait

Ordre à suivre, il fait gagner un quart d'heure à chaque fois :

1. **`nav.py onglets`.** Un onglet `fiverr.com/inbox/...` ouvert veut dire Fiverr connecté.
2. **`nav.py google`** : quel compte Google porte le profil du bot, et est-il connecté.
3. **Ouvrir la page de connexion du site.** Si le profil a déjà Google, la plupart des
   sites affichent « Continuer en tant que … ? ». Un `clic "Oui"` suffit.
4. **Si un vrai formulaire s'affiche**, chercher le bouton Google d'abord
   (`clic "Google"`), le mot de passe en dernier.

Le déroulé « Continuer avec Google » sur un site tiers :

```bash
$P $S elements "lesite"                        # repérer le libellé exact
$P $S clic "lesite" "Continuer avec Google"    # ouvre une POPUP, donc une autre fenêtre
$P $S onglets                                  # la popup y apparaît
$P $S clic "accounts.google" "<l'adresse>"
$P $S attendre "lesite" "<un texte de la zone connectée>" 20
```

**La popup naît au milieu de l'écran**, même quand les autres fenêtres sont hors champ.
`nav.py` la repousse tout seul après chaque `clic` et chaque `touche`, tant que le mode
discret est actif (drapeau `~/.bot-navigateur/.discret`). Ne pas retirer cet appel.

**Piège de lecture sur Gmail** : `innerText` revient **vide** sur la liste des messages
quand la fenêtre est hors écran, Chrome ne calculant pas le rendu de ce qui n'est pas
peint. Passer par `textContent` sur un sélecteur, jamais par `lire` :

```bash
$P $S js "mail.google" "[...document.querySelectorAll('.a3s')].map(e=>e.textContent).join(' ')"
```

Et vérifier le contexte d'un code avant de le saisir : un `\d{6}` attrapé au hasard dans
une page peut être un numéro d'article d'aide.

## Ce qui s'arrête, et se dit en une ligne

Trois choses ne se contournent pas, et s'acharner dessus coûte des heures :

- une **2FA** au moment de l'action, ou « Ce navigateur n'est peut-être pas sécurisé » ;
- un **paiement** ;
- le **bouton publier** de ce qui sort vers le public.

Dans ces cas on s'arrête et on écrit une ligne : `BLOQUÉ : <ce que l'utilisateur doit
faire>`. Tout le reste (une session tombée, un token sans la bonne portée, un réglage
enfoui dans un shadow DOM) est un problème technique : il a une solution technique, et
c'est notre travail de la trouver avant de parler.

**Avant d'envoyer quoi que ce soit à un humain** (message fournisseur, mail client, post),
montrer le texte en une ligne. Le reste se fait sans demander.

**« Continuer avec Google » sur un site où le compte n'existe pas encore crée un compte.**
On annonce le site en une ligne avant, comme pour tout ce qui engage.
