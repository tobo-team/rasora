import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))


class Memoire(unittest.TestCase):
    def setUp(self):
        os.environ["HOME"] = tempfile.mkdtemp()
        import memoire
        self.m = importlib.reload(memoire)

    def test_cle(self):
        self.assertEqual(self.m.cle("https://app.foo.com/x"), "foo.com")
        self.assertEqual(self.m.cle("general"), "general")

    def test_secrets_ecartes(self):
        self.m.journal("project-a", "my password is hunter2")
        self.m.journal("project-a", "key sk-abcdefghijklmnop")
        self.assertFalse(os.path.exists(os.path.join(self.m.RACINE, "journal", "project-a.md")))

    def test_a_retenir(self):
        for x in ("je prefere des reponses courtes", "garde ca en tete", "remember this"):
            self.assertTrue(self.m.A_RETENIR.search(x), x)
        self.assertFalse(self.m.A_RETENIR.search("ouvre mon gmail"))

    def test_journal_garde_le_reste(self):
        self.m.journal("project-a", "fix the login page")
        p = os.path.join(self.m.RACINE, "journal", "project-a.md")
        self.assertIn("fix the login page", open(p).read())


if __name__ == "__main__":
    unittest.main()
