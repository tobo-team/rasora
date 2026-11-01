#!/bin/bash
# Never blocks, never prints. A hook must not disturb the conversation.
[ -f "$HOME/.rasora/bin/memoire.py" ] || exit 0
exec python3 "$(dirname "$0")/hook-prompt.py" 2>/dev/null
