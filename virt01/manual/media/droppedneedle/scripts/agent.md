# AGENT.md - DroppedNeedle API

Notes for an agent (or human) writing scripts against the DroppedNeedle API.
DroppedNeedle is a self-hosted "music request and management system" — think
Overseerr/Ombi, but for music, matched against MusicBrainz.

Reference: `dn_openapi.json` (OpenAPI 1.0.0, 613 paths) in this repo/uploads is
the source of truth for schemas. This doc is a curated summary of the parts
that matter for request/library-management scripts; when in doubt, grep the
OpenAPI spec rather than trusting this doc, since DroppedNeedle is under
active development.

## Base URL

```
https://droppedneedle.k3s.nf.lab
```

Only reachable from inside the home network / k3s cluster — not from an
external sandbox. Test connectivity with a plain `curl` before debugging
"network" issues in a script.

## Auth

No formal OpenAPI `securitySchemes` are declared (the spec doesn't mark
endpoints as requiring auth), but in practice:

- **Login:** `POST /api/v1/auth/login`
  Body: `{"username": "...", "password": "..."}`
  Returns `AuthResponse`:
  ```json
  {
    "token": "...",
    "user": {
      "id": "...", "display_name": "...", "role": "...",
      "email": null, "avatar_url": null, "username": "...",
      "username_display": "...", "providers": [],
      "musicbrainz_source": {"source_mode": "brainzmash", "source_id": "...", "generation": 1}
    }
  }
  ```
  On bad credentials: `401` with
  `{"error": {"code": "INTERNAL_ERROR", "message": "Invalid username or password", "details": null}}`.

- **Use the token:** send `Authorization: Bearer <token>` on subsequent calls
  that mutate state or read user-scoped data (requests, held items, library
  writes). Some read-only/catalog-style endpoints (e.g. `GET /api/v1/albums/{mbid}`)
  appear to work without it in practice — but sending the header anyway is
  harmless, so default to always sending it once you have a token.

- Credentials should come from environment variables in scripts, never
  hardcoded: `DROPPEDNEEDLE_URL`, `DROPPEDNEEDLE_USERNAME`, `DROPPEDNEEDLE_PASSWORD`.

## Identifiers: MusicBrainz IDs are the primary key

Almost everything in this API is keyed by MusicBrainz ID (MBID) — artist
MBID, release-group/album MBID, recording MBID — rather than DroppedNeedle's
own internal integer IDs. When wiring up Lidarr (or any other source) to
DroppedNeedle, match on MBID, not on names or Lidarr's internal artist/album
IDs. A handful of endpoints do use DroppedNeedle-internal integer IDs instead
(e.g. held items, see below) — check each endpoint's path param type before
assuming MBID.

## Requesting content

- `POST /api/v1/requests/new` — request a single album or artist.
  ```json
  {
    "musicbrainz_id": "<album or artist mbid>",
    "artist_mbid": "<artist mbid>",
    "artist_name": "...",
    "album_title": "...",      // only meaningful for album requests
    "request_kind": "album"    // or "artist"
  }
  ```
  **Unconfirmed/inferred:** the exact shape and whether `request_kind: "artist"`
  is truly the mechanism for a whole-discography sync was inferred, not found
  documented. Empirically, DroppedNeedle appears to require that an artist
  already have at least one album requested/in-library before an
  artist-level request succeeds — so submit an album first, then the artist.
- `POST /api/v1/requests/batch` / `POST /api/v1/requests/batch/cancel` —
  batch variants exist; not yet used by our scripts, worth switching to for
  bulk syncs to cut down on request volume (see "Rate limiting" below).
- `GET /api/v1/requests/active`, `GET /api/v1/requests/history`,
  `GET /api/v1/requests/wanted` — check status of outstanding requests
  instead of re-requesting blindly.
- `DELETE /api/v1/requests/active/{musicbrainz_id}` — cancel a request.
- `POST /api/v1/requests/retry/{musicbrainz_id}` — retry a failed request.

## Checking whether something already exists (avoid duplicate requests)

**Confirmed, use this:** `GET /api/v1/albums/{musicbrainz_id}` returns full
album metadata plus two booleans that answer the question directly:

```json
{
  "title": "...", "musicbrainz_id": "...", "artist_name": "...",
  "artist_id": "...", "in_library": false, "requested": false,
  "tracks": [...], "cover_url": "...", ...
}
```

- `in_library: true` → DroppedNeedle already has this album downloaded.
- `requested: true` → already requested (in flight), don't re-request.
- `404` → DroppedNeedle has never heard of this MBID at all → safe to request.

This is a **per-album** lookup, so checking a large batch means one GET per
album. There is no confirmed bulk "give me the status of these 500 MBIDs"
endpoint — if performance matters, check `POST /api/v1/requests/batch` or
`GET /api/v1/library/mbids` (unexplored, name suggests it might return known
MBIDs in bulk) before assuming one-at-a-time is the only option.

Endpoints that sound like they'd do this but are **not** the right one:
`GET /api/v1/library/artists/{artist_id}/albums` and
`GET /api/v1/library/albums/{album_id}` use DroppedNeedle-internal
integer/target IDs (see `Get Target Artist Albums` / `Target Album Detail` in
the spec), not MBIDs — don't pass an MBID as `{album_id}` there.

## Held items ("Import Anyway" review queue)

When a download's audio matches the expected track by duration but its
AcoustID fingerprint disagrees with the expected recording — usually because
the file's own tags are for a different song — DroppedNeedle holds it for
manual review instead of auto-importing. This is the "COULDN'T VERIFY" queue
in the UI.

- `GET /api/v1/downloads/held` — list held items. Optional query param
  `release_group_mbid` to filter to one album. Returns `HeldListResponse`:
  ```json
  { "items": [ HeldImportResponse, ... ] }
  ```
  Key `HeldImportResponse` fields:
  | field | meaning |
  |---|---|
  | `id` | DroppedNeedle-internal integer ID (use this for discard/import, not an MBID) |
  | `artist_name`, `track_title`, `album_title` | what was **expected** |
  | `evidence_artist`, `evidence_title`, `evidence_score` | what AcoustID / the file's own tags actually say |
  | `reason`, `reason_detail` | why it's held (free-text string, no enum declared in the spec) |
  | `source_task_id` | links back to the originating download task |

  To detect a genuine tag mismatch programmatically: compare
  `evidence_title`/`evidence_artist` against `track_title`/`artist_name`
  (case/whitespace-insensitive). Don't just filter on `reason` text matching
  "COULDN'T VERIFY" — that's a UI label, not a guaranteed stable API value.

- `POST /api/v1/downloads/held/{held_id}/import` — import anyway (accept the
  mismatch, keep the file).
- `POST /api/v1/downloads/held/{held_id}/discard` — reject and delete the
  held file. `{held_id}` is the integer `id` from the list response.
- `POST /api/v1/downloads/held/reverify` (bulk) / `POST /api/v1/downloads/held/{held_id}/reverify`
  — re-run identity verification instead of discarding outright, in case a
  MusicBrainz metadata fix upstream would now make it verify cleanly.
- `POST /api/v1/downloads/held/management/{source_task_id}/retry` and
  `.../discard` — a separate "management hold" concept (distinct from the
  per-track held-import queue above); don't conflate the two `{id}` types.

## Library / Lidarr-style browsing (internal target IDs, not MBIDs)

A large `/api/v1/library/*` surface (target artists/albums/tracks, stats,
scan runs, identity repairs, duplicate-group merges, etc.) operates on
DroppedNeedle's own internal library, addressed by its own integer/string
`{artist_id}` / `{album_id}` / `{track_id}` — these are **not** MBIDs. If you
need to cross-reference an MBID-keyed request against this library surface,
look for an endpoint that accepts an MBID explicitly (e.g. `GET /api/v1/local/albums/match/{musicbrainz_id}`,
`GET /api/v1/jellyfin/albums/match/{musicbrainz_id}`) rather than assuming
the internal ID and the MBID are interchangeable.

## Error handling conventions

- **422** — Pydantic/FastAPI validation error:
  ```json
  {"detail": [{"loc": ["body", "field_name"], "msg": "...", "type": "..."}]}
  ```
  Parse `detail` for the actual field name/message rather than guessing —
  this is the fastest way to find the *real* expected payload shape when a
  guessed schema is wrong.
- **401** — bad credentials or missing/expired token.
- **404** — for lookup-by-ID endpoints (e.g. `GET /api/v1/albums/{mbid}`),
  treat as "doesn't exist yet" rather than a hard failure — this is the
  expected, common case when checking "have I already requested this."
- Other error bodies follow `{"error": {"code": "...", "message": "...", "details": null}}`.

## Rate limiting / etiquette

No documented rate limit, but this is a home-lab single-instance service —
be a good neighbor in scripts:
- Add a small delay (e.g. 0.3-0.5s) between POST/mutating calls in a loop.
- Prefer batch endpoints (`/api/v1/requests/batch`) over N sequential single
  calls once confirmed working.
- Check `in_library`/`requested` (or the batch equivalent) before submitting,
  to avoid pointless duplicate work across every non-Lidarr artist/album,
  especially if a sync script runs on a schedule.

## Existing scripts in this repo

- `lidarr_to_droppedneedle.py` — reads Lidarr's `/api/v1/artist` and
  `/api/v1/album`, requests missing/all albums into DroppedNeedle by MBID,
  optionally syncs whole artists (`--sync-artists`), checks `in_library`/
  `requested` before submitting (`--force` to skip), supports `--artist`/
  `--limit` scoping and `--list-artists` for quick artist enumeration.
- `discard_held_mismatches.py` — lists `GET /api/v1/downloads/held`, flags
  items where `evidence_title`/`evidence_artist` disagree with
  `track_title`/`artist_name`, and discards them via
  `POST /api/v1/downloads/held/{id}/discard`. Dry-run by default (`--sync`
  to act), `--artist`/`--limit` to scope a test batch first.

Both follow the same pattern: dry-run by default, explicit `--sync` flag to
mutate anything, small per-request delay, and print enough per-item detail in
dry-run mode to sanity-check before flipping `--sync` on.