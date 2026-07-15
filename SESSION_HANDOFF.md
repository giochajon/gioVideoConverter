# Session Handoff — gioVideoConvert

Status as of this update: **the app is built, deployed, and running live** against real
media folders on this host. All items from the original verification checklist have
been completed. This doc now records what's actually been proven to work, the real
bugs found and fixed along the way, and known limitations to keep in mind.

## What this project is

A self-hosted, dockerized video transcoder built on headless HandBrakeCLI:
- **Interactive mode** (`/`) — browse any of the three configured folders (Interactive,
  Movies, Series) via tabs, multi-select files, enqueue for conversion. Status persists
  in Redis across page navigation. Read/write permissions for each folder are checked
  live and surfaced in the UI. Red **STOP ALL** button kills the running HandBrake
  process and clears the interactive queue.
- **Batch mode** (`/batch`) — disabled by default. Enable for Movies (top 5 files
  >1.5GB in `MOVIE_DIR`) or Series (largest `Season NN` folder found anywhere under
  `SERIES_DIR`, regardless of category/show nesting) — mutually exclusive. Runs
  nightly during a configurable window, default **1:30–5:30 AM** `TZ` (default
  `America/Denver`), changeable live from Settings. Shows a live preview of tonight's
  pick (even before the window opens) plus a persistent JSONL conversion log.
- **Settings** (`/settings`) — HandBrake preset picker (default `Fast 720p30`, built
  from `HandBrakeCLI --preset-list`), nightly batch start/stop time pickers; the three
  folders are shown read-only (set via `.env`).
- Converted files replace the original **in the same source folder**; any `[...]` tag
  in the filename is stripped and replaced with `[<preset name>]`.
- On any conversion failure: processing halts immediately, queues are left untouched,
  batch mode auto-disables, and a "Resume" action in the UI clears the halt after
  manual review.

Stack: FastAPI + Redis (queue/status/settings) backend, React (Vite) frontend built
into the backend's static dir, all served on port **9095**. Only open-source
components (HandBrakeCLI, FastAPI, Redis, React).

## Key decisions locked in during planning

- Backend: **Python/FastAPI**, not Node — chosen for clean subprocess management of
  HandBrakeCLI and APScheduler for the nightly window.
- Scheduling: **in-process APScheduler**, timezone `America/Denver` (observes DST;
  functionally identical to Calgary/`America/Edmonton` — same offset and DST rules
  year-round).
- Containers: **3-service-worth of behavior in 2 containers** — one `app` image
  (backend + built frontend + HandBrakeCLI binary) + one `redis` container.
- Volumes: **3 separate bind mounts** from `.env` — `MOVIE_DIR`, `SERIES_DIR`,
  `INTERACTIVE_DIR` — plus a `LOG_DIR` holding `batch_log.jsonl`. (Design intent was for
  `LOG_DIR` to live outside the compose project dir; double check your own `.env` if
  that matters to you — it's easy to point it at a path inside the repo by accident.)
- After a successful conversion: **delete the original**, keep only the renamed
  converted file (matches the "reduce size" goal of batch mode).
- Series batch rotation: **compare at the Season-folder level directly**, not
  per-series. The scanner recursively finds every folder named like `Season NN`
  anywhere under `SERIES_DIR` (regardless of how many category/show levels sit above
  it — real libraries are often `SERIES_DIR/Category/Show/Season NN/`, not the flatter
  `SERIES_DIR/Show/Season NN/` originally assumed) and picks the single largest one
  each night. Already-converted seasons are tracked in a flat Redis set
  (`state:series_progress`) so they're excluded from future picks; when every known
  season has been converted, the set resets and rotation starts fresh.
- Presets: **built-in HandBrakeCLI presets only** (via `--preset-list`), no custom
  preset-JSON import.
- Batch window: **user-configurable from Settings**, stored in Redis (not static env
  config), with the nightly cron rescheduled live via APScheduler when changed — no
  restart required.

## Bugs found and fixed during runtime verification

These were all real, previously-unverified defects — the "Not yet verified" section of
the original handoff turned up actual bugs, which is exactly what it was for.

1. **Silent exception swallowing in the worker loop** — any crash during a transcode
   was caught by a bare `except Exception: sleep(2)` with zero logging, leaving jobs
   frozen at "running" forever with no trace of what happened. Fixed: crashes are now
   logged with full tracebacks, and the job is properly marked failed + the system
   halted (or, if the crash was actually a deliberate STOP ALL, marked cancelled — see
   #4 below).
2. **HandBrake progress parsing crash** — HandBrake writes progress via `\r` (carriage
   return, terminal-style in-place update), not `\n`. The old code used
   `stdout.readline()`, which only recognizes `\n`, so it kept buffering until it blew
   past asyncio's default 64KB line limit and raised `LimitOverrunError`. Fixed by
   reading raw chunks and splitting on either `\r` or `\n` manually.
3. **Preset dropdown always showed only "Fast 720p30"** — two compounding bugs:
   `list_presets()` read the subprocess's `stdout`, but HandBrake actually writes
   `--preset-list` output to `stderr`; and the parser was looking for lines starting
   with `+`, which doesn't match HandBrake's actual indented category-tree format.
   Fixed both; the dropdown now correctly shows all ~84 built-in presets.
4. **STOP ALL incorrectly halted the whole system** — `stop_all()` only marked
   *queued-but-not-yet-started* jobs as cancelled, never the *actively running* one. So
   killing the live subprocess made it exit non-zero, which fell through to the
   ordinary failure path and halted everything — meaning every real STOP ALL click
   would've required a manual "Resume" afterward. Fixed: the active job is now marked
   cancelled before being killed, so it's recognized and cleaned up without touching
   the halted state.
5. **Series batch folder-structure mismatch** — the original scanner assumed
   `SERIES_DIR/ShowName/Season NN/`, but this library is
   `SERIES_DIR/Category/ShowName/Season NN/` (with non-TV folders like `audiobooks`/
   `music` as siblings). It picked the largest *category* folder, tried to treat each
   *show* inside it as a season, found no matching episode files, and silently queued
   nothing. Fixed by recursing for any `Season NN`-named folder regardless of nesting
   depth (see design decision above). Known gap: shows with no `Season NN` subfolder at
   all (flat episodes directly in the show folder, e.g. some older single-season
   shows) aren't eligible for batch rotation.
6. **SPA routing 404 on page refresh** — the frontend uses React Router's
   `BrowserRouter` (real URL paths), so refreshing on `/batch` or `/settings` sent a
   real GET to the server, which only auto-served `index.html` for the exact root path
   and 404'd on everything else. Fixed by mounting static assets at `/assets`
   specifically and adding a catch-all fallback that serves `index.html` for any
   unmatched non-`/api/*` path.
7. **Missing `tzdata` package** — the container had no IANA timezone database
   installed. `ZoneInfo(settings.tz)` (used by the batch-window check) threw
   `ZoneInfoNotFoundError` on every single worker-loop iteration once batch mode was
   enabled, silently swallowed by bug #1 above until that was fixed and the error
   became visible. Net effect: **batch jobs would queue but never actually process**,
   on any night, until this was fixed. Fixed by adding the pure-Python `tzdata` package
   to `requirements.txt` (lighter-weight than adding OS-level `tzdata` via apt, and
   doesn't touch the already-fragile Dockerfile apt chain).

## Known limitations (not bugs, just current scope)

- Series batch rotation only considers shows organized with a `Season NN` subfolder;
  shows with episodes directly in the show folder (no season wrapper) are skipped.
- A season is marked "processed" as soon as it's *queued*, not once conversion actually
  *completes*. If a season is too large to finish inside one night's window, the
  remainder stays queued (not lost) but the season won't be picked again by the
  next night's queue-builder — it'll just keep draining from the existing queue.
- The batch window doesn't support wrapping past midnight (e.g. 23:00–02:00); it
  assumes start time < stop time on the same day, matching the original design.
- `LOG_DIR` in this deployment's `.env` currently points inside the project directory
  rather than outside it (see decisions section above) — works fine, just a deviation
  from the original design intent if that matters to you.

## Verified (all items from the original checklist)

- Docker build succeeds end-to-end; HandBrakeCLI + Python deps install cleanly.
- Runtime smoke test: SPA loads, `/api/settings` and `/api/settings/presets` respond
  correctly (HandBrakeCLI binary genuinely runs).
- End-to-end interactive conversion: enqueue → progress streams live → output renamed
  `Name [Preset].ext` → original deleted. Confirmed on real media files.
- STOP ALL mid-conversion: subprocess actually killed (no zombie/orphan), tmp file
  cleaned up, job marked cancelled, original file preserved, system stays live (no
  spurious halt).
- Failure handling: a corrupt file halts processing immediately, the queue is left
  untouched (a second queued file stays `queued`, doesn't get processed or cleared),
  batch mode auto-disables, and Resume cleanly restores normal operation and drains the
  queue that was waiting.
- Batch scheduling: verified queue-building for both Movies and Series targets via a
  read-only preview path (no side effects) and via direct invocation.
- Batch log: a real batch-mode conversion completed and produced a correct
  `batch_log.jsonl` entry (`started_at`, `filename`, `initial_size`, `final_size`,
  `status`), readable via `/api/batch/log`.
- No leftover test containers/networks at any point.

## Current live state (informational — will drift over time)

At the time of this update: batch mode is **enabled**, target **series**, window
**01:30–05:30** (`TZ=America/Denver`). The next nightly run will pick up wherever the
Season-folder rotation left off. Check `/api/batch/tonight` for a live preview of the
current pick, and `/api/batch/log` for conversion history.
