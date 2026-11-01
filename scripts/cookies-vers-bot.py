#!/usr/bin/env python3
"""Greffe la session Google d'un profil du Chrome personnel dans le navigateur bot.

Pourquoi (21/08/2026) : le bot avait perdu sa session Google et ne peut pas en
reprendre une, `accounts.google.com` retombe sur l'ecran de connexion des qu'il
detecte un navigateur pilote. Le Chrome personnel, lui, a la session ; et son
Chrome ne peut pas etre relance en CDP sans le deranger. On deplace donc les
cookies, pas l'humain.

Rien ne sort de la machine : on lit le fichier Cookies du profil (SQLite,
chiffre AES-128-CBC avec une cle du Trousseau), on dechiffre, on pose les
cookies dans le bot par CDP. Le bot n'a pas besoin d'etre redemarre.

  cookies-vers-bot.py "Profile 2" domain [domain ...]

Only the domains named here are read. There is no default on purpose: nothing is
copied unless the user allowed that site (see `rasora allow`).
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = int(os.environ.get("CDP_PORT", "9333"))
CACHE = os.path.expanduser("~/.rasora/.chrome-key")
CHROME = os.path.expanduser("~/Library/Application Support/Google/Chrome")


def cle():
    """Chrome's key, asked once. "Always Allow" on the Keychain prompt would hand it to
    every program that calls `security`, for good. A single "Allow" plus this private
    file means only this tool keeps it, and `rasora wipe` destroys it."""
    if os.path.exists(CACHE):
        return bytes.fromhex(open(CACHE).read().strip())
    mdp = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]
    ).strip()
    k = hashlib.pbkdf2_hmac("sha1", mdp, b"saltysalt", 1003, 16)
    fd = os.open(CACHE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(k.hex())
    return k


def dechiffrer(blob, cle_de):
    """`cle_de` is called only for an encrypted value, so Keychain stays untouched
    when there is nothing to decrypt."""
    if not blob:
        return ""
    if blob[:3] not in (b"v10", b"v11"):
        return blob.decode("utf-8", "replace")
    d = Cipher(algorithms.AES(cle_de()), modes.CBC(b" " * 16)).decryptor()
    clair = d.update(blob[3:]) + d.finalize()
    clair = clair[: -clair[-1]] if clair and clair[-1] <= 16 else clair
    # Chrome recent prefixe la valeur par le SHA256 du domaine, 32 octets
    try:
        return clair.decode("utf-8")
    except UnicodeDecodeError:
        return clair[32:].decode("utf-8", "replace")


def lire(profil, domaines):
    src = os.path.join(CHROME, profil, "Cookies")
    if not os.path.exists(src):
        sys.exit(f"no Cookies file in {profil}")
    tmp = tempfile.mkdtemp()
    copie = os.path.join(tmp, "Cookies")
    shutil.copy2(src, copie)
    for suffixe in ("-wal", "-shm"):
        if os.path.exists(src + suffixe):
            shutil.copy2(src + suffixe, copie + suffixe)
    memo = []

    def k():
        if not memo:
            memo.append(cle())
        return memo[0]

    con = sqlite3.connect(f"file:{copie}?mode=ro", uri=True)
    # "*.foo.com" = foo.com and every subdomain, for sites without a recipe.
    conditions, params = [], []
    for d in domaines:
        if d.startswith("*."):
            conditions.append("host_key = ? OR host_key LIKE ?")
            params += [d[2:], "%." + d[2:]]
        else:
            conditions.append("host_key = ? OR host_key = ?")
            params += [d, d.lstrip(".")]
    ou = " OR ".join(conditions)
    lignes = con.execute(
        "SELECT host_key,name,encrypted_value,path,expires_utc,is_secure,"
        "is_httponly,samesite FROM cookies WHERE " + ou, params
    ).fetchall()
    con.close()
    shutil.rmtree(tmp, ignore_errors=True)

    out = []
    for host, nom, chiffre, chemin, exp, sec, http, same in lignes:
        val = dechiffrer(chiffre, k)
        if not val:
            continue
        # sans `url`, CDP rejette en silence tout cookie Secure ou httpOnly :
        # c'est ce qui faisait echouer la greffe sans le dire (21/08/2026).
        c = {"name": nom, "value": val, "domain": host, "path": chemin or "/",
             "secure": bool(sec), "httpOnly": bool(http),
             "url": "https://" + host.lstrip(".") + (chemin or "/")}
        if exp:  # microsecondes depuis 1601 -> secondes depuis 1970
            c["expires"] = exp / 1_000_000 - 11644473600
        if same == 2:
            c["sameSite"] = "Strict"
        elif same == 1:
            c["sameSite"] = "Lax"
        elif c["secure"]:
            c["sameSite"] = "None"
        out.append(c)
    return out


def poser(cookies):
    ws_url = json.load(
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version")
    )["webSocketDebuggerUrl"]
    import websocket

    ws = websocket.create_connection(ws_url, timeout=30)
    poses, refuses = 0, []
    for i, c in enumerate(cookies, start=1):
        # un par un : Storage.setCookies en lot ne dit jamais lequel a echoue
        ws.send(json.dumps({"id": i, "method": "Storage.setCookies",
                            "params": {"cookies": [c]}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == i:
                break
        if "error" in r:
            refuses.append((c["name"], r["error"].get("message", "")))
        else:
            poses += 1
    ws.close()
    return poses, refuses


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    profil, domaines = sys.argv[1], sys.argv[2:]
    cookies = lire(profil, domaines)
    if not cookies:
        sys.exit("no cookie read, wrong profile?")
    poses, refuses = poser(cookies)
    print(f"{poses}/{len(cookies)} cookies copied from {profil}")
    for nom, pourquoi in refuses:
        print(f"  refused: {nom} ({pourquoi})")


if __name__ == "__main__":
    main()
