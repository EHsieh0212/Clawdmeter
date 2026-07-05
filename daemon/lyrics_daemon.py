#!/usr/bin/env python3
"""Clawdmeter lyrics daemon (Phase 3, standalone).

Polls Spotify for the currently-playing track + position, fetches time-synced
lyrics from LRCLIB, and streams them to the Clawdmeter over BLE using the `ly`
message protocol the firmware understands (header / line / position / stop).

Runs alongside the usage daemon — both connect to the same board over BLE; on
one Mac they share the physical link.

Setup (one time):
    Spotify app at https://developer.spotify.com/dashboard, redirect URI
    http://127.0.0.1:8888/callback, then:

        export SPOTIFY_CLIENT_ID=...
        export SPOTIFY_CLIENT_SECRET=...
        /opt/homebrew/bin/python3.11 daemon/lyrics_daemon.py   # (python with bleak)

    First run opens a browser to authorize (scope: read currently-playing).
    The refresh token is cached to ~/.config/claude-usage-monitor/spotify-token.json.

The board only shows lyrics while it's on the lyrics screen (tap to it); when
nothing is playing the firmware falls back to the gif on its own.
"""
import asyncio
import base64
import hashlib
import http.server
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from bleak import BleakClient, BleakScanner

# --- BLE / protocol ---------------------------------------------------------
SERVICE_UUID = "4c41555a-4465-7669-6365-000000000001"
RX_CHAR_UUID = "4c41555a-4465-7669-6365-000000000002"
DEVICE_NAME  = "Clawdmeter"

# --- Spotify ----------------------------------------------------------------
CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SCOPE         = "user-read-currently-playing user-read-playback-state"
TOKEN_FILE    = Path.home() / ".config/claude-usage-monitor/spotify-token.json"
UA            = "clawdmeter-lyrics/0.1"

POLL_SECONDS  = 5.0


def log(m):
    print(f"[lyrics] {m}", flush=True)


# ---------------------------------------------------------------------------
# Spotify auth + polling (blocking; called via asyncio.to_thread)
# ---------------------------------------------------------------------------
def _post_token(data):
    body = urllib.parse.urlencode(data).encode()
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=body,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def _authorize_interactive():
    code_holder = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.urlparse(self.path).query
            code_holder["code"] = urllib.parse.parse_qs(qs).get("code", [None])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<h2>Clawdmeter lyrics authorized. You can close this tab.</h2>")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "scope": SCOPE})
    log("opening browser to authorize Spotify…")
    log(f"  if it doesn't open: {auth_url}")
    webbrowser.open(auth_url)
    for _ in range(120):
        if code_holder.get("code"):
            break
        time.sleep(0.5)
    if not code_holder.get("code"):
        raise RuntimeError("timed out waiting for Spotify authorization")
    tok = _post_token({"grant_type": "authorization_code",
                       "code": code_holder["code"], "redirect_uri": REDIRECT_URI})
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    return tok


class Spotify:
    """Holds a Spotify access token, refreshing before expiry."""
    def __init__(self):
        self._access = None
        self._expires_at = 0.0

    def _ensure_token(self):
        if self._access and time.time() < self._expires_at - 60:
            return self._access
        rt = None
        if TOKEN_FILE.exists():
            rt = json.loads(TOKEN_FILE.read_text()).get("refresh_token")
        if rt:
            tok = _post_token({"grant_type": "refresh_token", "refresh_token": rt})
        else:
            tok = _authorize_interactive()
        self._access = tok["access_token"]
        self._expires_at = time.time() + int(tok.get("expires_in", 3600))
        return self._access

    def now_playing(self):
        """-> dict | None. None when nothing is playing."""
        token = self._ensure_token()
        req = urllib.request.Request(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 204:
                    return None
                d = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._access = None
                return self.now_playing()
            raise
        item = d.get("item")
        if not item:
            return None
        return {
            "track": item["name"],
            "artist": item["artists"][0]["name"],
            "album": item["album"]["name"],
            "duration": round(item["duration_ms"] / 1000),
            "progress_ms": d.get("progress_ms", 0),
            "is_playing": d.get("is_playing", False),
            "sid": item["id"],
        }


def lrclib_synced(track, artist, album, duration):
    """-> list[(ms, text)] sorted, or [] if no synced lyrics."""
    def _get(url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    try:
        qs = urllib.parse.urlencode({"track_name": track, "artist_name": artist,
                                     "album_name": album, "duration": duration})
        d = _get("https://lrclib.net/api/get?" + qs)
    except urllib.error.HTTPError:
        try:
            qs = urllib.parse.urlencode({"track_name": track, "artist_name": artist})
            arr = _get("https://lrclib.net/api/search?" + qs)
            d = next((x for x in arr if x.get("syncedLyrics")), {})
        except Exception:
            return []
    return parse_lrc(d.get("syncedLyrics") or "")


def parse_lrc(text):
    out = []
    for raw in text.splitlines():
        stamps = []
        while raw.startswith("["):
            close = raw.find("]")
            if close == -1:
                break
            tag, raw = raw[1:close], raw[close + 1:]
            parts = tag.split(":")
            try:
                stamps.append(int((int(parts[0]) * 60 + float(parts[1])) * 1000))
            except (ValueError, IndexError):
                pass  # metadata tag like [ar:…]
        line = raw.strip()
        for ms in stamps:
            if line:
                out.append((ms, line))
    return sorted(out)


def track_id(track, artist):
    return int(hashlib.md5(f"{track}|{artist}".encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# BLE
# ---------------------------------------------------------------------------
async def find_target():
    if sys.platform == "darwin":
        try:
            from bleak.backends.corebluetooth.CentralManagerDelegate import CentralManagerDelegate
            from bleak.backends.device import BLEDevice
            from CoreBluetooth import CBUUID
            mgr = CentralManagerDelegate()
            await mgr.wait_until_ready()
            cm = mgr.central_manager
            for uuid, need_name in ((SERVICE_UUID, False), ("1812", True)):
                for p in cm.retrieveConnectedPeripheralsWithServices_(
                        [CBUUID.UUIDWithString_(uuid)]) or []:
                    if need_name and p.name() != DEVICE_NAME:
                        continue
                    return BLEDevice(p.identifier().UUIDString(), p.name(), (p, mgr))
        except Exception as e:
            log(f"CoreBluetooth lookup failed: {e}")
    return await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)


async def send(client, obj):
    data = json.dumps(obj, separators=(",", ":")).encode()
    await client.write_gatt_char(RX_CHAR_UUID, data, response=False)


async def push_song(client, tid, np, lines):
    """Send header + all lines for a new track."""
    await send(client, {"ly": "h", "id": tid, "n": len(lines),
                        "tr": np["track"], "ar": np["artist"]})
    for i, (ms, text) in enumerate(lines):
        await send(client, {"ly": "l", "id": tid, "i": i, "ms": ms, "x": text})
        await asyncio.sleep(0.012)
    log(f"pushed '{np['track']}' — {np['artist']} ({len(lines)} lines)")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def run_session(client, sp):
    cur_sid = None
    cur_tid = None
    was_playing = True
    while True:
        try:
            np = await asyncio.to_thread(sp.now_playing)
        except Exception as e:
            log(f"Spotify poll error: {e}")
            await asyncio.sleep(POLL_SECONDS)
            continue

        if np is None or not np["is_playing"]:
            if was_playing:
                await send(client, {"ly": "x"})   # nothing playing → device shows gif
                log("nothing playing" if np is None else "paused")
                was_playing = False
            await asyncio.sleep(POLL_SECONDS)
            continue
        was_playing = True

        if np["sid"] != cur_sid:
            cur_sid = np["sid"]
            cur_tid = track_id(np["track"], np["artist"])
            try:
                lines = await asyncio.to_thread(
                    lrclib_synced, np["track"], np["artist"], np["album"], np["duration"])
            except Exception as e:
                log(f"LRCLIB error: {e}")
                lines = []
            if not lines:
                log(f"no synced lyrics for '{np['track']}' — showing title only")
            await push_song(client, cur_tid, np, lines)

        await send(client, {"ly": "p", "id": cur_tid,
                            "ms": np["progress_ms"], "pl": 1})
        await asyncio.sleep(POLL_SECONDS)


async def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        log("set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET (see header).")
        return 1
    sp = Spotify()
    # Warm up / trigger one-time auth before touching BLE.
    await asyncio.to_thread(sp._ensure_token)
    log("Spotify authorized.")
    while True:
        dev = await find_target()
        if not dev:
            log("Clawdmeter not found; retrying in 10s…")
            await asyncio.sleep(10)
            continue
        try:
            async with BleakClient(dev) as client:
                log("connected to Clawdmeter. streaming lyrics…")
                await run_session(client, sp)
        except Exception as e:
            log(f"BLE session ended: {e}; reconnecting in 5s…")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        log("bye")
