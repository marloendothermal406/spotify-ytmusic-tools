#!/usr/bin/env python3
"""
Build spotify_tracks.json from Spotify CSV exports.

If you exported your Spotify library using a tool like Exportify
(https://exportify.net), you'll have one CSV file per playlist.
This script reads a folder of those CSVs and converts them into the
spotify_tracks.json format that yt_import.py expects.

Usage:
  python3 build_import.py <CSV_FOLDER> [OUTPUT_FILE]

  CSV_FOLDER   — folder containing .csv files (one per playlist)
  OUTPUT_FILE  — where to write JSON (default: spotify_tracks.json)

Example:
  python3 build_import.py ~/Downloads/spotify_csvs spotify_tracks.json

CSV format expected (Exportify default):
  Track Name, Artist Name(s), Duration (ms), ...
"""

import csv
import json
import os
import re
import sys


def norm(s):
    return re.sub(r"[\s\u200b\u00a0_]+", " ", s.lower().strip())


def filename_to_name(f):
    return f.replace(".csv", "").replace("_", " ")


if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

CSV_DIR = sys.argv[1]
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "spotify_tracks.json"

if not os.path.isdir(CSV_DIR):
    print(f"ERROR: '{CSV_DIR}' is not a directory.")
    sys.exit(1)

result = {}
summary = []

for fname in sorted(os.listdir(CSV_DIR)):
    if not fname.endswith(".csv"):
        continue
    playlist_name = filename_to_name(fname)
    filepath = os.path.join(CSV_DIR, fname)
    tracks = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Track Name", "").strip()
                artist = row.get("Artist Name(s)", "").strip().replace(";", ", ")
                duration = int(row.get("Duration (ms)", 0) or 0)
                if name and name != "Track Name":
                    tracks.append(
                        {"name": name, "artist": artist, "duration_ms": duration}
                    )
    except Exception as e:
        print(f"  Error reading {fname}: {e}")
        continue

    if tracks:
        result[playlist_name] = tracks
        summary.append((playlist_name, len(tracks), fname))

print(f"Read {len(result)} playlists from {len(os.listdir(CSV_DIR))} CSV files:\n")
for name, count, fname in sorted(summary, key=lambda x: x[1], reverse=True):
    print(f"  {count:>5} tracks | {name}")

total = sum(len(t) for t in result.values())
print(f"\nTotal: {len(result)} playlists, {total} tracks")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Saved to {OUTPUT}")
