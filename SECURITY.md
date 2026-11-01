# Security

Rasora acts with your accounts, so here is exactly what it does and what it doesn't protect
you from. No agent is immune to prompt injection: this page tells you where the limits are.

## Report a vulnerability

Please use [private vulnerability reporting](https://github.com/vocalyagent/rasora/security/advisories/new),
not a public issue.

## What protects you

- **It stays away from your everyday Chrome.** Rasora never reads its cookies, its passwords
  or your Keychain. It has its own Chrome profile.
- **You sign in yourself.** `rasora login` shows a window and you type your own password and
  codes. The agent never sees them. Signing in to a site is how you allow it.
- **Saved passwords stay in Chrome.** If you click Save, Rasora's own Chrome keeps the password
  and fills in the page. The agent only presses the button. It is forbidden from looking for
  passwords in files, apps or the Keychain.
- **A guard outside the model** (`scripts/garde.py`). It is a Claude Code hook, so text on a
  page can't talk it out of acting. It asks you before clicks that pay, order, publish, send
  or delete, before filling card or password fields, and before opening a sign-in window.
  With permissions switched off, it refuses instead of asking. If it can't read a call, or the
  call is too long to read in time, it asks.
- **A second check at the moment of acting** (`scripts/nav.py`). Whatever was asked for, it
  looks at the real element: a piece of a label can't click "Buy now", a piece of a name can't
  fill a password field, and Enter can't press a payment button.
- **Forbidden outright.** Reading cookies or storage from a page, reading the Rasora profile,
  changing Rasora's own files from Claude, opening anything but http and https, and reaching
  local addresses such as the browser's debug port, including through a redirect.
- **Other MCP clients get the guard too.** They have no way to ask you, so `rasora mcp` refuses
  what Claude Code would ask you to confirm.
- **Page content is marked as untrusted** before the model reads it, inside tags a page can't
  close because they hold a random value. Memory is presented as notes, not instructions.
- **Locked dependencies.** Exact versions and hashes, wheels only.
- **No server of ours.** No account, no telemetry. Sessions and memory stay on your Mac. What
  does leave it: searches go to DuckDuckGo, pages are requested from their sites, and Claude
  sends what it reads to Anthropic, as with any tool you use with it.

## What it does on your Mac

- **It keeps live sessions on disk**, in `~/.rasora/chrome-profile`, inside a folder only your
  macOS user can read. Screenshots stay in `~/.rasora/screenshots` for one day.
- **It opens a Chrome debug port** on `127.0.0.1`, on a port of its own.
- **It writes memory in plain files**, including one line per message you send to Claude.
  Lines that look like keys, passwords or card numbers are skipped. That filter is simple, not
  a guarantee.
- **It approves its own ordinary actions** through the guard, so Claude doesn't ask each time.
  Your Claude Code settings are never changed.

## What it does not protect you from

- **Other programs on your Mac.** The debug port has no password: any program on this Mac, under
  any macOS account, can drive that Chrome while it runs. Anything running as your user can also
  read the profile. Don't install Rasora on a machine you don't trust or share.
- **Prompt injection.** The guard covers the riskiest actions, not all of them. A page could
  still trick the agent into reading something on a signed-in site, or send a message in a chat
  box where Enter sends. Stay around for sensitive work.
- **Poisoned memory.** A page could trick the agent into saving a false note, and notes are read
  at the next session. They are presented as facts to check, and you can read and edit them in
  `~/.rasora/memory`.
- **Disguised commands.** The guard reads every `rasora` call in a shell command, however it is
  chained, and asks when part of it is only known once it runs. A shell can still write a
  program that reaches the browser without ever naming Rasora, through a variable or an encoded
  string. With permissions switched off, the guard is your only brake, and a shell without
  permission checks can do anything your user can.
- **Word-based checks.** The guard looks for words like "Pay" or "Delete". A button with an
  unusual label can slip past it.
- **Sensitive accounts.** Don't sign in to your bank or your main email, and run
  `rasora logout` when you are done with any account. It deletes the site's cookies and stored
  data. A password you saved in Rasora's Chrome stays there until `rasora wipe`.
- **Updates.** A plugin runs what its repository ships. Read the changes if you enable
  auto-update.

## Known limits

- Sites whose sign-in only lasts until the browser closes ask you to sign in again after the
  browser stops, which it does after 45 minutes without use.
- Some sites, Google in particular, can refuse sign-ins in a browser driven by software.
- `rasora get` checks where a name points just before the request. A site that changes its DNS
  in that instant could still reach a local address.

## Good habits

- `rasora pause` the moment something looks wrong.
- `rasora wipe` to remove everything.
