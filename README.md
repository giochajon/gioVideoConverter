# gioVideoConvert

Self-hosted, dockerized video transcoding app built on headless HandBrakeCLI, with an
interactive on-demand mode and an unattended nightly batch mode. Backend: FastAPI +
Redis. Frontend: React, served on port 9095.

## Setup

1. Copy `.env.example` to `.env` and set `MOVIE_DIR`, `SERIES_DIR`, `INTERACTIVE_DIR`
   (host folders bind-mounted into the container) and `LOG_DIR` (a host folder
   **outside** this project directory, used for the persistent batch conversion log).
2. `docker compose up -d --build`
3. Open `http://localhost:9095`.

## Modes

- **Interactive** (`/`) — browse any of the three configured folders (Interactive,
  Movies, Series) via tabs, multi-select files, enqueue them for conversion. Each
  folder's read/write permissions are checked live and surfaced as a warning if
  something's misconfigured. Status is stored in Redis so it survives page
  navigation/reloads. The red **STOP ALL** button kills any in-flight conversion and
  clears the interactive queue.
- **Batch** (`/batch`) — disabled by default. Enable for either Movies (top 5 files over
  1.5GB in `MOVIE_DIR`) or Series (largest `Season NN` folder found anywhere under
  `SERIES_DIR`, one season per night, rotating through folders already converted) —
  mutually exclusive. Runs nightly during a configurable window (default 1:30–5:30 AM
  `TZ`, default `America/Denver`; change it from Settings — takes effect immediately,
  no restart needed). A toggle switches between **Queued** (what's waiting to be
  processed, with a "Remove" button per item) and **Recently Processed** (the
  conversion log, also removable per entry) — the two are never shown mixed together.
  The nightly scan never re-queues a file that's already queued/running elsewhere, or
  one that's already been converted (identified by its `[<preset name>]` tag).
- **Settings** (`/settings`) — choose the HandBrake preset (default `Fast 720p30`) and
  the nightly batch start/stop time; configured folders are shown read-only (set via
  `.env`).

Converted files are written back into the same folder the source file was picked up
from, with any `[...]` tag in the filename stripped and replaced with `[<preset name>]`.
The original file is deleted after a successful conversion. Every finished conversion —
interactive or batch — is recorded in the persistent log with its start time, finish
time, and duration.

If a conversion fails, processing halts immediately, the queue is left untouched for
review, and batch mode is auto-disabled. Use the "Resume" button (or `/batch` toggle)
after investigating.

## Local frontend dev

```
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:9095` — run the backend separately
(`uvicorn app.main:app --reload` from `backend/`, with a local Redis available) for a
live-reloading dev loop.
