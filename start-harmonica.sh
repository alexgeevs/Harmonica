#!/usr/bin/env bash
# Sets up and starts Harmonica. Safe to run again at any time.
set -e
cd "$(dirname "$0")"

# uv (the Python package manager): install it if missing.
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Install Python dependencies.
uv sync

# Build the player UI once (needs Node.js from https://nodejs.org).
if [ ! -f web/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Please install Node.js from https://nodejs.org, then run this again."; exit 1; }
  (cd web && npm install && npm run build)
fi

# Start Harmonica and open it in the browser (Ctrl+C here stops it).
(sleep 3; xdg-open http://127.0.0.1:8765 2>/dev/null || open http://127.0.0.1:8765) &
uv run harmonica serve
