# Spotify lyrics daemon — setup

`lyrics_daemon.py` polls Spotify for the currently-playing track + position,
fetches time-synced lyrics from LRCLIB, and streams them to the Clawdmeter over
BLE. It runs alongside the usage daemon (both connect to the same board).

The device shows lyrics only while it's on the lyrics/Spotify screen (tap to
it). Nothing playing / paused → the board shows a large Spotify logo.

## One-time setup (macOS)

1. **Spotify app** — https://developer.spotify.com/dashboard → create an app,
   redirect URI `http://127.0.0.1:8888/callback`, API = Web API. Note the
   Client ID + Secret.

2. **Creds file** (keeps the secret out of the shell/launchd config):

   ```bash
   cat > ~/.config/claude-usage-monitor/spotify.env << 'EOF'
   SPOTIFY_CLIENT_ID=your_id
   SPOTIFY_CLIENT_SECRET=your_secret
   EOF
   ```

3. **Python env** — a venv with bleak + certifi. (The pio Python works but lacks
   CA certs, hence certifi + `SSL_CERT_FILE`; the launcher sets that.)

   ```bash
   ~/.platformio/penv/bin/python -m venv ~/.config/claude-usage-monitor/lyrics-venv
   ~/.config/claude-usage-monitor/lyrics-venv/bin/pip install bleak certifi
   ```

4. **First authorization** — run the launcher once in a terminal so the browser
   OAuth can complete; the refresh token caches to
   `~/.config/claude-usage-monitor/spotify-token.json`:

   ```bash
   bash daemon/run-lyrics-daemon.sh      # authorize in the browser, Ctrl-C after "connected"
   ```

5. **Install the launchd agent** (auto-start at login, restart on crash):

   ```bash
   cp daemon/run-lyrics-daemon.sh          ~/.config/claude-usage-monitor/
   cp daemon/com.user.clawdmeter-lyrics.plist ~/Library/LaunchAgents/
   chmod +x ~/.config/claude-usage-monitor/run-lyrics-daemon.sh
   launchctl load -w ~/Library/LaunchAgents/com.user.clawdmeter-lyrics.plist
   ```

## Managing it

```bash
launchctl list | grep clawdmeter-lyrics          # running? (col 1 = pid)
tail -f ~/Library/Logs/clawdmeter-lyrics.out.log # logs
launchctl unload ~/Library/LaunchAgents/com.user.clawdmeter-lyrics.plist  # stop
launchctl load   ~/Library/LaunchAgents/com.user.clawdmeter-lyrics.plist  # start
```

Paths in `run-lyrics-daemon.sh` and the plist are absolute (`/Users/elaine.hsieh/...`);
adjust if the repo or user moves. `daemon/lyrics_inject.py` is a standalone
BLE test tool (sends a fixed song without Spotify).
