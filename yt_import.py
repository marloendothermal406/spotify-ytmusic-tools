import json
import re
import time
import os
import sys
import unicodedata
from hashlib import sha1
from http.cookies import SimpleCookie

from ytmusicapi import YTMusic

_HERE = os.path.dirname(os.path.abspath(__file__))
BROWSER_JSON = os.path.join(_HERE, "browser.json")
TRACKS_JSON = os.path.join(_HERE, "spotify_tracks.json")
PROGRESS_FILE = os.path.join(_HERE, "import_progress.json")


def refresh_browser_auth():
    """Refresh SAPISIDHASH in browser.json (fixes empty JSON responses after long runs)."""
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


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def norm_tokens(s):
    if not s:
        return []
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return [t for t in s.split() if len(t) > 1]


def artists_to_string(artists):
    if not artists:
        return ""
    parts = []
    for a in artists:
        if isinstance(a, dict):
            parts.append(a.get("name", ""))
        else:
            parts.append(str(a))
    return " ".join(parts)


def score_candidate(r, track_name, track_artist, duration_ms):
    """
    Score a YouTube Music search hit vs Spotify track.
    Higher = more likely the correct recording (not a random cover at rank 1).
    """
    title = (r.get("title") or "").lower()
    artist_blob = artists_to_string(r.get("artists") or []).lower()
    combined = f"{title} {artist_blob}"

    score = 0.0
    skip_words = {"the", "a", "an", "feat", "ft", "featuring", "vs", "and", "remix", "mix"}

    for t in norm_tokens(track_artist):
        if len(t) < 2:
            continue
        if t in artist_blob:
            score += 4.0
        elif t in title:
            score += 1.5

    for t in norm_tokens(track_name):
        if t in skip_words or len(t) < 3:
            continue
        if t in title:
            score += 2.0

    # Soft penalties for common wrong-match patterns
    junk = ("karaoke", "8d audio", "nightcore", "speed up", "tiktok", "reaction")
    for j in junk:
        if j in title:
            score -= 3.0

    # Slight preference for uploads that look like real tracks
    if "official" in title or "official audio" in title:
        score += 0.5
    if "cover by" in title or "covered by" in title:
        score -= 2.5

    ds = r.get("duration_seconds")
    if duration_ms and ds:
        diff_ms = abs(ds * 1000 - duration_ms)
        if diff_ms < 5000:
            score += 5.0
        elif diff_ms < 15000:
            score += 3.0
        elif diff_ms < 45000:
            score += 1.0

    return score


def pick_best_video_id(results, track_name, track_artist, duration_ms):
    if not results:
        return None
    best_id = None
    best_score = float("-inf")
    for r in results:
        vid = r.get("videoId")
        if not vid:
            continue
        s = score_candidate(r, track_name, track_artist, duration_ms)
        if s > best_score:
            best_score = s
            best_id = vid
    # If everything scored terribly, fall back to first result with videoId
    if best_score < 1.0:
        for r in results:
            vid = r.get("videoId")
            if vid:
                return vid
    return best_id


consecutive_errors = 0


def search_song(yt, name, artist, duration_ms=0):
    global consecutive_errors

    def do_search(query, limit=10):
        nonlocal yt
        for attempt in range(3):
            try:
                results = yt.search(query, filter="songs", limit=limit)
                consecutive_errors = 0
                return results
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    wait = min(30, consecutive_errors * 5)
                    print(f"      Rate limited, backing off {wait}s...", flush=True)
                    time.sleep(wait)
                else:
                    time.sleep(2)
                if attempt == 2:
                    return None
        return None

    # Primary query: title + artist (same as before)
    results = do_search(f"{name} {artist}")
    if results:
        vid = pick_best_video_id(results, name, artist, duration_ms)
        if vid:
            return vid

    # Alternate query: "artist - title" often matches YT upload titles
    results = do_search(f"{artist} - {name}")
    if results:
        vid = pick_best_video_id(results, name, artist, duration_ms)
        if vid:
            return vid

    # Last resort: title only
    results = do_search(name, limit=8)
    if results:
        return pick_best_video_id(results, name, artist, duration_ms)

    return None


def create_playlist_with_retry(yt, name, video_ids, tracks_len):
    """create_playlist sometimes returns empty body when session is stale — retry with auth refresh."""
    first_batch = video_ids[:300]
    last_err = None
    for attempt in range(3):
        try:
            if attempt > 0:
                refresh_browser_auth()
                yt = YTMusic(BROWSER_JSON)
                time.sleep(2 + attempt * 5)
            playlist_id = yt.create_playlist(
                title=name,
                description=f"Imported from Spotify ({len(video_ids)}/{tracks_len} songs)",
                privacy_status="PRIVATE",
                video_ids=first_batch,
            )
            remaining = video_ids[300:]
            while remaining:
                batch = remaining[:300]
                remaining = remaining[300:]
                try:
                    yt.add_playlist_items(playlist_id, batch, duplicates=False)
                    time.sleep(1)
                except Exception as e:
                    print(f"    Warning: batch add error: {e}", flush=True)
            return playlist_id, yt
        except Exception as e:
            last_err = e
            print(f"    create_playlist attempt {attempt + 1}/3 failed: {e}", flush=True)
    raise last_err


def main():
    dry_run = "--dry" in sys.argv
    retry_failed = "--retry-failed" in sys.argv

    print("Loading data...", flush=True)
    with open(TRACKS_JSON, "r", encoding="utf-8") as f:
        playlists = json.load(f)

    print(f"Loaded {len(playlists)} playlists", flush=True)

    if dry_run:
        print("[DRY RUN] No changes will be made to YouTube Music", flush=True)

    print("Connecting to YouTube Music...", flush=True)
    yt = YTMusic(BROWSER_JSON)
    print("Connected!", flush=True)

    progress = load_progress()
    imported = 0
    skipped = 0
    failed = 0

    playlist_items = sorted(playlists.items(), key=lambda x: len(x[1]), reverse=True)

    for i, (name, tracks) in enumerate(playlist_items, 1):
        st = progress.get(name, {}).get("status")
        if retry_failed:
            if st not in ("error", "no_songs_found"):
                if st == "done":
                    print(f"\n[{i}/{len(playlists)}] SKIP (already imported): {name}", flush=True)
                    skipped += 1
                continue
        elif st == "done":
            print(f"\n[{i}/{len(playlists)}] SKIP (already imported): {name}", flush=True)
            skipped += 1
            continue

        print(f"\n[{i}/{len(playlists)}] {name} ({len(tracks)} tracks)", flush=True)

        if dry_run:
            print(f"  [DRY RUN] Would search and create playlist", flush=True)
            continue

        print(f"  Searching YouTube Music...", flush=True)
        video_ids = []
        not_found = []
        for j, track in enumerate(tracks):
            vid = search_song(yt, track["name"], track["artist"], track.get("duration_ms", 0))
            if vid:
                video_ids.append(vid)
            else:
                not_found.append(f"{track['artist']} - {track['name']}")

            time.sleep(0.2)
            if (j + 1) % 50 == 0:
                print(f"    {j+1}/{len(tracks)} searched ({len(video_ids)} found)", flush=True)
                time.sleep(2)

        print(f"  Found {len(video_ids)}/{len(tracks)} songs", flush=True)

        if not_found and len(not_found) <= 20:
            for nf in not_found:
                print(f"    NOT FOUND: {nf}", flush=True)
        elif not_found:
            print(f"    {len(not_found)} songs not found (showing first 10):", flush=True)
            for nf in not_found[:10]:
                print(f"      - {nf}", flush=True)

        if not video_ids:
            print(f"  ERROR: No songs found, skipping", flush=True)
            progress[name] = {"status": "no_songs_found", "total": len(tracks)}
            save_progress(progress)
            failed += 1
            continue

        print(f"  Creating playlist on YouTube Music...", flush=True)
        try:
            playlist_id, yt = create_playlist_with_retry(yt, name, video_ids, len(tracks))
            print(f"  SUCCESS: '{name}' — {len(video_ids)} songs (ID: {playlist_id})", flush=True)
            progress[name] = {
                "status": "done",
                "yt_playlist_id": playlist_id,
                "songs_added": len(video_ids),
                "songs_total": len(tracks),
                "not_found": len(not_found),
            }
            save_progress(progress)
            imported += 1
        except Exception as e:
            print(f"  ERROR creating playlist: {e}", flush=True)
            progress[name] = {"status": "error", "error": str(e)}
            save_progress(progress)
            failed += 1

        time.sleep(1)

    print(f"\n{'='*60}", flush=True)
    print(f" IMPORT COMPLETE", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Imported:  {imported}", flush=True)
    print(f"  Skipped:   {skipped}", flush=True)
    print(f"  Failed:    {failed}", flush=True)
    print(f"  Progress:  {PROGRESS_FILE}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
