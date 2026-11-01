#!/usr/bin/env python3
"""The one yes: stop Claude Code asking each time. `add` or `remove`.

A plugin cannot grant permissions, so `rasora setup` writes these rules in the user's
~/.claude/settings.json, keeps a copy of the file, and `rasora wipe` takes them back out.
"""
import json
import os
import shutil
import sys

CHEMIN = os.path.expanduser("~/.claude/settings.json")
REGLES = ["Bash(rasora:*)", "mcp__plugin_rasora_rasora"]


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in ("add", "remove"):
        sys.exit(__doc__)
    if os.environ.get("RASORA_NO_SETTINGS") == "1":
        return
    d = {}
    if os.path.exists(CHEMIN):
        d = json.load(open(CHEMIN, encoding="utf-8"))
        shutil.copy2(CHEMIN, os.path.expanduser("~/.rasora/settings.avant.json"))
    os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
    regles = d.setdefault("permissions", {}).setdefault("allow", [])
    if action == "add":
        regles += [r for r in REGLES if r not in regles]
    else:
        d["permissions"]["allow"] = [r for r in regles if r not in REGLES]
    tmp = CHEMIN + ".rasora"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, CHEMIN)
    print(f"  Claude Code settings updated ({action})")


if __name__ == "__main__":
    main()
