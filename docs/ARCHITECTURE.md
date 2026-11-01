# Architecture

```
You talk to Claude
      |
      |-- SessionStart hook   sets up ~/.rasora, gives Claude its memory
      |-- UserPromptSubmit    keeps one line per message, locally
      |-- PreToolUse guard    outside the model: asks, or refuses
      |
   MCP tools / rasora command
      |
      |-- web.py        open data, then a plain request
      |-- nav.py        hidden Chrome, last resort or signed-in sites
      |-- sessions.py   repairs dead sessions from your Chrome
      |-- memoire.py    plain Markdown files
```

| Path | Role |
|---|---|
| `scripts/garde.py` | Confirms risky actions, refuses forbidden ones |
| `scripts/sensibles.py` | Sites left out by default, local address checks |
| `scripts/web.py` | Search and read without a browser |
| `scripts/nav.py` | Drives Chrome by visible text |
| `scripts/sessions.py` | Tests and repairs sessions |
| `scripts/configurer-sessions.py` | What is allowed |
| `scripts/memoire.py` | Memory |
| `scripts/mcp_server.py` | MCP tools, standard library only |
| `scripts/bootstrap.sh` | Silent setup in `~/.rasora` |
