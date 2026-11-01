# Working on Rasora

- Layout: `scripts/` is the product, `hooks/` and `.mcp.json` plug it into Claude Code,
  `skills/` teaches Claude, `tests/` runs without a browser or network.
- Run `python -m unittest discover -s tests` before any change.
- Never weaken `scripts/garde.py` or `scripts/sensibles.py` to make a task pass.
- Sessions and memory never leave the user's machine. No telemetry.
- Dependencies stay pinned with hashes in `scripts/requirements.lock`.
