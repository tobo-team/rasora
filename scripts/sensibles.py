#!/usr/bin/env python3
"""What the agent must never reach on its own.

Signing in to a site holding money, identity or passwords shows a warning. Local addresses are refused so a page can't send the agent to the
browser's debug port or to a machine on the home network.
"""
import ipaddress
import re
import socket
import sys
import urllib.parse

# Shared by the guard and by nav.py, which checks the real element once it has found it.
RISQUE = re.compile(
    r"\b(pay|payer|payez|payment|paiement|pagar|bezahlen|zahlen|buy|acheter|achetez|achat|"
    r"purchase|comprar|acquista|kaufen|order|commander|commandez|bestellen|checkout|check out|"
    r"subscribe|s'abonner|abonnez|transfer|virement|withdraw|publish|publier|publiez|post|"
    r"poster|tweet|share|partager|send|envoyer|envoyez|enviar|senden|invia|reply|r[eé]pondre|"
    r"delete|supprimer|supprimez|effacer|eliminar|l[oö]schen|elimina|remove|confirm|confirmer|"
    r"confirmez|confirmar|best[aä]tigen|conferma|valider|validez|book|r[eé]server|r[eé]servez|"
    r"donate)\b", re.I)
CHAMP = re.compile(r"card|carte|cvv|cvc|iban|password|passwort|contrase[nñ]a|mot de passe|\bmdp\b|"
                   r"\bpass\b|passcode|\bpwd\b|\bpin\b|\botp\b|\b2fa\b|security code|"
                   r"code de s[eé]curit[eé]|\bcb\b|ssn|routing|api.?key|secret|token", re.I)

MOTS = ("bank", "banque", "paypal", "chase", "wellsfargo", "citibank", "capitalone",
        "americanexpress", "amex", "schwab", "fidelity", "vanguard", "robinhood", "revolut",
        "wise", "n26", "boursorama", "creditagricole", "credit-agricole", "bnpparibas",
        "societegenerale", "labanquepostale", "caisse-epargne", "lcl", "hsbc", "barclays",
        "santander", "coinbase", "binance", "kraken", "bitstamp", "metamask", "ledger",
        "1password", "lastpass", "bitwarden", "dashlane", "keeper", "okta", "turbotax",
        "ameli", "impots", "franceconnect", "myhealthchart", "healthcare")
SUFFIXES = (".gov", ".gouv.fr", ".mil")
DEUXIEME_NIVEAU = {"ac", "co", "com", "edu", "go", "gob", "gouv", "gov", "ne", "net", "or", "org"}


def normaliser(texte):
    """The URL as a browser reads it: backslashes, a missing slash and stray spaces change nothing."""
    t = re.sub(r"[\x00-\x20]", "", str(texte or "")).replace("\\", "/").lower()
    return re.sub(r"^(https?):/*", r"\1://", t)


def hote_de(texte):
    """The host, "" if there is none, None if it can't be read."""
    t = normaliser(texte)
    try:
        return urllib.parse.urlsplit(t if "://" in t else "//" + t).hostname or ""
    except ValueError:
        return None


def racine(hote):
    """The registrable part of a host: app.foo.com -> foo.com, www.bbc.co.uk -> bbc.co.uk"""
    m = (hote or "").split(".")
    if len(m) >= 3 and len(m[-1]) == 2 and m[-2] in DEUXIEME_NIVEAU:
        return ".".join(m[-3:])
    return ".".join(m[-2:]) if len(m) >= 2 else ""


def sensible(texte):
    h = hote_de(texte) or ""
    if h.endswith(SUFFIXES):
        return True
    return any(m in part for part in h.split(".")[:-1] for m in MOTS)


def privee_litterale(h):
    if h is None:                        # what can't be read is not let through
        return True
    h = h.strip("[]").rstrip(".").lower()
    if h in ("localhost", "") or h.endswith((".local", ".localhost", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        try:                             # browsers also accept 127.1, 2130706433, 0x7f.1
            ip = ipaddress.ip_address(socket.inet_aton(h))
        except OSError:
            return False
    return not ip.is_global


def adresse_privee(url, resoudre=False):
    h = hote_de(url)
    if privee_litterale(h):
        return True
    if resoudre:
        try:
            return any(privee_litterale(i[4][0]) for i in socket.getaddrinfo(h, None))
        except (OSError, UnicodeError):
            return False
    return False


def clic_masque(demande, lu):
    """Asking for a piece of a label must not hide what the element really says."""
    return bool(RISQUE.search(lu or "")) and not RISQUE.search(demande or "")


def refus_url(url, resoudre=False):
    """Why this URL can't be opened, or None. A bare word passes: the command line refuses it."""
    t = normaliser(url)
    m = re.match(r"([a-z][a-z0-9+.-]*):(?!\d)", t)
    if m and m[1] not in ("http", "https"):
        return "Only http and https URLs are allowed."
    if adresse_privee(t, resoudre):
        return "Local addresses are refused."
    return None


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check-url":
        u = sys.argv[2]
        if not normaliser(u).startswith(("http://", "https://")):
            sys.exit("only http and https URLs are allowed")
        raison = refus_url(u, resoudre=True)
        if raison:
            sys.exit(raison)
    else:
        sys.exit(__doc__)
