#!/usr/bin/env bash
# Downloads Harmonica into your home folder, sets it up, and starts it.
# For Linux and macOS. Safe to run again at any time.
set -e
cd "$HOME"

if [ ! -d Harmonica ]; then
  curl -L https://github.com/alexgeevs/Harmonica/archive/refs/tags/v1.0.0.tar.gz | tar xz
  mv Harmonica-1.0.0 Harmonica
  echo "Harmonica downloaded to $HOME/Harmonica"
fi

cd Harmonica
exec ./start-harmonica.sh
