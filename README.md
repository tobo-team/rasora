# Rasora

**Hands and a memory for Claude. Install it, then forget it.**

You keep talking to Claude the way you always do. It just gets things done: it works on any
site where you are signed in, remembers what matters from one session to the next, and
tries another way when something fails. All of it in the background, on your Mac, with the
Claude subscription you already have.

Built by Camille and Micka, with Claude Code. Camille can't code.

> Demo video: coming soon.

## Install

Inside Claude Code:

```
/plugin install rasora --marketplace vocalyagent/rasora
```

That's it. There is no command to learn and nothing to mention. The first time a task needs
one of your accounts, Claude asks you once, in one sentence. macOS asks once for Keychain
access: click Always Allow. After that it stays out of your way.

Older Claude Code:

```
/plugin marketplace add vocalyagent/rasora
/plugin install rasora@rasora
```

macOS and Google Chrome required.

## What changes

- **It acts on the web.** Claude uses a hidden Chrome of its own, signed in to your accounts,
  on sites with no API. Your screen and tabs stay yours.
- **It never gets logged out.** Dead sessions repair themselves from your everyday Chrome.
- **It remembers.** Your preferences, your projects, what worked on each site, in plain
  Markdown files you can read and edit in `~/.rasora/memory`.
- **It finds another way.** Visible text, iframes, keyboard, direct URLs, screenshots,
  JavaScript, then a different method altogether.
- **It costs less to run.** It reads text rather than screenshots. There is no server or
  extra model: only your own Claude subscription.

It asks before a payment, a publish button, a deletion or a message to a person, unless
your request says to do exactly that. A 2FA prompt or a CAPTCHA stays yours.

## If you want to look under the hood

```bash
rasora sites             # what is allowed
rasora allow foo.com     # allow one site
rasora deny foo.com      # forbid it and delete its cookies from the bot
rasora deny --all        # back to nothing
rasora recall stripe     # search the memory
rasora do "<task>"       # run a task in the background
rasora wipe              # delete everything
```

## Other MCP clients

Run [install.sh](install.sh) after reading it, then add this server:

```json
{ "mcpServers": { "rasora": { "command": "/Users/YOU/.rasora/bin/rasora", "args": ["mcp"] } } }
```

## Security

Rasora acts with your accounts. Read [SECURITY.md](SECURITY.md) before installing.

## License

MIT.
