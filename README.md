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

- **Interactive** (`/`) — browse `INTERACTIVE_DIR`, multi-select files, enqueue them for
  conversion. Status is stored in Redis so it survives page navigation/reloads. The red
  **STOP ALL** button kills any in-flight conversion and clears the interactive queue.
- **Batch** (`/batch`) — disabled by default. Enable for either Movies (top 5 files over
  1.5GB in `MOVIE_DIR`) or Series (largest series folder in `SERIES_DIR`, one season per
  night) — mutually exclusive. Runs nightly 2:00–5:00 AM `TZ` (default
  `America/Denver`). Shows tonight's queue and a persistent conversion log.
- **Settings** (`/settings`) — choose the HandBrake preset (default `Fast 720p30`);
  configured folders are shown read-only (set via `.env`).

Converted files are written back into the same folder the source file was picked up
from, with any `[...]` tag in the filename stripped and replaced with `[<preset name>]`.
The original file is deleted after a successful conversion.

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
