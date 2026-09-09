# Lidarr to DroppedNeedle

`lidarr_to_droppedneedle.py` reads the artists and albums configured in Lidarr and submits missing albums to DroppedNeedle using their MusicBrainz IDs.

The script is safe by default: without `--submit`, it only fetches Lidarr data and prints the albums that would be requested.

## Requirements

- Python 3.10 or newer
- Network access to Lidarr and DroppedNeedle
- A Lidarr API key
- A DroppedNeedle bearer token for submissions

The scripts and the reusable `droppedneedle` package use only Python's standard library; no package installation is required.

## Configuration

The internal lab URLs are used by default:

- Lidarr: `https://lidarr.k3s.nf.lab`
- DroppedNeedle: `https://droppedneedle.k3s.nf.lab`

Set credentials through environment variables:

```bash
export LIDARR_API_KEY='your-lidarr-api-key'
export DROPPEDNEEDLE_USERNAME='your-droppedneedle-username'
export DROPPEDNEEDLE_PASSWORD='your-droppedneedle-password'
```

You can override the URLs with:

```bash
export LIDARR_URL='https://lidarr.example.com'
export DROPPEDNEEDLE_URL='https://droppedneedle.example.com'
```

Credentials can also be passed with the DroppedNeedle username/password CLI options.

## Python client

The `droppedneedle` package provides authenticated transport plus grouped
resource classes. The generic `call()` method exposes any endpoint declared in
`dn_openapi.json`.

```python
from droppedneedle import DroppedNeedleApi, DroppedNeedleAuth, DroppedNeedleClient

client = DroppedNeedleClient("https://droppedneedle.example.com")
DroppedNeedleAuth(client).login("username", "password")
api = DroppedNeedleApi(client)

albums = api.search.search("Boards of Canada")
held = api.downloads.held()
```

## Usage

Run a dry run first:

```bash
python3 scripts/lidarr_to_droppedneedle.py
```

By default, the script selects monitored albums that do not already have files in Lidarr. It prints the artist, album title, and MusicBrainz album ID for every selected album.

Submit the selected albums to DroppedNeedle:

```bash
python3 scripts/lidarr_to_droppedneedle.py --submit
```

`--submit` is the only option that makes POST requests to DroppedNeedle. Each album is submitted individually, and the script reports successful and failed requests separately.

Cancel downloads and retries with a dry run:

```bash
python3 scripts/cancel_downloads.py
```

With no scope flags, this previews active downloads, scheduled auto-retries,
and held review files. Apply the preview explicitly with `--sync`, or choose
one scope such as `--active`, `--retries`, or `--held`. Use `--limit 1` for a
controlled test. Held cleanup deletes the secured held files; completed and
cancelled download history is never cleared by this command.

```bash
python3 scripts/cancel_downloads.py --active --retries --sync
```

Report albums with missing local tracks:

```bash
python3 scripts/find_missing_tracks.py
python3 scripts/find_missing_tracks.py --artist "Boards of Canada" --limit 10
python3 scripts/find_missing_tracks.py --details --album-id LIBRARY_ALBUM_ID
```

This checks albums in DroppedNeedle's local library against the tracklist of
their linked MusicBrainz release. A track is reported as missing when no local
track with a matching recording ID and a non-zero `file_size_bytes` is found;
tracks without a recording ID use disc and track position as a fallback. The
default report shows each incomplete album as `present/expected` and a
completion percentage, such as `3/10 tracks (30% complete)`. Use `--details`
to retain the per-track missing list. The command is report-only and never
requests, downloads, deletes, or changes library data. Albums without a linked
MusicBrainz release are reported as skipped.

## Options

```text
--lidarr-url URL                 Override the Lidarr URL
--lidarr-api-key KEY             Override LIDARR_API_KEY
--droppedneedle-url URL          Override the DroppedNeedle URL
--droppedneedle-token TOKEN      Override DROPPEDNEEDLE_TOKEN
--include-downloaded             Include albums that already have files
--unmonitored                    Include albums not monitored by Lidarr
--submit                         Create DroppedNeedle requests
--timeout SECONDS                HTTP timeout; default is 30 seconds
```

For example, include all Lidarr albums, regardless of file or monitored status:

```bash
python3 scripts/lidarr_to_droppedneedle.py \
  --include-downloaded \
  --unmonitored
```

## Behavior

- Albums without a MusicBrainz album ID are skipped.
- Duplicate album IDs are submitted only once.
- Existing downloaded albums are excluded unless `--include-downloaded` is used.
- Unmonitored albums are excluded unless `--unmonitored` is used.
- Lidarr GET requests are retried automatically after transient failures.
- DroppedNeedle POST requests are not retried automatically, preventing accidental duplicate submissions.
