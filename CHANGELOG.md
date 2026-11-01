# Changelog

## Unreleased

- Installs on the Python a Mac ships with (3.9). The lock asked for 3.10 and the setup failed
  in silence. Reported by Micka.
- Setup failures now give a reason, and Claude hears about it at the next session.
- Pillow is gone: screenshots are cropped with macOS `sips`, so there is no native dependency
  left. The last Pillow for Python 3.9 has known vulnerabilities.
- CI runs the install and the tests on the system Python.

## 0.5.0

- Guard: every `rasora` call in a chained or nested command is checked, and the strictest
  answer wins. Reported by Micka.

- Sign-ins survive a browser stop on sites that allow it, and Chrome can save passwords in
  Rasora's own profile, so signing in again takes one click.
- Claude knows which sites are signed in, and a daily visit keeps sessions fresh.

- Reconnects by itself: passwords saved in Rasora's Chrome fill in the page, and the agent
  only presses the button. It never sees them.
- Accounts already signed in through a connector or a CLI are used first.
- The guard refuses any search for passwords in files or the Keychain.

## 0.4.0

- Rasora no longer touches your everyday Chrome or Keychain. You sign in by hand, once per
  site, in its own window. Copying cookies is gone, and so is the dependency it needed.
- Its own port, so it runs next to anything else.
- No more prompts for ordinary actions, and your settings are never changed.
- Memory no longer depends on the model: what you ask to keep is written by the hook, and
  recent requests come back at session start.
- The browser stops after 45 minutes without use.

## 0.3.0

- Safety guard outside the model: asks before payments, publishing, deleting and messages,
  refuses cookie access and local addresses.
- Web search and page reading without Chrome. The browser is now the last resort.
- Locked dependencies with hashes, tests, CI and CodeQL.

## 0.2.0

- Claude Code plugin, memory across sessions, background tasks.

## 0.1.0

- First version.
