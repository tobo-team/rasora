# neverlogout

**Your AI agent never gets logged out. It works like you do, in the background.**

Give your agent a real browser that stays signed in to your accounts. It goes anywhere you
can go, clicks through any site, remembers what it learned, and tries another way when
something fails. It runs on your Mac, with the Claude Code subscription you already pay for.

```bash
neverlogout do "open my GitHub notifications and summarize what needs a reply"
```

Built with Claude Code, by someone who can't code, to run a real online store.

> Demo video: coming soon.

## Why this exists

Agents are great until they hit the real web: a site with no API, an expired session at
3 a.m., a button that isn't where it should be. Most agents stop there and hand the work
back to you. This one takes another path.

- **Everywhere.** It uses the accounts you are signed in to in Chrome, on any site.
- **In the background.** Its own hidden Chrome. Your screen and your tabs stay yours.
- **Never logged out.** Dead sessions repair themselves from your everyday Chrome.
- **Remembers.** What worked on each site stays in plain files, and it reads them next time.
- **Finds another way.** Visible text, then iframes, keyboard, direct URLs, screenshots,
  JavaScript, then a different method altogether.
- **Cheap.** It reads text rather than screenshots, and there is no server or extra model.

## Install

macOS with Google Chrome, signed in to your accounts. Read the script, then run it:

```bash
curl -fsSL https://raw.githubusercontent.com/vocalyagent/neverlogout/main/install.sh -o install.sh
less install.sh
bash install.sh
```

It asks one question: use every account, or choose site by site. **Nothing is allowed unless
you say yes.** Everything lives in `~/.neverlogout`, and your own Chrome is not touched.

## Use it

```bash
neverlogout do "<task>"       # run a task in the background
neverlogout jobs              # list tasks
neverlogout job <id>          # see what a task did

neverlogout sites             # what is allowed
neverlogout allow foo.com     # allow one site
neverlogout allow --all       # allow everywhere
neverlogout deny foo.com      # forbid it and delete its cookies from the bot
neverlogout deny --all        # back to nothing

neverlogout recall stripe     # search what it remembers
neverlogout wipe              # delete everything
```

If `neverlogout` is not found, use `~/.neverlogout/bin/neverlogout`. Memory is plain Markdown
in `~/.neverlogout/memory`, so you can read and edit it.

### With Claude Code

The installer adds a skill, so you can also just ask in a normal session.

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

## Security

This tool acts with your accounts. Read [SECURITY.md](SECURITY.md) before installing.

## Limits

- macOS and Google Chrome only. Background tasks need Claude Code.
- A 2FA prompt or a CAPTCHA stops there: those stay yours.
- It asks before a payment, a publish button, a deletion or a message to a person, unless
  your request says to do exactly that.
- One real account for one real user. It is not a tool for fake or bulk sign-ups.

## License

MIT.
