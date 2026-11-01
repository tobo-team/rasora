import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import web  # noqa: E402


class Web(unittest.TestCase):
    def test_texte(self):
        t = web.texte_de("<html><head><title>x</title><script>evil()</script></head>"
                         "<body><p>Hello <b>world</b></p><nav>menu</nav></body></html>")
        self.assertIn("Hello world", t)
        self.assertNotIn("evil", t)
        self.assertNotIn("menu", t)

    def test_local_refuse(self):
        with self.assertRaises(web.Sortie):
            web.demander("http://127.0.0.1:9333/json")

    def test_schema_refuse(self):
        with self.assertRaises(web.Sortie):
            web.get("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
