# neverlogout

**Your AI agent never gets logged out.**

A separate Chrome your agent drives for you, signed in to the accounts you allow, working
in the background without taking over your screen. When a session dies, it repairs itself
from your everyday Chrome. No password is shared, and nothing leaves your Mac.

Built with Claude Code, by someone who can't code, to run a real online store.

> Demo video: coming soon.

## Why this exists

Agents are great until they hit a login: a site with no API, an expired session at 3 a.m.
Tools that attach to your open Chrome help, but they use your window and stop when you
close it. neverlogout gives the agent its own browser and keeps its sessions alive.

## Install

macOS with Google Chrome, signed in to your accounts. Read the script, then run it:

```bash
curl -fsSL https://raw.githubusercontent.com/vocalyagent/neverlogout/main/install.sh -o install.sh
less install.sh
bash install.sh
```

It asks site by site. **Nothing is allowed unless you say yes.** Everything lives in
`~/.neverlogout`, and your own Chrome is not touched.

## Use it

```bash
neverlogout sites            # sites found in Chrome, and which are allowed
neverlogout allow github     # let the agent use a site
neverlogout deny github      # forbid it and delete its cookies from the bot
neverlogout sessions         # which sessions are alive
neverlogout open https://github.com/notifications
neverlogout read github 2000
neverlogout wipe             # delete everything
```

If `neverlogout` is not found, use `~/.neverlogout/bin/neverlogout`.

### With Claude Code

The installer adds a skill. Ask: "open my GitHub notifications and summarize them".

### With any MCP client

```json
{
  "mcpServers": {
    "neverlogout": {
      "command": "/Users/YOU/.neverlogout/bin/neverlogout",
      "args": ["mcp"]
    }
  }
}
```

Running arbitrary JavaScript is not exposed over MCP, on purpose.

## How it works

- **A separate Chrome** on port 9333, with its own profile.
- **Borrowed sessions.** For allowed sites only, cookies are copied locally from the Chrome
  profile that holds the account. No password moves.
- **Stays out of the way.** Background guardians keep it hidden and give focus back to you.
- **Self-repair.** Every 20 minutes it tests allowed sessions and re-copies dead ones.
- **Driven by visible text** ("click Send"), so a moved banner breaks nothing.

## Security

This tool handles live sessions. Read [SECURITY.md](SECURITY.md) before installing.

## Limits

- macOS and Google Chrome only.
- Supported sites today: Gmail, Drive, YouTube, GitHub, Shopify, Notion, X, Instagram,
  TikTok, LinkedIn, Canva, Figma, Vercel.
- A 2FA prompt, a payment or a publish button stops there: those stay yours.

## License

MIT.
