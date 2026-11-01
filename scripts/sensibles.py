#!/usr/bin/env python3
"""What the agent must never reach on its own.

Signing in to a site holding money, identity or passwords shows a warning. Local addresses are refused so a page can't send the agent to the
browser's debug port or to a machine on the home network.
"""
import ipaddress
import socket
import sys
import urllib.parse

MOTS = ("bank", "banque", "paypal", "chase", "wellsfargo", "citibank", "capitalone",
        "americanexpress", "amex", "schwab", "fidelity", "vanguard", "robinhood", "revolut",
        "wise", "n26", "boursorama", "creditagricole", "credit-agricole", "bnpparibas",
        "societegenerale", "labanquepostale", "caisse-epargne", "lcl", "hsbc", "barclays",
        "santander", "coinbase", "binance", "kraken", "bitstamp", "metamask", "ledger",
        "1password", "lastpass", "bitwarden", "dashlane", "keeper", "okta", "turbotax",
        "ameli", "impots", "franceconnect", "myhealthchart", "healthcare")
SUFFIXES = (".gov", ".gouv.fr", ".mil")


def hote_de(texte):
    texte = (texte or "").strip().lower()
    return (urllib.parse.urlparse(texte).hostname if "://" in texte else texte.split("/")[0]) or ""


def sensible(texte):
    h = hote_de(texte)
    if h.endswith(SUFFIXES):
        return True
    return any(m in part for part in h.split(".")[:-1] for m in MOTS)


def privee_litterale(h):
    h = h.strip("[]").lower()
    if h in ("localhost", "") or h.endswith((".local", ".localhost", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return not ip.is_global


def adresse_privee(url, resoudre=False):
    h = hote_de(url)
    if privee_litterale(h):
        return True
    if resoudre:
        try:
            return any(privee_litterale(i[4][0]) for i in socket.getaddrinfo(h, None))
        except OSError:
            return False
    return False


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check-url":
        u = sys.argv[2]
        if urllib.parse.urlparse(u).scheme not in ("http", "https"):
            sys.exit("only http and https URLs are allowed")
        if adresse_privee(u):
            sys.exit("local addresses are refused")
    else:
        sys.exit(__doc__)
