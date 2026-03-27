#!/usr/bin/env python3
"""
Fetch Spotify library playlists via the internal partner (GraphQL) API.

This can see ALL playlists in your library, including those the standard
API sometimes misses (e.g. collaborative playlists, imported ones, etc.).

Requires two short-lived tokens copied from browser DevTools.
Output is saved to spotify_tracks.json for use with yt_import.py.

Usage:
  python3 fetch_spotify_partner.py <BEARER_TOKEN> <CLIENT_TOKEN>

How to get the tokens:
  1. Open https://open.spotify.com in your browser while logged in
  2. Open DevTools → Network tab → filter "api-partner.spotify.com"
  3. Click any request → Headers tab:
     - Copy "authorization" value (everything after "Bearer ")  → BEARER_TOKEN
     - Copy "client-token" value                                → CLIENT_TOKEN
  Tokens expire in ~1 hour — re-copy if you get a 401.

Output:
  spotify_tracks.json  — { "Playlist Name": [{name, artist, duration_ms}, ...], ... }
"""

import json
import re
import sys
import time
import urllib.parse

import requests

if len(sys.argv) < 3:
    print("Usage: python3 fetch_spotify_partner.py <BEARER_TOKEN> <CLIENT_TOKEN>")
    print("\nSee the docstring at the top of this file for how to get the tokens.")
    sys.exit(1)

TOKEN = sys.argv[1].strip()
CLIENT_TOKEN = sys.argv[2].strip()
OUTPUT = "spotify_tracks.json"

HEADERS = {
    "authorization": f"Bearer {TOKEN}",
    "client-token": CLIENT_TOKEN,
    "app-platform": "WebPlayer",
    "accept": "application/json",
    "origin": "https://open.spotify.com",
    "referer": "https://open.spotify.com/",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ),
}
STANDARD_HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BASE = "https://api-partner.spotify.com"


def api_get(url, headers=HEADERS, retries=5):
    for attempt in range(retries):
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5))
            if wait > 300:
                print(f"    Rate limit too long ({wait}s). Stopping.", flush=True)
                sys.exit(1)
            print(f"    Rate limited, waiting {wait}s...", flush=True)
            time.sleep(wait + 1)
        elif r.status_code == 401:
            print("TOKEN EXPIRED. Get a new one from DevTools.", flush=True)
            sys.exit(1)
        else:
            print(f"    Error {r.status_code}", flush=True)
            time.sleep(2)
    return None


def norm(s):
    return re.sub(r"[\s\u200b\u00a0]+", " ", s.lower().strip())


def fetch_library_playlists():
    """Fetch all library playlists via the partner GraphQL API."""
    all_items = []
    offset = 0
    limit = 50
    while True:
        variables = json.dumps(
            {
                "filters": ["Playlists"],
                "order": None,
                "textFilter": "",
                "features": ["LIKED_SONGS", "YOUR_EPISODES"],
                "limit": limit,
                "offset": offset,
                "flatten": False,
                "expandedFolders": [],
                "folderUri": None,
                "includeFoldersWhenFlattening": True,
                "withCuration": False,
            }
        )
        extensions = json.dumps(
            {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": (
                        "17d801ba80f3a3d7405966641818c334fe32158f97e9e8b38cdc5b32ad9b8d5c"
                    ),
                }
            }
        )
        url = (
            f"{BASE}/pathfinder/v1/query"
            f"?operationName=libraryV3"
            f"&variables={urllib.parse.quote(variables)}"
            f"&extensions={urllib.parse.quote(extensions)}"
        )
        d = api_get(url)
        if not d:
            break
        items = (
            d.get("data", {})
            .get("me", {})
            .get("libraryV3", {})
            .get("items", [])
        )
        if not items:
            break
        for item in items:
            data = item.get("item", {}).get("data", {})
            uri = data.get("uri", "")
            name = data.get("name", "")
            if uri.startswith("spotify:playlist:"):
                pid = uri.split(":")[-1]
                all_items.append({"id": pid, "name": name, "uri": uri})
        total = (
            d.get("data", {})
            .get("me", {})
            .get("libraryV3", {})
            .get("totalCount", 0)
        )
        offset += limit
        if offset >= total:
            break
        time.sleep(0.5)
    return all_items


def fetch_playlist_tracks(playlist_id):
    tracks = []
    url = (
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        "?fields=items(track(name,artists(name),duration_ms)),next&limit=100"
    )
    while url:
        d = api_get(url, headers=STANDARD_HEADERS)
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
    return tracks


print("Fetching library playlists via partner API...", flush=True)
playlists = fetch_library_playlists()
print(f"Found {len(playlists)} playlists in library", flush=True)

result = {}
for i, pl in enumerate(playlists, 1):
    tracks = fetch_playlist_tracks(pl["id"])
    result[pl["name"]] = tracks
    print(f"  [{i}/{len(playlists)}] {pl['name']}: {len(tracks)} tracks", flush=True)

total_tracks = sum(len(t) for t in result.values())
print(f"\nDONE: {len(result)} playlists, {total_tracks} total tracks", flush=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Saved to {OUTPUT}", flush=True)
