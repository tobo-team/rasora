import os
import struct
import sys
import tempfile
import unittest
import zlib

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts"))
import capture_png  # noqa: E402


def morceau(nature, data):
    return (struct.pack(">I", len(data)) + nature + data
            + struct.pack(">I", zlib.crc32(nature + data)))


def fabriquer(largeur, hauteur):
    """Each pixel encodes its own position: R = x, G = y. Any wrong offset shows."""
    lignes = b"".join(b"\0" + bytes(c for x in range(largeur) for c in (x, y, 0))
                      for y in range(hauteur))
    return (b"\x89PNG\r\n\x1a\n"
            + morceau(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
            + morceau(b"IDAT", zlib.compress(lignes)) + morceau(b"IEND", b""))


def pixel(brut, x, y):
    """Reads a pixel of a non-interlaced 8-bit PNG, undoing every filter sips may choose."""
    largeur, hauteur = capture_png.taille(brut)
    prof, couleur = brut[24], brut[25]
    assert prof == 8 and couleur in (2, 6)
    n = 3 if couleur == 2 else 4
    i, idat = 8, b""
    while i < len(brut):
        taille, nature = struct.unpack(">I", brut[i:i + 4])[0], brut[i + 4:i + 8]
        if nature == b"IDAT":
            idat += brut[i + 8:i + 8 + taille]
        i += 12 + taille
    d = zlib.decompress(idat)
    pas = largeur * n
    avant = bytearray(pas)
    for ligne in range(y + 1):
        f, brute = d[ligne * (pas + 1)], d[ligne * (pas + 1) + 1:(ligne + 1) * (pas + 1)]
        cur = bytearray(pas)
        for k in range(pas):
            a = cur[k - n] if k >= n else 0
            b = avant[k]
            c = avant[k - n] if k >= n else 0
            if f == 0:
                p = 0
            elif f == 1:
                p = a
            elif f == 2:
                p = b
            elif f == 3:
                p = (a + b) // 2
            else:
                t = a + b - c
                pa, pb, pc = abs(t - a), abs(t - b), abs(t - c)
                p = a if pa <= pb and pa <= pc else b if pb <= pc else c
            cur[k] = (brute[k] + p) & 255
        avant = cur
    return avant[x * n], avant[x * n + 1]


@unittest.skipUnless(os.path.exists("/usr/bin/sips"), "macOS only")
class Recadrage(unittest.TestCase):
    def couper(self, brut, *boite):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sortie.png")
            capture_png.recadrer(brut, *boite, p)
            with open(p, "rb") as f:
                return f.read()

    def test_taille(self):
        self.assertEqual(capture_png.taille(fabriquer(30, 20)), (30, 20))

    def test_pas_un_png(self):
        with self.assertRaises(ValueError):
            capture_png.taille(b"GIF89a" + b"\0" * 30)

    def test_boite_exacte(self):
        r = self.couper(fabriquer(120, 80), 37, 11, 25, 9)
        self.assertEqual(capture_png.taille(r), (25, 9))
        self.assertEqual(pixel(r, 0, 0), (37, 11))
        self.assertEqual(pixel(r, 24, 8), (61, 19))

    def test_boite_qui_deborde(self):
        r = self.couper(fabriquer(50, 40), 40, 30, 500, 500)
        self.assertEqual(capture_png.taille(r), (10, 10))
        self.assertEqual(pixel(r, 0, 0), (40, 30))

    def test_boite_hors_image(self):
        r = self.couper(fabriquer(50, 40), 900, 900, 10, 10)
        self.assertEqual(capture_png.taille(r), (1, 1))


if __name__ == "__main__":
    unittest.main()
