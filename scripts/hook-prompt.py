#!/usr/bin/env python3
"""Reads the hook event on stdin and keeps one line per user message, locally."""
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.rasora/bin"))
try:
    import memoire
    e = json.load(sys.stdin)
    projet = "project-" + os.path.basename((e.get("cwd") or "general").rstrip("/"))
    texte = e.get("prompt") or ""
    if texte:
        memoire.journal(projet, texte)
        # What the user asks to keep is written here, not left to the model's goodwill.
        if (memoire.A_RETENIR.search(texte) and not memoire.SECRET.search(texte)
                and not texte.rstrip().endswith("?")):
            memoire.save(projet if "projet" in texte.lower() or "project" in texte.lower()
                         else "general", texte[:300])
except Exception:
    pass
