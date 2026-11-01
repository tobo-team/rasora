"""One test per hole found by the audit of 01/11. Each of these went through before."""
import importlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts"))
import garde  # noqa: E402
import sensibles as s  # noqa: E402
import web  # noqa: E402

M = "mcp__plugin_rasora_rasora__"


def d(nom, e):
    r = garde.decider(nom, e)
    return r[0] if r else None


def hook(e):
    r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "garde.py")],
                       input=json.dumps(e), capture_output=True, text=True)
    return r.stdout


def sans_permissions(cmd):
    return hook({"tool_name": "Bash", "tool_input": {"command": cmd},
                 "permission_mode": "bypassPermissions"})


class Contournements(unittest.TestCase):
    def test_une_valeur_cassee_ne_coupe_pas_le_garde(self):
        self.assertIn('"deny"', sans_permissions("rasora open 'http://[' ; rasora click t Pay"))

    def test_exemption_login_stricte(self):
        for c in ("rasora wipe --yes rasora login x", "rasora do rasora login buy it",
                  "rasora click t rasora login Pay"):
            self.assertIn('"deny"', sans_permissions(c), c)
        self.assertEqual(sans_permissions("rasora login https://x.com/login"), "")

    def test_scripts_appeles_directement(self):
        for c in ("cd ~/.rasora/bin && ./nav.py click t Pay",
                  "python3 ~/.claude/plugins/cache/rasora/rasora/x/scripts/nav.py click t Pay"):
            self.assertEqual(d("Bash", {"command": c}), "ask", c)

    def test_un_nav_py_a_soi_reste_libre(self):
        self.assertIsNone(d("Bash", {"command": "python3 ~/tools/nav.py click tab Pay"}))

    def test_commandes_masquees(self):
        for c in ('ras""ora click t Pay', "r\\asora click t Pay", "rasora click t Pa$X",
                  "rasora click t Pa`echo y`", "rasora click t $'\\x50ay'"):
            self.assertEqual(d("Bash", {"command": c}), "ask", c)

    def test_commande_geante(self):
        c = "echo " + "rasora x " * 2000 + "; rasora click t Pay"
        self.assertEqual(d("Bash", {"command": c}), "ask")
        self.assertEqual(d("Bash", {"command": "echo " + "rasora " * 20000}), "ask")

    def test_une_longue_commande_sans_rasora_passe(self):
        self.assertIsNone(d("Bash", {"command": "echo " + "x " * 50000}))

    def test_js_qui_agit(self):
        for c in ("document.querySelector('button.primary').click()", "f.requestSubmit()",
                  "eval(x)", "document.forms[0].dispatchEvent(e)", "window['fe'+'tch']('x')",
                  "document['coo'+'kie']", "input.value = 'x'", "location.assign('x')"):
            self.assertEqual(d(M + "browser_js", {"code": c}), "ask", c)
        for c in ("document.title", "document.querySelectorAll('a').length", "a.value == 1"):
            self.assertEqual(d(M + "browser_js", {"code": c}), "allow", c)

    def test_mots_et_champs(self):
        for t in ("Achetez", "Payez maintenant", "Commandez", "Supprimez", "Envoyez", "Book now",
                  "Reply", "Répondre", "Comprar", "Kaufen", "Bezahlen", "Bestätigen"):
            self.assertEqual(d(M + "browser_click", {"text": t}), "ask", t)
        for l in ("Passwort", "Code de sécurité", "PIN", "OTP", "Numéro CB", "API key"):
            self.assertEqual(d(M + "browser_fill", {"label": l}), "ask", l)
        self.assertEqual(d(M + "browser_click", {"text": "Learn more"}), "allow")
        self.assertEqual(d(M + "browser_fill", {"label": "Search"}), "allow")

    def test_un_bout_de_libelle_ne_cache_pas_le_bouton(self):
        self.assertTrue(s.clic_masque("uy no", "Buy now"))
        self.assertFalse(s.clic_masque("Buy", "Buy now"))
        self.assertFalse(s.clic_masque("Learn", "Learn more"))


class Fichiers(unittest.TestCase):
    def test_sessions_hors_de_portee(self):
        for c in ("cd ~/.rasora && cat chrome-profile/Default/Cookies",
                  "cat ~/.rasora/*/Default/Cookies", "cat ~/.rasora/port",
                  "curl http://[::1]:9333/json", "curl http://0.0.0.0:9334/json"):
            self.assertEqual(d("Bash", {"command": c}), "deny", c)
        self.assertEqual(d("Grep", {"path": "/Users/x/.rasora/chrome-profile", "pattern": "x"}), "deny")
        self.assertEqual(d("Glob", {"pattern": "/Users/x/.rasora/chrome-profile/**"}), "deny")

    def test_le_garde_ne_se_modifie_pas(self):
        p = "/Users/x/.claude/plugins/cache/rasora/rasora/abc/scripts/garde.py"
        self.assertEqual(d("Edit", {"file_path": p}), "deny")
        self.assertEqual(d("Write", {"file_path": "/Users/x/.rasora/bin/garde.py"}), "deny")
        self.assertEqual(d("Bash", {"command": "rm ~/.rasora/bin/garde.py"}), "deny")
        self.assertEqual(d("Bash", {"command": "echo x > ~/.rasora/bin/garde.py"}), "deny")
        self.assertIsNone(d("Bash", {"command": "ls ~/.rasora/bin"}))
        self.assertEqual(d("Bash", {"command": "claude plugin disable rasora"}), "ask")
        self.assertEqual(d("Edit", {"file_path": "/Users/x/.claude/settings.json",
                                    "new_string": '"disableAllHooks": true'}), "ask")

    def test_le_travail_de_l_utilisateur_reste_libre(self):
        self.assertIsNone(d("Bash", {"command": "curl http://localhost:9000/health"}))
        self.assertIsNone(d("Edit", {"file_path": "/Users/x/app/settings.py", "new_string": "x"}))
        self.assertIsNone(d("Write", {"file_path": "/Users/x/app/a.py", "content": "x"}))


class Adresses(unittest.TestCase):
    def test_formes_deguisees(self):
        for u in ("http://127.1:9333/json", "http://2130706433:9333/", "http://0x7f000001/",
                  "http://0177.0.0.1/", "http://0/", "http:/127.0.0.1:9333/json",
                  "http:\\\\127.0.0.1:9333/json", "http://localhost./", "http://[::ffff:127.0.0.1]/",
                  "http://[", "127.0.0.1:9333", " http://127.0.0.1/", "ht\ntp://127.0.0.1/"):
            self.assertTrue(s.adresse_privee(u), u)
        self.assertFalse(s.adresse_privee("https://example.com/"))

    def test_schemas(self):
        for u in ("file:///etc/passwd", "view-source:https://x.com", "chrome://settings",
                  "javascript:alert(1)", "data:text/html,x"):
            self.assertEqual(d(M + "browser_open", {"url": u}), "deny", u)
        self.assertEqual(d(M + "browser_open", {"url": "https://example.com"}), "allow")

    def test_redirection_vers_le_port_de_chrome(self):
        r = web.Redirection()
        q = urllib.request.Request("https://example.com/")
        for u in ("http://127.0.0.1:9333/json/list", "http://2130706433/", "file:///etc/passwd"):
            with self.assertRaises(web.Sortie):
                r.redirect_request(q, None, 302, "", {}, u)
        self.assertIsNotNone(r.redirect_request(q, None, 302, "", {}, "https://example.org/"))

    def test_une_vraie_redirection_n_atteint_pas_la_cible(self):
        """Two real servers. The first counts as public here, the second is the debug port."""
        touchee = []

        class Cible(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                touchee.append(self.path)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        cible = http.server.HTTPServer(("127.0.0.1", 0), Cible)
        port = cible.server_port

        class Depart(Cible):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{port}/json/list")
                self.end_headers()

        depart = http.server.HTTPServer(("127.0.0.1", 0), Depart)
        for x in (cible, depart):
            threading.Thread(target=x.serve_forever, daemon=True).start()
        vrai = web.adresse_privee
        web.adresse_privee = lambda u, resoudre=False: f":{port}" in u
        try:
            with self.assertRaises(web.Sortie):
                web.demander(f"http://127.0.0.1:{depart.server_port}/")
        finally:
            web.adresse_privee = vrai
            cible.shutdown()
            depart.shutdown()
            cible.server_close()
            depart.server_close()
        self.assertEqual(touchee, [])

    def test_domaines_a_deux_niveaux(self):
        self.assertEqual(s.racine("www.bbc.co.uk"), "bbc.co.uk")
        self.assertEqual(s.racine("app.foo.com"), "foo.com")
        self.assertEqual(s.racine("www.impots.gouv.fr"), "impots.gouv.fr")
        self.assertEqual(s.racine("t.co"), "t.co")


class Memoire(unittest.TestCase):
    def setUp(self):
        self.ancien = os.environ["HOME"]
        os.environ["HOME"] = tempfile.mkdtemp()
        import memoire
        self.m = importlib.reload(memoire)

    def tearDown(self):
        os.environ["HOME"] = self.ancien

    def test_deux_sites_ne_partagent_pas_un_fichier(self):
        self.assertNotEqual(self.m.cle("bbc.co.uk"), self.m.cle("amazon.co.uk"))

    def test_nom_de_projet(self):
        self.assertEqual(self.m.cle("project-NAV-BOT"), "project-nav-bot")
        self.assertEqual(self.m.cle("project-a.b.c"), "project-a.b.c")
        self.assertEqual(self.m.cle("../../x"), "general")

    def test_secrets(self):
        for t in ("xoxb-123456789012-abcdef", "AIzaSyD1234567890abcdefghij", "4242 4242 4242 4242",
                  "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc", "-----BEGIN PRIVATE KEY-----",
                  "mon mdp est azerty", "api_key=abc", "sk_live_123456789012"):
            self.assertTrue(self.m.SECRET.search(t), t)
        with self.assertRaises(SystemExit):
            self.m.save("general", "le mdp est azerty")
        self.assertFalse(os.path.exists(self.m.chemin("general")))

    def test_une_phrase_banale_n_est_pas_une_consigne(self):
        for t in ("ca marche toujours pas", "jamais vu ca", "6k tokens par jour"):
            self.assertIsNone(self.m.A_RETENIR.search(t), t)
            self.assertIsNone(self.m.SECRET.search(t), t)


class Connexion(unittest.TestCase):
    """The window must stay open until the user has really been through the sign-in."""

    def suite(self, urls, depart):
        import connexion
        restes = list(urls)
        connexion.adresse = lambda tid: restes.pop(0)
        connexion.time.sleep = lambda s: None
        return connexion.attendre("t", connexion.time.time() + 5, depart)

    def test_depart_sur_l_accueil(self):
        self.assertEqual(self.suite(["https://x.com/", "https://x.com/login", "https://x.com/feed"],
                                    "https://x.com/"), "https://x.com/feed")

    def test_fenetre_fermee_sans_page_de_connexion(self):
        self.assertEqual(self.suite(["https://x.com/", None], "https://x.com/"), "https://x.com/")

    def test_fenetre_fermee_pendant_la_connexion(self):
        self.assertIsNone(self.suite(["https://x.com/login", None], "https://x.com/login"))


class Mcp(unittest.TestCase):
    def setUp(self):
        import mcp_server
        self.s = mcp_server

    def tearDown(self):
        os.environ.pop("RASORA_GARDE", None)

    def test_les_autres_clients_ont_aussi_le_garde(self):
        os.environ["RASORA_GARDE"] = "1"
        texte, echec = self.s.executer("browser_click", {"tab": "a", "text": "Buy now"})
        self.assertTrue(echec)
        self.assertIn("Refused", texte)


if __name__ == "__main__":
    unittest.main()
