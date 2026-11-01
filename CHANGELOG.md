# Changelog

## 0.5.0

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
