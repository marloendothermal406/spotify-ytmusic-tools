#!/usr/bin/env python3
"""
Bulk-delete YouTube Music playlists created by yt_import.py.

YouTube Music has no "select all and delete" in the app or website.
This uses ytmusicapi + your browser.json auth.

Default: deletes every playlist ID listed in import_progress.json (status "done").
Optional: delete ALL playlists in your library (dangerous — see --all-library).

Usage:
  source spotifyenv/bin/activate
  python3 delete_ytm_imports.py --dry-run          # list only, no deletes
  python3 delete_ytm_imports.py                    # delete from import_progress.json
  python3 delete_ytm_imports.py --all-library      # delete EVERY saved playlist (needs typing YES)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from hashlib import sha1
from http.cookies import SimpleCookie

from ytmusicapi import YTMusic


def refresh_browser_auth() -> None:
    with open(BROWSER_JSON, "r", encoding="utf-8") as f:
        headers = json.load(f)
    raw_cookie = headers["cookie"]
    cookie = SimpleCookie()
    cookie.load(raw_cookie.replace('"', ""))
    sapisid = cookie["__Secure-3PAPISID"].value
    origin = "https://music.youtube.com"
    unix_timestamp = str(int(time.time()))
    sha_1 = sha1()
    sha_1.update((unix_timestamp + " " + sapisid + " " + origin).encode("utf-8"))
    headers["authorization"] = "SAPISIDHASH " + unix_timestamp + "_" + sha_1.hexdigest()
    with open(BROWSER_JSON, "w", encoding="utf-8") as f:
        json.dump(headers, f, ensure_ascii=True, indent=4, sort_keys=True)

BROWSER_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser.json")
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "import_progress.json")


def load_ids_from_progress(path: str) -> list[tuple[str, str]]:
    """Return [(playlist_name, playlist_id), ...] from import_progress.json."""
    if not os.path.exists(path):
        print(f"No file: {path}", file=sys.stderr)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: list[tuple[str, str]] = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "done":
            continue
        pid = entry.get("yt_playlist_id")
        if pid:
            out.append((name, pid))
    return out


def load_ids_from_library(yt: YTMusic) -> list[tuple[str, str]]:
    """All playlists in your YT Music library (limit=None = fetch all)."""
    playlists = yt.get_library_playlists(limit=None)
    return [(p.get("title") or "(no title)", p["playlistId"]) for p in playlists if p.get("playlistId")]


def main() -> None:
    ap = argparse.ArgumentParser(description="Bulk delete YouTube Music playlists")
    ap.add_argument("--dry-run", action="store_true", help="Print only, do not delete")
    ap.add_argument(
        "--all-library",
        action="store_true",
        help="Delete ALL playlists in your library (not just import_progress). EXTREMELY DESTRUCTIVE.",
    )
    ap.add_argument(
        "--progress",
        default=PROGRESS_FILE,
        help=f"Path to import_progress.json (default: {PROGRESS_FILE})",
    )
    args = ap.parse_args()

    if not os.path.exists(BROWSER_JSON):
        print(f"Missing {BROWSER_JSON}", file=sys.stderr)
        sys.exit(1)

    refresh_browser_auth()
    yt = YTMusic(BROWSER_JSON)

    if args.all_library:
        pairs = load_ids_from_library(yt)
        print(f"\n*** ALL LIBRARY MODE: {len(pairs)} playlists ***\n")
        for title, _ in pairs[:15]:
            print(f"  - {title}")
        if len(pairs) > 15:
            print(f"  ... and {len(pairs) - 15} more")
        if not args.dry_run:
            confirm = input('\nType DELETE ALL (exactly) to delete every playlist above: ')
            if confirm != "DELETE ALL":
                print("Aborted.")
                sys.exit(0)
    else:
        pairs = load_ids_from_progress(args.progress)
        if not pairs:
            print("No completed imports with yt_playlist_id in progress file.")
            print("If you deleted import_progress.json, use --all-library (careful) or restore a backup.")
            sys.exit(1)
        print(f"Found {len(pairs)} playlist(s) from import progress.\n")

    deleted = 0
    errors = 0
    for i, (title, pid) in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] {title[:60]}…" if len(title) > 60 else f"[{i}/{len(pairs)}] {title}")
        print(f"         ID: {pid}")
        if args.dry_run:
            continue
        try:
            yt.delete_playlist(pid)
            deleted += 1
            time.sleep(0.35)
        except Exception as e:
            err = str(e)
            if "Expecting value" in err or "line 1 column 1" in err:
                try:
                    refresh_browser_auth()
                    yt = YTMusic(BROWSER_JSON)
                    yt.delete_playlist(pid)
                    deleted += 1
                    print("         (retry after auth refresh: OK)")
                    time.sleep(0.5)
                    continue
                except Exception as e2:
                    err = str(e2)
            print(f"         ERROR: {err}", file=sys.stderr)
            errors += 1
            time.sleep(1.0)

    print()
    if args.dry_run:
        print(f"Dry run: would delete {len(pairs)} playlist(s).")
    else:
        print(f"Deleted: {deleted}, errors: {errors}")


if __name__ == "__main__":
    main()
