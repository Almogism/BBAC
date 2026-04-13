#!/usr/bin/env python3
"""
random_spotify_song.py
Play a random track from one of your Spotify playlists on macOS.

Setup:
  1. pip install spotipy
  2. Go to https://developer.spotify.com/dashboard and create an app.
  3. In the app settings, add this Redirect URI: http://127.0.0.1:8888/callback
  4. Copy your Client ID and Client Secret into the constants below.
  5. Run the script — it will open a browser for one-time auth, then work silently.
"""

import random
from typing import Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# ── CONFIG ────────────────────────────────────────────────────────────────────
CLIENT_ID     = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI  = "http://127.0.0.1:8888/callback"

# Optional: pin a specific playlist by its name (case-insensitive substring match).
# Leave as "" to be prompted to pick from your playlists each run.
PLAYLIST_NAME_FILTER = ""
# ─────────────────────────────────────────────────────────────────────────────

SCOPE = "playlist-read-private user-modify-playback-state user-read-playback-state"


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


def fetch_all_playlists(sp: spotipy.Spotify) -> list[dict]:
    playlists, results = [], sp.current_user_playlists(limit=50)
    while results:
        playlists.extend(results["items"])
        results = sp.next(results) if results["next"] else None
    return playlists


def pick_playlist(sp: spotipy.Spotify) -> dict:
    playlists = fetch_all_playlists(sp)
    if not playlists:
        raise RuntimeError("No playlists found on your account.")

    if PLAYLIST_NAME_FILTER:
        filtered = [p for p in playlists if PLAYLIST_NAME_FILTER.lower() in p["name"].lower()]
        if filtered:
            return filtered[0]
        print(f"No playlist matched '{PLAYLIST_NAME_FILTER}', showing all playlists instead.\n")

    print("Your playlists:")
    for i, p in enumerate(playlists, 1):
        track_count = p.get('items', {}).get('total', '?')
        print(f"  {i:>2}. {p['name']}  ({track_count} tracks)")

    while True:
        try:
            choice = int(input("\nPick a playlist number: "))
            # choice = 1
            if 1 <= choice <= len(playlists):
                return playlists[choice - 1]
        except ValueError:
            pass
        print("Invalid choice, try again.")


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
    # Prefer an already-active device
    for d in devices:
        if d["is_active"]:
            return d["id"]
    return devices[0]["id"]


def play_random_track(sp: spotipy.Spotify, playlist: dict) -> None:
    tracks = fetch_all_tracks(sp, playlist["id"])

    if not tracks:
        raise RuntimeError("The selected playlist has no playable tracks.")

    track = random.choice(tracks)
    name    = track["name"]
    artists = ", ".join(a["name"] for a in track["artists"])
    uri     = track["uri"]

    device_id = get_active_device(sp)
    if not device_id:
        print("No active Spotify device found.")
        print("Open Spotify on any device (Mac, phone, etc.) and try again.")
        return

    sp.start_playback(device_id=device_id, uris=[uri])
    print(f"\n▶  Now playing: {name} — {artists}")
    print(f"   Playlist   : {playlist['name']}")

def main():
    sp       = get_spotify_client()
    playlist = pick_playlist(sp)
    play_random_track(sp, playlist)

if __name__ == "__main__":
    main()
