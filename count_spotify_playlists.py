#!/usr/bin/env python3
"""
Count and list all Spotify playlists (including private ones).

Requires a free Spotify developer app for OAuth authentication.

Setup (one-time):
  1. Go to https://developer.spotify.com/dashboard → Create app
  2. Set redirect URI to: http://localhost:8888/callback
  3. Copy your Client ID and Client Secret

Usage:
  export SPOTIPY_CLIENT_ID="your_client_id"
  export SPOTIPY_CLIENT_SECRET="your_client_secret"
  python3 count_spotify_playlists.py

Output:
  Prints a numbered list of all playlists with owner and track count.
  Saves a full report to spotify_playlists_report.txt
"""

import os
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth

REDIRECT_URI = "http://localhost:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative"

client_id = os.environ.get("SPOTIPY_CLIENT_ID")
client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")

if not client_id or not client_secret:
    print("ERROR: Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables first.")
    print()
    print("Usage:")
    print('  export SPOTIPY_CLIENT_ID="your_client_id"')
    print('  export SPOTIPY_CLIENT_SECRET="your_client_secret"')
    print("  python3 count_spotify_playlists.py")
    sys.exit(1)

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
    )
)

user = sp.current_user()
print(f"\nLogged in as: {user['display_name']} ({user['id']})\n")

playlists = []
offset = 0
while True:
    batch = sp.current_user_playlists(limit=50, offset=offset)
    playlists.extend(batch["items"])
    if batch["next"] is None:
        break
    offset += 50

print(f"{'='*60}")
print(f" TOTAL PLAYLISTS: {len(playlists)}")
print(f"{'='*60}\n")

own_count = 0
saved_count = 0
output_lines = []

for i, pl in enumerate(playlists, 1):
    owner = pl["owner"]["display_name"] or pl["owner"]["id"]
    tracks = pl["tracks"]["total"]
    is_own = pl["owner"]["id"] == user["id"]
    marker = "[YOURS]" if is_own else "[SAVED]"
    if is_own:
        own_count += 1
    else:
        saved_count += 1
    line = f"{i:4d}. {marker} {pl['name']}  ({tracks} songs)  — by {owner}"
    output_lines.append(line)
    print(line)

print(f"\n{'='*60}")
print(f" SUMMARY")
print(f"{'='*60}")
print(f" Total playlists:       {len(playlists)}")
print(f" Created by you:        {own_count}")
print(f" Saved from others:     {saved_count}")
print(f"{'='*60}\n")

report_path = "spotify_playlists_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"Spotify Playlists Report for {user['display_name']}\n")
    f.write(f"Total: {len(playlists)} | Yours: {own_count} | Saved: {saved_count}\n")
    f.write(f"{'='*60}\n\n")
    for line in output_lines:
        f.write(line + "\n")

print(f"Full report saved to: {report_path}")
