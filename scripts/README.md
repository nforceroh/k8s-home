# Lidarr to DroppedNeedle

`lidarr_to_droppedneedle.py` reads the artists and albums configured in Lidarr and submits missing albums to DroppedNeedle using their MusicBrainz IDs.

The script is safe by default: without `--submit`, it only fetches Lidarr data and prints the albums that would be requested.

## Requirements

- Python 3.10 or newer
- Network access to Lidarr and DroppedNeedle
- A Lidarr API key
- A DroppedNeedle bearer token for submissions

The script uses only Python's standard library; no package installation is required.

## Configuration

The internal lab URLs are used by default:

- Lidarr: `https://lidarr.k3s.nf.lab`
- DroppedNeedle: `https://droppedneedle.k3s.nf.lab`

Set credentials through environment variables:

```bash
export LIDARR_API_KEY='your-lidarr-api-key'
export DROPPEDNEEDLE_TOKEN='your-droppedneedle-bearer-token'
```

You can override the URLs with:

```bash
export LIDARR_URL='https://lidarr.example.com'
export DROPPEDNEEDLE_URL='https://droppedneedle.example.com'
```

Credentials can also be passed with `--lidarr-api-key` and `--droppedneedle-token`.

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
