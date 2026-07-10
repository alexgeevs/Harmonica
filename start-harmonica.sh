#!/usr/bin/env bash
# Sets up and starts Harmonica. Safe to run again at any time.
set -euo pipefail
cd "$(dirname "$0")"

# 1. uv (the Python package manager): install locally if missing.
if ! command -v uv >/dev/null 2>&1; then
  if [ -x "$HOME/.local/bin/uv" ]; then
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "Installing uv, the Python package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

# 2. Python dependencies.
uv sync

# 3. Build the player UI once (needs Node.js; skipped when already built).
if [ ! -f web/dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd web && npm install && npm run build)
  else
    echo "Node.js is needed to build the player UI (a one-off step)." >&2
    echo "Install it from https://nodejs.org, then run this script again." >&2
    exit 1
  fi
fi

# 4. Open the player and start the daemon (Ctrl+C here stops it).
url="http://127.0.0.1:8765"
(
  sleep 3
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1
  elif command -v open >/dev/null 2>&1; then open "$url"
  fi
) &
echo "Harmonica is starting at $url (Ctrl+C here stops it)."
exec uv run harmonica serve
