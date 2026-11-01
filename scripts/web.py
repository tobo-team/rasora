#!/usr/bin/env python3
"""The cheap way to read the web. Chrome is the last resort, not the default.

  web.py search <words>     search the web
  web.py get <url> [n]      read a page, using the lightest route that works

Route for a page: a site's own open data, then a plain request, then the hidden Chrome if
the page needs JavaScript or refuses plain requests. Standard library only.
"""
import html
import html.parser
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from sensibles import adresse_privee  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0 Safari/537.36")
BLOQUE = re.compile(r"enable javascript|verify you are human|just a moment|access denied|"
                    r"captcha|unusual traffic", re.I)


class Sortie(RuntimeError):
    pass


class Page(html.parser.HTMLParser):
    IGNORE = {"script", "style", "noscript", "svg", "template", "nav", "footer", "head"}
    BLOC = {"p", "div", "li", "h1", "h2", "h3", "h4", "tr", "br", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.cache = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORE:
            self.cache += 1
        elif tag in self.BLOC:
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORE and self.cache:
            self.cache -= 1

    def handle_data(self, data):
        if not self.cache and data.strip():
            self.morceaux.append(" ".join(data.split()) + " ")


def texte_de(contenu):
    p = Page()
    p.feed(contenu)
    return re.sub(r"\n\s*\n+", "\n", "".join(p.morceaux)).strip()


class Redirection(urllib.request.HTTPRedirectHandler):
    """Each hop is checked: a public page could otherwise send us to the browser's debug port."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith(("http://", "https://")) \
                or adresse_privee(newurl, resoudre=True):
            raise Sortie("a redirect led to a local address: refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OUVREUR = urllib.request.build_opener(Redirection)


def demander(url, donnees=None):
    if adresse_privee(url, resoudre=True):
        raise Sortie("local addresses are refused")
    req = urllib.request.Request(url, data=donnees, headers={"User-Agent": UA,
                                                             "Accept-Language": "en-US,en"})
    with OUVREUR.open(req, timeout=20) as r:
        return r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")


def reddit(url):
    u = urllib.parse.urlparse(url)
    d = json.loads(demander(f"https://www.reddit.com{u.path.rstrip('/')}.json?limit=30"))
    posts = []

    def lire(x):
        if isinstance(x, list):
            for i in x:
                lire(i)
        elif isinstance(x, dict):
            data = x.get("data", {})
            if data.get("title") or data.get("body"):
                posts.append(f"{data.get('author', '')}: {data.get('title', '')} "
                             f"{data.get('selftext') or data.get('body') or ''}".strip())
            lire(data.get("children", []))
            lire(data.get("replies") or [])
    lire(d)
    return "\n".join(posts)


def github(url):
    m = re.match(r"https://github\.com/([^/]+)/([^/?#]+)/?$", url)
    if not m:
        return None
    return demander(f"https://raw.githubusercontent.com/{m[1]}/{m[2]}/HEAD/README.md")


def navigateur(url, n):
    cli = os.path.join(ICI, "rasora")
    env = dict(os.environ, RASORA_BRUT="1")      # marked once, by the outer command
    a = subprocess.run(["/bin/bash", cli, "open", url], capture_output=True, text=True,
                       timeout=90, env=env)
    if a.returncode:
        raise Sortie("the browser could not open it")
    tab = re.search(r"#[0-9a-f]{6}", a.stdout)
    r = subprocess.run(["/bin/bash", cli, "read", tab[0] if tab else url, str(n)],
                       capture_output=True, text=True, timeout=60, env=env)
    return r.stdout


def get(url, n=8000):
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise Sortie("only http and https URLs are allowed")
    hote = urllib.parse.urlparse(url).hostname or ""
    try:
        t = None
        if hote == "reddit.com" or hote.endswith(".reddit.com"):
            t = reddit(url)
        elif hote == "github.com":
            t = github(url)
        if not t:
            t = texte_de(demander(url))
        if len(t) > 150 and not BLOQUE.search(t[:600]):
            return t[:n]
    except Sortie:
        raise
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        pass
    return navigateur(url, n)


def chercher(mots):
    q = urllib.parse.urlencode({"q": " ".join(mots)}).encode()
    page = demander("https://html.duckduckgo.com/html/", q)
    sortie = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                         r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S):
        lien = html.unescape(m[1])
        cible = urllib.parse.parse_qs(urllib.parse.urlparse(lien).query).get("uddg", [lien])[0]
        titre, extrait = (texte_de(x) for x in (m[2], m[3]))
        sortie.append(f"{titre}\n{cible}\n{extrait}\n")
        if len(sortie) == 8:
            break
    return "\n".join(sortie)


def main():
    a = sys.argv[1:]
    try:
        if len(a) >= 2 and a[0] == "search":
            r = chercher(a[1:])
            if not r:
                q = urllib.parse.quote(" ".join(a[1:]))
                r = navigateur(f"https://duckduckgo.com/?q={q}", 6000)
            print(r)
        elif len(a) >= 2 and a[0] == "get":
            print(get(a[1], int(a[2]) if len(a) > 2 else 8000))
        else:
            sys.exit(__doc__)
    except Sortie as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
