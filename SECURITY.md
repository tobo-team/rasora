# Security

neverlogout is powerful, so here is exactly what it does and what it does not protect you
from. If you are not comfortable with this, don't install it.

## What it does

- **It decrypts Chrome cookies.** For allowed sites, it asks macOS Keychain for Chrome's key,
  decrypts those cookies and copies them into a separate Chrome profile. Infostealers use
  the same mechanism. The difference is that this code is open, runs locally, and only
  touches the sites you allowed. Read `scripts/cookies-vers-bot.py`.
- **It keeps live sessions on disk**, in `~/.neverlogout/chrome-profile`. The folder is
  readable only by your macOS user.
- **It opens a Chrome debug port** on `127.0.0.1`.
- **It never sends anything anywhere.** There is no server, no telemetry and no account.
  Your agent may send page content to its own model provider, as it does with any tool.

## What it does not protect you from

- **Other programs on your Mac.** Any program running as your user could reach the debug
  port or the profile. Don't install this on a machine you don't trust.
- **Prompt injection.** Text on a page or in an email can try to trick your agent, and the
  agent acts with your accounts. Allow only what you need, and stay around for sensitive
  actions.
- **Site rules.** Copying sessions may go against the terms of some sites, and a site may
  flag or sign out a session. Use your own accounts only.

## Good habits

- Allow as few sites as you can. Banking and email deserve extra thought.
- Run `neverlogout deny <site>` when you are done with a site.
- Run `neverlogout wipe` to remove everything, cookies included.

## Report a problem

Please use GitHub's private vulnerability reporting on this repository, not a public issue.
