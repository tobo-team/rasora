# Security

Rasora acts with your accounts, so here is exactly what it does and what it doesn't protect
you from. No agent is immune to prompt injection: this page tells you where the limits are.

## Report a vulnerability

Please use [private vulnerability reporting](https://github.com/vocalyagent/rasora/security/advisories/new),
not a public issue.

## What protects you

- **A guard outside the model** (`scripts/garde.py`). It is a Claude Code hook, so text on a
  page can't talk it out of acting. It asks you before clicks that pay, order, publish, send
  or delete, before filling card or password fields, and before changing what is allowed.
  With permissions switched off, it refuses instead of asking.
- **Forbidden outright.** Reading cookies or storage from a page, reading the bot profile or
  the Chrome key, and reaching local addresses such as the browser's debug port.
- **Sensitive sites stay out.** "Everywhere" mode skips banks, payment, crypto, password
  managers, health and government sites (`scripts/sensibles.py`). You can add one by name.
- **Page content is marked as untrusted** before the model reads it, and memory is presented
  as notes, not instructions.
- **Locked dependencies.** Exact versions and hashes, wheels only.
- **No server of ours.** No account, no telemetry. Sessions, memory and the key stay on your
  Mac. What does leave it: searches go to DuckDuckGo, pages are requested from their sites,
  and Claude sends what it reads to Anthropic, as with any tool you use with it.

## What it does on your Mac

- **It decrypts Chrome cookies** for allowed sites and copies them into a separate profile.
  Infostealers use the same mechanism. The difference is that this code is open and local.
- **Keychain.** macOS asks once. Click **Allow**, never **Always Allow**: that would give
  Chrome's key to every program that asks, even after you uninstall. Rasora keeps the key in
  a private file, `~/.rasora/.chrome-key`, and `rasora wipe` deletes it.
- **It keeps live sessions on disk**, in `~/.rasora/chrome-profile`, readable only by your
  macOS user.
- **It opens a Chrome debug port** on `127.0.0.1`.
- **It writes memory in plain files**, including one line per message you send to Claude.
  Lines that look like keys or passwords are skipped. That filter is simple, not a guarantee.
- **`rasora setup` edits `~/.claude/settings.json`** so Claude stops asking each time. A copy
  is kept, and `rasora wipe` removes the rules.

## What it does not protect you from

- **Other programs on your Mac.** Anything running as your user could reach the debug port,
  the profile or the key file. Don't install Rasora on a machine you don't trust.
- **Prompt injection.** The guard covers the riskiest actions, not all of them. A page could
  still trick the agent into reading something on a signed-in site, or submit a form with the
  Enter key. Stay around for sensitive work.
- **Word-based checks.** The guard looks for words like "Pay" or "Delete". A button with an
  unusual label can slip past it.
- **Site rules.** Copying sessions may go against some sites' terms, and a site may sign you
  out. Use your own accounts only.
- **Updates.** A plugin runs what its repository ships. Read the changes if you enable
  auto-update.

## Good habits

- Use site-by-site mode if you handle sensitive data: `rasora deny --all`, then allow.
- `rasora pause` the moment something looks wrong.
- `rasora wipe` to remove everything.
