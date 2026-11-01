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
    if e.get("prompt"):
        memoire.journal(projet, e["prompt"])
except Exception:
    pass
