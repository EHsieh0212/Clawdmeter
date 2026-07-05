#!/bin/bash
# Launcher for the Clawdmeter Spotify-lyrics daemon (started by launchd).
# Sources Spotify creds, points SSL at certifi (the venv's Python lacks system
# CA certs), and runs the daemon from a stable venv.
set -euo pipefail
CFG="$HOME/.config/claude-usage-monitor"
VENV="$CFG/lyrics-venv"
REPO="/Users/elaine.hsieh/Clawdmeter"

set -a
[ -f "$CFG/spotify.env" ] && source "$CFG/spotify.env"
set +a

export SSL_CERT_FILE="$("$VENV/bin/python" -c 'import certifi; print(certifi.where())')"
exec "$VENV/bin/python" "$REPO/daemon/lyrics_daemon.py"
