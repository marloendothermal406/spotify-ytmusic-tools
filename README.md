# music-migration-tools

Python scripts to migrate your Spotify library to YouTube Music — including all playlists, tracks, and cleanup utilities.

Works great with [Metrolist](https://github.com/MetrolistGroup/Metrolist) and any YouTube Music client.

---

## What's included

| Script | What it does |
|---|---|
| [`fetch_spotify.py`](#1-fetch_spotifypy) | Fetch all your Spotify playlists + tracks via the official API |
| [`fetch_spotify_partner.py`](#2-fetch_spotify_partnerpy) | Same, but uses the internal partner API (catches more playlists) |
| [`build_import.py`](#3-build_importpy) | Build the import JSON from Spotify CSV exports (Exportify) |
| [`compare_playlists.py`](#4-compare_playlistspy) | Compare what's on Spotify vs YouTube Music side by side |
| [`count_spotify_playlists.py`](#5-count_spotify_playlistspy) | List all your Spotify playlists with owner and track counts |
| [`yt_import.py`](#6-yt_importpy) | Import playlists from `spotify_tracks.json` into YouTube Music |
| [`delete_ytm_imports.py`](#7-delete_ytm_importspy) | Bulk-delete playlists from YouTube Music (undo bad imports) |

---

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### YouTube Music auth (one-time)

```bash
ytmusicapi browser
# Follow the prompt — paste your request headers from music.youtube.com
# This creates browser.json in the current folder
```

### Spotify auth

- **`fetch_spotify.py` / `fetch_spotify_partner.py`:** No app registration needed — just copy a token from your browser DevTools (see each script's docstring).
- **`count_spotify_playlists.py` / `build_import.py` with OAuth:** Create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), set redirect URI to `http://localhost:8888/callback`, export `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`.

---

## Typical workflow

```
Spotify ──► fetch_spotify.py ──► spotify_tracks.json ──► yt_import.py ──► YouTube Music
```

```bash
# 1. Fetch your Spotify library
python3 fetch_spotify.py <BEARER_TOKEN>

# 2. Import into YouTube Music (resumes if interrupted)
python3 yt_import.py

# 3. Check what's still missing
python3 compare_playlists.py spotify.txt ytmusic.txt

# 4. If something went wrong, bulk-delete and retry
python3 delete_ytm_imports.py --dry-run   # preview
python3 delete_ytm_imports.py             # actually delete
```

---

## Scripts

### 1. `fetch_spotify.py`

Fetches **all your Spotify playlists and their tracks** using a browser token.
No app registration needed.

```bash
python3 fetch_spotify.py <BEARER_TOKEN>
```

**Getting the token:**
1. Open [open.spotify.com](https://open.spotify.com) while logged in
2. Open DevTools → Network → filter `api.spotify.com`
3. Click any request → Headers → copy `Authorization` (everything after `Bearer `)

**Output:** `spotify_tracks.json`

---

### 2. `fetch_spotify_partner.py`

Like `fetch_spotify.py` but uses Spotify's internal GraphQL partner API.
Useful if the standard API misses some playlists (e.g. collaborative, imported).

```bash
python3 fetch_spotify_partner.py <BEARER_TOKEN> <CLIENT_TOKEN>
```

**Getting the tokens:**
1. Open [open.spotify.com](https://open.spotify.com) while logged in
2. Open DevTools → Network → filter `api-partner.spotify.com`
3. Click any request → Headers:
   - `authorization` → BEARER_TOKEN (strip the `Bearer ` prefix)
   - `client-token` → CLIENT_TOKEN

**Output:** `spotify_tracks.json`

---

### 3. `build_import.py`

Converts Spotify CSV exports (from [Exportify](https://exportify.net)) into the JSON format used by `yt_import.py`.

```bash
python3 build_import.py <CSV_FOLDER> [output.json]
```

**Output:** `spotify_tracks.json`

---

### 4. `compare_playlists.py`

Compares your Spotify and YouTube Music libraries and shows what's missing, what's in both, and what's only on YouTube Music.

Reads text files exported from the [SongShift](https://songshift.com/) or similar app selection screens.

```bash
python3 compare_playlists.py spotify.txt ytmusic.txt
```

**Output format expected (`spotify.txt` / `ytmusic.txt`):**
```
Playlist Name
42/42 selected
Another Playlist
10/10 selected
```

---

### 5. `count_spotify_playlists.py`

Lists all your Spotify playlists (including private ones) with owner and track count.

```bash
export SPOTIPY_CLIENT_ID="your_id"
export SPOTIPY_CLIENT_SECRET="your_secret"
python3 count_spotify_playlists.py
```

**Output:** prints list + saves `spotify_playlists_report.txt`

---

### 6. `yt_import.py`

The main import engine. Reads `spotify_tracks.json` and creates matching playlists on YouTube Music.

**Features:**
- Fuzzy song matching with scoring (title, artist, duration)
- Penalises karaoke, nightcore, covers, speed-up versions
- Multiple search strategies (title+artist, artist-title, title only)
- Auto-retries with SAPISIDHASH refresh when sessions go stale
- Resumable — saves progress to `import_progress.json`
- Handles playlists > 300 tracks (YouTube API limit)

```bash
# Setup auth first
ytmusicapi browser   # creates browser.json

# Run import
python3 yt_import.py

# Preview without making changes
python3 yt_import.py --dry

# Retry only failed/not-found playlists
python3 yt_import.py --retry-failed
```

**Files used:**
- `browser.json` — YT Music auth (created by `ytmusicapi browser`)
- `spotify_tracks.json` — playlist data (created by `fetch_spotify.py`)
- `import_progress.json` — auto-saved progress (resume-safe)

---

### 7. `delete_ytm_imports.py`

Bulk-deletes YouTube Music playlists. Useful if an import failed partway through and you want to clean up and retry.

```bash
# Preview what would be deleted
python3 delete_ytm_imports.py --dry-run

# Delete playlists from import_progress.json (only "done" ones)
python3 delete_ytm_imports.py

# Delete ALL playlists in your library (dangerous — requires typing DELETE ALL)
python3 delete_ytm_imports.py --all-library
```

Auto-refreshes auth when sessions expire mid-run.

---

## Tips

- **Token expiry:** Spotify browser tokens last ~1 hour. If you get 401s, copy a new token.
- **Rate limits:** Scripts back off automatically on 429s. Don't run multiple scripts at the same time.
- **Resume:** `yt_import.py` saves progress after every playlist. Kill and restart anytime.
- **Large libraries:** The partner API (`fetch_spotify_partner.py`) handles 600+ playlist libraries better than the standard API.
- **YTMusic auth expiry:** If `yt_import.py` starts getting empty JSON responses after several hours, it auto-refreshes the SAPISIDHASH from your cookie. If it still fails, re-run `ytmusicapi browser`.

---

## License

MIT
