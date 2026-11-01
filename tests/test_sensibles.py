import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import sensibles as s  # noqa: E402


class Sensibles(unittest.TestCase):
    def test_argent_et_identite(self):
        for u in ("https://www.chase.com/x", "paypal.com", "coinbase.com", "irs.gov",
                  "https://www.impots.gouv.fr", "1password.com", "mabanque.bnpparibas.fr"):
            self.assertTrue(s.sensible(u), u)

    def test_sites_normaux(self):
        for u in ("github.com", "notion.so", "https://mail.google.com", "shopify.com"):
            self.assertFalse(s.sensible(u), u)

    def test_prive(self):
        for u in ("http://10.0.0.1/", "http://[::1]/", "http://printer.local/"):
            self.assertTrue(s.adresse_privee(u), u)
        self.assertFalse(s.adresse_privee("https://example.com/"))


if __name__ == "__main__":
    unittest.main()
