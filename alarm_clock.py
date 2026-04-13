#!/usr/bin/env python3
"""
alarm_clock.py
Terminal alarm clock that plays a random song from a Spotify playlist.

Usage:
  python alarm_clock.py

Commands (at the prompt):
  add    HH:MM [label]   – add an alarm (24h format), optional label
  list                   – show all alarms
  remove <id>            – remove an alarm by its ID
  quit                   – exit
"""

import random
import threading
import time
from datetime import datetime
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# ── CONFIG ────────────────────────────────────────────────────────────────────
CLIENT_ID     = ""
CLIENT_SECRET = ""
REDIRECT_URI  = "http://127.0.0.1:8888/callback"

# Hardcoded playlist name (case-insensitive substring match)
PLAYLIST_NAME = "Big Brother"
# ─────────────────────────────────────────────────────────────────────────────

SCOPE = "playlist-read-private user-modify-playback-state user-read-playback-state"


# ── Spotify helpers ───────────────────────────────────────────────────────────

def get_spotify_client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,
        cache_path=".spotify_token_cache",
    )
    return spotipy.Spotify(auth_manager=auth)


def find_playlist(sp: spotipy.Spotify, name: str) -> Optional[dict]:
    results = sp.current_user_playlists(limit=50)
    while results:
        for p in results["items"]:
            if name.lower() in p["name"].lower():
                return p
        results = sp.next(results) if results["next"] else None
    return None


def fetch_all_tracks(sp: spotipy.Spotify, playlist_id: str) -> list:
    tracks = []
    results = sp.playlist_tracks(playlist_id, limit=100)
    while results:
        for item in results["items"]:
            track = item.get("track") or item.get("item")
            if track and track.get("uri"):
                tracks.append(track)
        results = sp.next(results) if results.get("next") else None
    return tracks


def get_active_device(sp: spotipy.Spotify) -> Optional[str]:
    devices = sp.devices().get("devices", [])
    if not devices:
        return None
    for d in devices:
        if d["is_active"]:
            return d["id"]
    return devices[0]["id"]


def play_random_track(sp: spotipy.Spotify, tracks: list) -> None:
    track     = random.choice(tracks)
    name      = track["name"]
    artists   = ", ".join(a["name"] for a in track["artists"])
    uri       = track["uri"]
    device_id = get_active_device(sp)

    if not device_id:
        print("\n⚠  No active Spotify device found. Open Spotify on any device and try again.")
        return

    sp.start_playback(device_id=device_id, uris=[uri])
    print(f"\n🎵  ALARM! Now playing: {name} — {artists}\n> ", end="", flush=True)


# ── Alarm state ───────────────────────────────────────────────────────────────

alarms: dict[int, dict] = {}   # id -> {"time": "HH:MM", "label": str, "fired": bool}
_next_id = 1
_lock    = threading.Lock()


def add_alarm(time_str: str, label: str = "") -> int:
    global _next_id
    with _lock:
        alarm_id = _next_id
        alarms[alarm_id] = {"time": time_str, "label": label, "fired": False}
        _next_id += 1
    return alarm_id


def remove_alarm(alarm_id: int) -> bool:
    with _lock:
        if alarm_id in alarms:
            del alarms[alarm_id]
            return True
    return False


def list_alarms() -> None:
    with _lock:
        if not alarms:
            print("  No alarms set.")
            return
        for aid, a in alarms.items():
            label = f"  ({a['label']})" if a["label"] else ""
            status = "✓ fired" if a["fired"] else "pending"
            print(f"  [{aid}] {a['time']}{label}  — {status}")


# ── Background thread ─────────────────────────────────────────────────────────

def alarm_watcher(sp: spotipy.Spotify, tracks: list) -> None:
    """Checks every 10 seconds if any alarm should fire."""
    while True:
        now = datetime.now().strftime("%H:%M")
        with _lock:
            to_fire = [
                aid for aid, a in alarms.items()
                if a["time"] == now and not a["fired"]
            ]
        for aid in to_fire:
            with _lock:
                alarms[aid]["fired"] = True
            play_random_track(sp, tracks)
        time.sleep(10)


# ── CLI ───────────────────────────────────────────────────────────────────────

HELP = """
Commands:
  add HH:MM [label]   Add an alarm (24h). Label is optional.
  list                Show all alarms.
  remove <id>         Remove an alarm by ID.
  help                Show this message.
  quit                Exit.
"""


def parse_time(s: str) -> Optional[str]:
    try:
        datetime.strptime(s, "%H:%M")
        return s
    except ValueError:
        return None


def run_cli() -> None:
    print("🕐  Spotify Alarm Clock")
    print("   Connecting to Spotify...", end="", flush=True)

    sp = get_spotify_client()
    playlist = find_playlist(sp, PLAYLIST_NAME)
    if not playlist:
        print(f"\n✗  Playlist '{PLAYLIST_NAME}' not found on your account.")
        return

    tracks = fetch_all_tracks(sp, playlist["id"])
    if not tracks:
        print(f"\n✗  Playlist '{PLAYLIST_NAME}' has no playable tracks.")
        return

    print(f" connected.\n   Loaded {len(tracks)} tracks from '{playlist['name']}'.")
    print(HELP)

    watcher = threading.Thread(target=alarm_watcher, args=(sp, tracks), daemon=True)
    watcher.start()

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=2)
        cmd   = parts[0].lower()

        if cmd == "quit":
            print("Goodbye!")
            break

        elif cmd == "help":
            print(HELP)

        elif cmd == "list":
            list_alarms()

        elif cmd == "add":
            if len(parts) < 2:
                print("  Usage: add HH:MM [label]")
                continue
            t = parse_time(parts[1])
            if not t:
                print("  Invalid time format. Use HH:MM (24h), e.g. 07:30")
                continue
            label = parts[2] if len(parts) > 2 else ""
            aid   = add_alarm(t, label)
            print(f"  Alarm [{aid}] set for {t}" + (f" ({label})" if label else ""))

        elif cmd == "remove":
            if len(parts) < 2 or not parts[1].isdigit():
                print("  Usage: remove <id>")
                continue
            aid = int(parts[1])
            if remove_alarm(aid):
                print(f"  Alarm [{aid}] removed.")
            else:
                print(f"  No alarm with ID {aid}.")

        else:
            print(f"  Unknown command '{cmd}'. Type 'help' for usage.")


if __name__ == "__main__":
    run_cli()