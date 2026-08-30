# navigateur bot

Un Chrome que Claude Code pilote à ta place, **déjà connecté à tes comptes**, qui
travaille sans jamais passer devant ton écran.

Tu demandes « ouvre mon Gmail et résume-moi les 3 derniers mails », « va sur mon Shopify
et regarde les commandes du jour », « connecte-toi à ce site et envoie ce message » : il
le fait, au lieu de te rendre un texte à copier-coller.

## Installer

Une commande, sur un **Mac** avec **Google Chrome** installé et tes comptes connectés
dedans :

```bash
curl -fsSL https://raw.githubusercontent.com/vocalyagent/nav-bot/main/install.sh | bash
```

Rien à configurer ensuite. L'installation lit tes profils Chrome, trouve toute seule quels
comptes tu as (Google, Gmail, Drive, YouTube, GitHub, Shopify, Notion, X, Instagram,
TikTok, LinkedIn, Canva, Figma, Vercel), et branche le navigateur bot dessus.

macOS te demandera l'accès au Trousseau : c'est Chrome qui protège tes cookies, il faut
accepter pour les recopier dans le navigateur bot. **Rien ne quitte ta machine.**

Ensuite, ouvre Claude Code et demande-lui quelque chose. Il lit tout seul la fiche
`naviguer` installée en même temps, et sait s'en servir.

## Comment ça marche

- Un **Chrome séparé** sur le port 9333, profil `~/.bot-navigateur`. Il ne touche jamais
  au Chrome que tu utilises, ni à tes onglets.
- Il **emprunte tes cookies** au profil Chrome qui porte déjà le compte, en local, par le
  protocole de debug de Chrome. Aucun mot de passe ne circule, aucun 2FA à refaire.
- Il **travaille masqué**. Quatre gardiens le tiennent hors de ton écran et te rendent le
  focus s'il essaie de passer devant.
- On le pilote **par texte visible** (« clique sur Envoyer »), jamais en coordonnées : un
  bandeau qui bouge de 20 px ne casse rien.

## Vérifier, à la main

```bash
~/.claude/scripts/navigateur-bot.sh --etat            # allumé ?
P=~/.claude/scripts/.venv-cdp/bin/python; S=~/.claude/scripts/nav.py
$P ~/.claude/scripts/sessions.py etat                 # quelles sessions sont vivantes
$P $S ouvrir https://gmail.com 20
$P $S lire gmail 2000
$P $S onglets
```

Une session **MORTE** veut dire une seule chose : ce compte n'est connecté dans aucun de
tes profils Chrome. Connecte-toi **une fois** dans ton Chrome habituel, la greffe repart
seule dans les 20 minutes.

## Ce qui est installé

| Où | Quoi |
|---|---|
| `~/.claude/scripts/` | les scripts et leur environnement python (`.venv-cdp`) |
| `~/.claude/skills/naviguer/` | la fiche que Claude Code lit tout seul |
| `~/.claude/etat/`, `~/.claude/sessions/` | états et journaux |
| `~/.bot-navigateur/` | le profil du Chrome bot (tes cookies greffés) |
| `~/Library/LaunchAgents/com.navbot.*` | les quatre gardiens |

Tout fichier qui existait déjà sous le même nom est sauvegardé en `.avant-navbot-<date>`.

## Désinstaller

```bash
for f in ~/Library/LaunchAgents/com.navbot.*.plist; do launchctl unload "$f"; rm "$f"; done
~/.claude/scripts/navigateur-bot.sh --arret
rm -rf ~/.bot-navigateur ~/.claude/skills/naviguer
```

## Limites, dites d'avance

- **macOS seulement** (launchd, Trousseau, le masquage d'application). Pas de Windows,
  pas de Linux.
- **Google Chrome obligatoire**, avec tes comptes déjà connectés dedans.
- Une **2FA** demandée au moment de l'action, un **paiement**, un **bouton publier** :
  ça s'arrête là, c'est à toi. Le reste est de la technique, et c'est son travail.

## Ce qui reste chez toi

Tes cookies, tes comptes, ta table `sessions.json`. Ce dépôt ne contient que des scripts :
aucune donnée personnelle, aucune clé, aucun jeton. Ta table de sessions est **générée sur
ta machine** au moment de l'installation, à partir de ton Chrome à toi.
