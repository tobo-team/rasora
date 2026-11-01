# Contributing

Thanks for helping.

## Most useful right now

- A site recipe: add a domain list and a check URL to `RECETTES` in
  `scripts/configurer-sessions.py`.
- A bug report with your macOS version, Chrome version and the exact output.
- Linux or Windows support: the cookie and window code is macOS-only today.

## Rules

- No telemetry, and nothing that sends data off the machine.
- Nothing is copied unless the user allowed it.
- Don't add anything that bypasses 2FA, CAPTCHAs or a site's security.
- No fake identities or bulk account creation.
- Never paste real cookies, tokens or account details in an issue.

## Note on the code

The project started in French, so many internal names and comments still are. User-facing
messages are in English, and French names are fine to rename as you go.

## Test

Run the installer with your changes from a clean macOS user. `RASORA_NO_LAUNCHD=1`
skips the background guardians.
