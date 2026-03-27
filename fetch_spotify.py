#!/usr/bin/env python3
"""
Fetch Spotify playlists and their tracks using the official Spotify Web API.

Requires a short-lived Bearer token (copy from browser DevTools).
Saves output to spotify_tracks.json for use with yt_import.py.

Usage:
  python3 fetch_spotify.py <BEARER_TOKEN>

How to get a token (no app registration needed):
  1. Open https://open.spotify.com in your browser while logged in
  2. Open DevTools → Network tab → filter "api.spotify.com"
  3. Click any request → Headers → copy the Authorization value
     (everything after "Bearer ")
  4. Tokens expire in ~1 hour — re-copy if you get a 401

Output:
  spotify_tracks.json  — { "Playlist Name": [{name, artist, duration_ms}, ...], ... }
"""

import json
import re
import sys
import time

import requests

if len(sys.argv) < 2:
    print("Usage: python3 fetch_spotify.py <BEARER_TOKEN>")
    print("\nSee the docstring at the top of this file for how to get a token.")
    sys.exit(1)

TOKEN = sys.argv[1].strip()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
OUTPUT = "spotify_tracks.json"


def api_get(url, retries=5):
    for attempt in range(retries):
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 10))
            print(f"    Rate limited, waiting {wait}s...", flush=True)
            time.sleep(wait + 1)
        elif r.status_code == 401:
            print("TOKEN EXPIRED. Get a new one from DevTools.", flush=True)
            sys.exit(1)
        else:
            print(f"    Error {r.status_code}: {r.text[:100]}", flush=True)
            time.sleep(2)
    return None


def norm(s):
    return re.sub(r"[\s\u200b\u00a0]+", " ", s.lower().strip())


print("Connecting to Spotify...", flush=True)
me = api_get("https://api.spotify.com/v1/me")
if not me:
    print("Failed to authenticate. Token may have expired.")
    sys.exit(1)
print(f"Logged in as: {me['display_name']} ({me['id']})", flush=True)

# Fetch all playlists
all_playlists = []
url = "https://api.spotify.com/v1/me/playlists?limit=50&offset=0"
while url:
    d = api_get(url)
    if not d:
        break
    all_playlists.extend(d["items"])
    url = d.get("next")
    time.sleep(0.5)

print(f"Found {len(all_playlists)} playlists. Fetching tracks for all...", flush=True)

result = {}
for i, pl in enumerate(all_playlists, 1):
    if not pl or not pl.get("name"):
        continue
    tracks = []
    url = (
        f"https://api.spotify.com/v1/playlists/{pl['id']}/tracks"
        "?fields=items(track(name,artists(name),duration_ms)),next&limit=100"
    )
    while url:
        d = api_get(url)
        if not d:
            break
        for item in d.get("items", []):
            t = item.get("track")
            if t and t.get("name"):
                tracks.append(
                    {
                        "name": t["name"],
                        "artist": ", ".join(a["name"] for a in t.get("artists", [])),
                        "duration_ms": t.get("duration_ms", 0),
                    }
                )
        url = d.get("next")
        time.sleep(0.3)
    result[pl["name"]] = tracks
    print(f"  [{i}/{len(all_playlists)}] {pl['name']}: {len(tracks)} tracks", flush=True)

total_tracks = sum(len(t) for t in result.values())
print(f"\nDONE: {len(result)} playlists, {total_tracks} total tracks", flush=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Saved to {OUTPUT}", flush=True)
