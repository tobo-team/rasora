<p align="center">
  <img src="assets/banner.svg" alt="Rasora: hands and a memory for Claude" width="100%">
</p>

<p align="center">
  <a href="https://github.com/vocalyagent/rasora/actions/workflows/ci.yml"><img src="https://github.com/vocalyagent/rasora/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/macOS-Chrome-lightgrey" alt="macOS and Chrome">
  <img src="https://img.shields.io/badge/telemetry-none-brightgreen" alt="No telemetry">
</p>

You keep talking to Claude the way you always do. It just gets more done: it finds things on
the web, works on sites where you are signed in, remembers what matters from one session to
the next, and tries another way when something fails. All in the background, on your Mac,
with the Claude subscription you already have.

## Install

Inside Claude Code:

```
/plugin marketplace add vocalyagent/rasora
/plugin install rasora@rasora
```

That's it. There is no command to learn and nothing to mention. The first time a task needs
one of your accounts, a small window opens: you sign in once, by hand, and it hides itself.

## What changes

| | |
|---|---|
| **Works on the web** | Search and reading first, a hidden Chrome only when a site needs it. Your screen and tabs stay yours. |
| **Stays signed in** | You sign in once per site in its own Chrome, and it stays there for as long as the site allows. |
| **Remembers** | Your preferences, your projects, what worked on each site, in Markdown files you can read. |
| **Finds another way** | Visible text, iframes, keyboard, direct links, screenshots, then a different method altogether. |
| **Costs less** | Text rather than screenshots, Chrome last. No extra model. |

## Built to be safe

An agent that acts with your accounts can be tricked by a web page, so safety doesn't rely
on the model behaving:

- **A guard outside the model** stops before payments, publishing, deleting and messages,
  and asks you. Page text can't talk it out of it.
- **It never touches your everyday Chrome.** No reading your cookies, your passwords or your
  Keychain. It only knows the sites you signed in to in its own window.
- **You type your own passwords.** The agent never sees them.
- **Sessions stay out of reach.** Pages can't read cookies, and local addresses are refused.
- **No server of ours.** No account, no telemetry. Your sessions and memory stay on your Mac.
- **Stop at any time.** `rasora pause` freezes it, `rasora wipe` removes everything.

No agent is immune to prompt injection. Read [SECURITY.md](SECURITY.md) to see exactly what
Rasora does and doesn't protect you from.

## Under the hood

You never need these, but you can look:

```bash
rasora sites             # sites you signed in to
rasora login <url>       # sign in to a site by hand
rasora logout foo.com    # sign out and delete its cookies
rasora recall stripe     # search the memory
rasora do "<task>"       # run a task in the background
rasora pause             # freeze everything
rasora wipe              # delete everything
```

Other MCP clients: run [install.sh](install.sh) after reading it, then use
`~/.rasora/bin/rasora mcp`. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Who made this

Camille and Micka, with Claude Code. Camille can't code. Rasora began as the setup that
runs a real online store.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).
