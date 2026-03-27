import re

def parse_playlists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines()]

    playlists = {}
    i = 0
    while i < len(lines) - 1:
        match = re.match(r'^(\d+)/\d+ selected$', lines[i + 1])
        if match and lines[i] not in (
            'Entire Library', 'Favorite Songs', 'Favorite Albums',
            'Favorite Artists', 'Choose Destination', ''
        ) and not lines[i].startswith('Playlists ('):
            name = lines[i]
            count = int(match.group(1))
            if name not in playlists or count > playlists[name]:
                playlists[name] = count
            i += 2
        else:
            i += 1
    return playlists

import sys as _sys
_spotify_txt = _sys.argv[1] if len(_sys.argv) > 1 else "spotify.txt"
_ytmusic_txt = _sys.argv[2] if len(_sys.argv) > 2 else "ytmusic.txt"

spotify = parse_playlists(_spotify_txt)
ytmusic = parse_playlists(_ytmusic_txt)

def normalize(name):
    return re.sub(r'[\s\u200b\u00a0]+', ' ', name.lower().strip())
    
sp_norm = {normalize(k): (k, v) for k, v in spotify.items()}
yt_norm = {normalize(k): (k, v) for k, v in ytmusic.items()}

missing_from_yt = []
for norm_name, (orig_name, sp_count) in sp_norm.items():
    found = False
    for yt_norm_name in yt_norm:
        if norm_name == yt_norm_name or norm_name in yt_norm_name or yt_norm_name in norm_name:
            found = True
            break
    if not found:
        missing_from_yt.append((orig_name, sp_count))

in_both = []
for norm_name, (sp_name, sp_count) in sp_norm.items():
    for yt_norm_name, (yt_name, yt_count) in yt_norm.items():
        if norm_name == yt_norm_name or norm_name in yt_norm_name or yt_norm_name in norm_name:
            in_both.append((sp_name, sp_count, yt_name, yt_count))
            break

only_on_yt = []
for norm_name, (orig_name, yt_count) in yt_norm.items():
    found = False
    for sp_norm_name in sp_norm:
        if norm_name == sp_norm_name or norm_name in sp_norm_name or sp_norm_name in norm_name:
            found = True
            break
    if not found:
        only_on_yt.append((orig_name, yt_count))

print("=" * 70)
print(f" SPOTIFY: {len(spotify)} playlists | YOUTUBE MUSIC: {len(ytmusic)} playlists")
print("=" * 70)

print(f"\n{'='*70}")
print(f" MISSING FROM YOUTUBE MUSIC ({len(missing_from_yt)} playlists)")
print(f" These are on Spotify but NOT on YouTube Music")
print(f"{'='*70}")
for name, count in sorted(missing_from_yt, key=lambda x: x[1], reverse=True):
    print(f"  {count:>5} songs | {name}")

print(f"\n{'='*70}")
print(f" IN BOTH ({len(in_both)} playlists)")
print(f" Song count: Spotify vs YouTube Music")
print(f"{'='*70}")
for sp_name, sp_count, yt_name, yt_count in sorted(in_both, key=lambda x: abs(x[1]-x[3]), reverse=True):
    diff = yt_count - sp_count
    marker = "" if abs(diff) < 5 else f" ({'+'if diff>0 else ''}{diff})"
    display_name = sp_name if sp_name == yt_name else f"{sp_name} → {yt_name}"
    print(f"  SP:{sp_count:>5} | YT:{yt_count:>5}{marker:>10} | {display_name}")

if only_on_yt:
    print(f"\n{'='*70}")
    print(f" ONLY ON YOUTUBE MUSIC ({len(only_on_yt)} playlists)")
    print(f" These are on YouTube Music but NOT on Spotify")
    print(f"{'='*70}")
    for name, count in sorted(only_on_yt, key=lambda x: x[1], reverse=True):
        print(f"  {count:>5} songs | {name}")

total_missing_songs = sum(c for _, c in missing_from_yt)
print(f"\n{'='*70}")
print(f" SUMMARY")
print(f"{'='*70}")
print(f"  Spotify total:              {len(spotify)} playlists")
print(f"  YouTube Music total:        {len(ytmusic)} playlists")
print(f"  Found in both:              {len(in_both)} playlists")
print(f"  Missing from YT Music:      {len(missing_from_yt)} playlists ({total_missing_songs} songs)")
print(f"  Only on YT Music:           {len(only_on_yt)} playlists")
print(f"{'='*70}")
