#!/usr/bin/env bash
# Downloads Harmonica into your home folder, sets it up, and serves it to your
# local network. For a NAS, Pi, or any always-on computer. Safe to run again at any time.
set -e
cd "$HOME"

if [ ! -d Harmonica ]; then
  curl -L https://github.com/alexgeevs/Harmonica/archive/refs/tags/v1.0.0.tar.gz | tar xz
  mv Harmonica-1.0.0 Harmonica
  echo "Harmonica downloaded to $HOME/Harmonica"
fi
cd Harmonica

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

# Serve to the whole network (Ctrl+C here stops it). Set up per-user profiles
# with passphrases in the app before sharing the address with your household.
ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Other devices on your network can open: http://${ip:-YOUR-NAS-IP}:8765"
HARMONICA_HOST=0.0.0.0 uv run harmonica serve
