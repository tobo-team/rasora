"""PNG size and cropping with what macOS ships, so a screenshot needs no image library."""
import os
import struct
import subprocess
import tempfile


def taille(brut):
    """(width, height) from the PNG header."""
    if brut[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", brut[16:24])


def recadrer(brut, x, y, w, h, sortie):
    """Write the box (x, y, w, h), in pixels, to `sortie`. The box is kept inside the image."""
    largeur, hauteur = taille(brut)
    x, y = min(max(0, int(x)), largeur - 1), min(max(0, int(y)), hauteur - 1)
    w, h = max(1, min(int(w), largeur - x)), max(1, min(int(h), hauteur - y))
    d = tempfile.mkdtemp()
    entree = os.path.join(d, "capture.png")
    try:
        with open(entree, "wb") as f:
            f.write(brut)
        subprocess.run(["/usr/bin/sips", "-c", str(h), str(w), "--cropOffset", str(y), str(x),
                        entree, "--out", sortie],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        if os.path.exists(entree):
            os.remove(entree)
        os.rmdir(d)
    return w, h
