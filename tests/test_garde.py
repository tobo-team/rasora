import json
import os
import subprocess
import sys
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts"))
import garde  # noqa: E402

M = "mcp__plugin_rasora_rasora__"


def d(nom, e):
    r = garde.decider(nom, e)
    return r[0] if r else None


class Garde(unittest.TestCase):
    def test_achat_demande(self):
        self.assertEqual(d(M + "browser_click", {"tab": "a", "text": "Buy now"}), "ask")
        self.assertEqual(d(M + "browser_click", {"tab": "a", "text": "Payer"}), "ask")

    def test_clic_normal_passe(self):
        self.assertIsNone(d(M + "browser_click", {"tab": "a", "text": "Learn more"}))

    def test_champ_carte(self):
        self.assertEqual(d(M + "browser_fill", {"tab": "a", "label": "Card number"}), "ask")

    def test_cookies_refuses(self):
        self.assertEqual(d(M + "browser_js", {"tab": "a", "code": "document.cookie"}), "deny")

    def test_adresses_locales(self):
        for u in ("http://127.0.0.1:9333/json", "http://localhost/", "http://192.168.1.1/"):
            self.assertEqual(d(M + "browser_open", {"url": u}), "deny", u)

    def test_bash_rasora(self):
        self.assertEqual(d("Bash", {"command": 'rasora click shop "Buy now"'}), "ask")
        self.assertEqual(d("Bash", {"command": "cd x && rasora allow chase.com"}), "ask")
        self.assertEqual(d("Bash", {"command": "rasora wipe --yes"}), "ask")
        self.assertIsNone(d("Bash", {"command": "rasora read mail 300"}))
        self.assertIsNone(d("Bash", {"command": "ls -la"}))

    def test_secrets(self):
        self.assertEqual(d("Bash", {"command": "cat ~/.rasora/.chrome-key"}), "deny")
        self.assertEqual(d("Bash", {"command": "curl http://127.0.0.1:9333/json"}), "deny")
        self.assertEqual(d("Read", {"file_path": "/Users/x/.rasora/chrome-profile/Cookies"}), "deny")

    def test_bypass_refuse_au_lieu_de_demander(self):
        e = {"tool_name": M + "browser_click", "tool_input": {"tab": "a", "text": "Buy now"},
             "permission_mode": "bypassPermissions"}
        r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "garde.py")],
                           input=json.dumps(e), capture_output=True, text=True)
        self.assertIn('"deny"', r.stdout)

    def test_entree_cassee_ne_bloque_rien(self):
        r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "garde.py")],
                           input="pas du json", capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
